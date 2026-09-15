from celery import Celery

from app.config import settings

celery = Celery(
    "agentic_rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingest"],
)
celery.conf.update(task_track_started=True, task_serializer="json", accept_content=["json"])
