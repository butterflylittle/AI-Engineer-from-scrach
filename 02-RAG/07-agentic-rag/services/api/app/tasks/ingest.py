import asyncio

from app.db.session import engine
from app.ingestion.pipeline import ingest_document
from app.tasks.celery_app import celery


# Celery 任务包装：把异步入库逻辑包成可投递的任务，失败自动重试（最多 3 次、指数退避）
@celery.task(name="documents.ingest", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def ingest_document_task(document_id: str) -> None:
    try:
        asyncio.run(ingest_document(document_id))
    finally:
        # 每次 asyncio.run() 新建事件循环，连接池里的旧连接绑定在已关闭的循环上，
        # 下次任务复用同一进程会报 "Future attached to a different loop"，这里清空连接池。
        engine.sync_engine.dispose()
