from __future__ import annotations

import re
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.schemas import SearchResult


# 重排器抽象：对检索候选按相关性重新排序，取 top_n
class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self, query: str, documents: list[SearchResult], top_n: int
    ) -> list[SearchResult]: ...


# 远端实现：调用外部重排模型（返回 index + relevance_score）
class APIReranker(Reranker):
    async def rerank(
        self, query: str, documents: list[SearchResult], top_n: int
    ) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                settings.rerank_api_base,
                headers={"Authorization": f"Bearer {settings.rerank_api_key}"},
                json={
                    "model": settings.rerank_model,
                    "query": query,
                    "documents": [item.content for item in documents],
                    "top_n": top_n,
                },
            )
            response.raise_for_status()
            ranked = response.json()["results"]
            # 用重排模型给的分数覆盖原向量相似度分数
            return [
                documents[item["index"]].model_copy(update={"score": item["relevance_score"]})
                for item in ranked
            ]


# 本地 fallback：按“向量分数 + 词法重合度”加权排序（仅供开发）
class LexicalReranker(Reranker):
    async def rerank(
        self, query: str, documents: list[SearchResult], top_n: int
    ) -> list[SearchResult]:
        terms = set(re.findall(r"[\w]+|[\u4e00-\u9fff]", query.lower()))

        def score(item: SearchResult) -> float:
            words = set(re.findall(r"[\w]+|[\u4e00-\u9fff]", item.content.lower()))
            lexical = len(terms & words) / max(len(terms), 1)
            return 0.65 * item.score + 0.35 * lexical

        ranked = sorted(documents, key=score, reverse=True)[:top_n]
        return [item.model_copy(update={"score": score(item)}) for item in ranked]


# 工厂函数：配置了重排接口用远端，否则退回词法重排
def get_reranker() -> Reranker:
    if settings.rerank_api_base and settings.rerank_api_key:
        return APIReranker()
    return LexicalReranker()
