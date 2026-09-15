from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx

from app.config import settings


# Embedding Provider 抽象：查询与文档共用同一套向量化接口
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


# 远端实现：调用 OpenAI 兼容 /embeddings 接口（支持批量）
class OpenAICompatibleEmbeddings(EmbeddingProvider):
    async def _embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.embedding_api_base.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={
                    "model": settings.embedding_model,
                    "input": texts,
                    "dimensions": settings.embedding_dimensions,
                },
            )
            response.raise_for_status()
            return [item["embedding"] for item in response.json()["data"]]

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)


# 本地 fallback：确定性哈希 Embedding（仅供开发，非语义模型）
class LocalHashEmbeddings(EmbeddingProvider):
    """Deterministic local fallback for development; not a semantic production model."""

    # 把每个词哈希到固定维度向量的一格并 +/-1，最后归一化
    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * settings.embedding_dimensions
        tokens = re.findall(r"[\w]+|[\u4e00-\u9fff]", text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            value = int.from_bytes(digest)
            vector[value % len(vector)] += 1.0 if value & 1 else -1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


# 工厂函数：配置了 API key 用远端，否则退回本地哈希实现
def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_api_key:
        return OpenAICompatibleEmbeddings()
    return LocalHashEmbeddings()
