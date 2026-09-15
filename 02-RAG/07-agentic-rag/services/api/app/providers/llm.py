from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from app.config import settings


# LLM Provider 抽象：统一封装 invoke（一次性）与 stream（流式）两种调用
class LLMProvider(ABC):
    @abstractmethod
    async def invoke(self, messages: list[dict[str, str]]) -> str: ...

    @abstractmethod
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if False:
            yield ""


# 远端实现：调用任意 OpenAI 兼容的 /chat/completions 接口
class OpenAICompatibleLLM(LLMProvider):
    async def invoke(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.llm_api_base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.llm_model, "messages": messages, "temperature": 0.1},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    # 流式：逐行解析 SSE 增量，yield 每次产生的文本片段
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream(
                "POST",
                f"{settings.llm_api_base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.llm_model, "messages": messages, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta


# 本地 fallback：未配置模型密钥时，用规则式回答保证链路可跑通（仅供开发）
class LocalLLM(LLMProvider):
    async def invoke(self, messages: list[dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        if "REWRITE_QUERY" in prompt:
            return prompt.split("QUESTION:", 1)[-1].strip().replace("?", "").replace("？", "")
        if "CONTEXT:" in prompt:
            context = prompt.split("CONTEXT:", 1)[1].split("QUESTION:", 1)[0].strip()
            excerpt = context[:420].strip()
            return f"根据知识库中的相关内容：{excerpt}" if excerpt else "知识库证据不足，无法可靠回答。"
        return "你好。我可以基于当前知识库回答问题；请告诉我你想了解什么。"

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        answer = await self.invoke(messages)
        for index in range(0, len(answer), 12):
            yield answer[index : index + 12]


# 工厂函数：配置了 API key 用远端，否则退回本地实现
def get_llm_provider() -> LLMProvider:
    return OpenAICompatibleLLM() if settings.llm_api_key else LocalLLM()
