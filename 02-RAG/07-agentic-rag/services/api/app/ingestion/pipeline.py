from sqlalchemy import delete, select

from app.db.models import Chunk, Document, DocumentStatus
from app.db.session import SessionLocal
from app.ingestion.parser import parse_document
from app.ingestion.splitter import split_elements
from app.providers import get_embedding_provider
from app.storage import ObjectStore


# 入库主流程（由 Celery worker 异步执行）：
#   标记处理中 → 从对象存储取原文件 → 解析 → 切块 → 向量化 → 删除旧 chunk 后写入新 chunk → 标记就绪
async def ingest_document(document_id: str) -> None:
    async with SessionLocal() as session:
        document = await session.scalar(select(Document).where(Document.id == document_id))
        if document is None:
            return
        document.status = DocumentStatus.processing.value
        document.error_message = None
        await session.commit()
        try:
            content = await ObjectStore().get(document.object_key)          # 取原文件字节
            elements = await parse_document(content, document.filename)     # 解析为元素
            parsed_chunks = split_elements(elements, document.filename)     # 切块
            vectors = await get_embedding_provider().embed_documents(       # 批量向量化
                [item.content for item in parsed_chunks]
            )
            await session.execute(delete(Chunk).where(Chunk.document_id == document.id))  # 清空旧 chunk（重跑时）
            session.add_all(
                [
                    Chunk(
                        document_id=document.id,
                        knowledge_base_id=document.knowledge_base_id,
                        content=item.content,
                        chunk_index=index,
                        page_number=item.page_number,
                        chunk_metadata=item.metadata,
                        embedding=vector,
                    )
                    for index, (item, vector) in enumerate(
                        zip(parsed_chunks, vectors, strict=True)
                    )
                ]
            )
            document.status = DocumentStatus.ready.value
            await session.commit()
        except Exception as exc:
            await session.rollback()
            document = await session.get(Document, document_id)
            if document:
                document.status = DocumentStatus.failed.value
                document.error_message = str(exc)[:1000]
                await session.commit()
            raise
