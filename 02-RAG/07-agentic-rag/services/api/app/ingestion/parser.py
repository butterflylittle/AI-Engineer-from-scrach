from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedElement:
    text: str
    page_number: int | None = None
    metadata: dict = field(default_factory=dict)


# 解析文档为结构化元素（ParsedElement）列表：
# 纯文本(.txt/.md)直接解码读取；PDF/DOCX 走 unstructured 库，在线程池执行避免阻塞事件循环
async def parse_document(content: bytes, filename: str) -> list[ParsedElement]:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return [
            ParsedElement(
                text=content.decode("utf-8", errors="replace"),
                metadata={"source_type": suffix.lstrip(".")},
            )
        ]

    if suffix not in {".pdf", ".docx"}:
        raise ValueError("Only PDF, DOCX, Markdown and TXT files are supported")

    def partition() -> list[ParsedElement]:
        from unstructured.partition.auto import partition as unstructured_partition

        with tempfile.NamedTemporaryFile(suffix=suffix) as file:
            file.write(content)
            file.flush()
            elements = unstructured_partition(filename=file.name, strategy="auto")
        return [
            ParsedElement(
                text=str(element),
                page_number=getattr(element.metadata, "page_number", None),
                metadata={"category": getattr(element, "category", "Text")},
            )
            for element in elements
            if str(element).strip()
        ]

    return await asyncio.to_thread(partition)
