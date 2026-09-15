from dataclasses import dataclass, field

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import settings
from app.ingestion.parser import ParsedElement

# 切块分隔符优先级：段落 → 换行 → 中文句末标点 → 逗号 → 空格 → 单字符
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


@dataclass
class ParsedChunk:
    content: str
    page_number: int | None
    metadata: dict = field(default_factory=dict)


# 把解析出的元素切分成 chunk：
# Markdown 先按标题(h1/h2/h3)切节，再对每节用递归字符切分器按 chunk_size/overlap 切块
def split_elements(elements: list[ParsedElement], filename: str) -> list[ParsedChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=SEPARATORS,
    )
    chunks: list[ParsedChunk] = []
    is_markdown = filename.lower().endswith((".md", ".markdown"))
    for element in elements:
        sections = [element.text]
        section_metadata = [{}]
        if is_markdown:
            documents = MarkdownHeaderTextSplitter(
                [("#", "h1"), ("##", "h2"), ("###", "h3")]
            ).split_text(element.text)
            sections = [document.page_content for document in documents]
            section_metadata = [document.metadata for document in documents]
        for section, headers in zip(sections, section_metadata, strict=True):
            for text in splitter.split_text(section):
                chunks.append(
                    ParsedChunk(
                        content=text,
                        page_number=element.page_number,
                        metadata={**element.metadata, **headers},   # 合并元素元信息与标题层级
                    )
                )
    return chunks
