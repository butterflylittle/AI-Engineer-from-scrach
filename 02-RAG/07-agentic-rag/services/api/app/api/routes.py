from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import build_graph
from app.auth import get_current_user
from app.config import settings
from app.db.models import Conversation, Document, KnowledgeBase, Message
from app.db.session import get_session
from app.providers import get_embedding_provider, get_llm_provider, get_reranker
from app.retrieval import PgVectorRetriever
from app.schemas import (
    ChatRequest,
    DocumentCreated,
    DocumentRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    Principal,
)
from app.storage import ObjectStore
from app.tasks.ingest import ingest_document_task

# ============================================================================
# API 路由：知识库 / 文档 / 会话 / 聊天的 HTTP 入口
# 两条主流程：
#   1) 上传入库：upload_document → 存对象存储 → 写 DB → 投递 Celery 异步任务
#   2) 问答查询：chat → 构建 LangGraph → astream 流式执行 → SSE 推给前端
# ============================================================================
router = APIRouter()
logger = logging.getLogger("agentic_rag")
ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}   # 允许上传的文件类型
MAX_UPLOAD_BYTES = 25 * 1024 * 1024                                  # 单文件大小上限 25MB


# 把事件包装成 SSE 帧：`event: <类型>\ndata: <JSON>\n\n`
def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 权限校验辅助：知识库必须属于当前用户，否则 404（避免泄露他人资源）
async def owned_knowledge_base(
    session: AsyncSession, knowledge_base_id: str, principal: Principal
) -> KnowledgeBase:
    knowledge_base = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == principal.user_id,
        )
    )
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return knowledge_base


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/api/knowledge-bases", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return list(
        await session.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == principal.user_id)
            .order_by(KnowledgeBase.updated_at.desc())
        )
    )


@router.post(
    "/api/knowledge-bases", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    knowledge_base = KnowledgeBase(user_id=principal.user_id, **payload.model_dump())
    session.add(knowledge_base)
    await session.commit()
    await session.refresh(knowledge_base)
    return knowledge_base


@router.get("/api/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    knowledge_base_id: str,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await owned_knowledge_base(session, knowledge_base_id, principal)
    return list(
        await session.scalars(
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.post(
    "/api/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    knowledge_base_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await owned_knowledge_base(session, knowledge_base_id, principal)
    # 校验文件类型与大小（仅允许 PDF/DOCX/MD/TXT，上限 25MB）
    safe_filename = Path(file.filename or "").name
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB")
    # 1) 原文件写入对象存储（key 按 用户/知识库/文档/文件名 组织）
    document_id = str(uuid4())
    object_key = f"{principal.user_id}/{knowledge_base_id}/{document_id}/{safe_filename}"
    await ObjectStore().put(object_key, content, file.content_type or "application/octet-stream")
    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        filename=safe_filename,
        object_key=object_key,
        mime_type=file.content_type or "application/octet-stream",
        size=len(content),
        status="uploaded",
    )
    # 2) 文档元信息写入 DB（状态 uploaded）
    session.add(document)
    await session.commit()
    # 3) 投递 Celery 异步入库任务，立即返回 202（解析/切块/向量化在 worker 完成）
    ingest_document_task.delay(document.id)
    return DocumentCreated(document_id=document.id, status=document.status)


@router.get("/api/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    document = await session.scalar(
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == document_id, KnowledgeBase.user_id == principal.user_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    document = await session.scalar(
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == document_id, KnowledgeBase.user_id == principal.user_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await ObjectStore().delete(document.object_key)
    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/documents/{document_id}/content")
async def document_content(
    document_id: str,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    document = await session.scalar(
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == document_id, KnowledgeBase.user_id == principal.user_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    content = await ObjectStore().get(document.object_key)
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(document.filename)}"},
    )


@router.get("/api/conversations")
async def list_conversations(
    knowledge_base_id: str,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await owned_knowledge_base(session, knowledge_base_id, principal)
    conversations = await session.scalars(
        select(Conversation)
        .where(
            Conversation.user_id == principal.user_id,
            Conversation.knowledge_base_id == knowledge_base_id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    return [
        {"id": item.id, "title": item.title, "updated_at": item.updated_at}
        for item in conversations
    ]


@router.post("/api/chat")
async def chat(
    payload: ChatRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await owned_knowledge_base(session, payload.knowledge_base_id, principal)
    # 找到或新建会话
    conversation = None
    if payload.conversation_id:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == principal.user_id,
                Conversation.knowledge_base_id == payload.knowledge_base_id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation is None:
        conversation = Conversation(
            user_id=principal.user_id,
            knowledge_base_id=payload.knowledge_base_id,
            title=payload.message[:80],
        )
        session.add(conversation)
        await session.flush()
    # 记录用户消息
    session.add(
        Message(conversation_id=conversation.id, role="user", content=payload.message, citations=[])
    )
    await session.commit()

    # 流式响应体：构建 LangGraph 并逐节点产出 SSE 事件
    async def event_stream():
        trace_id = str(uuid4())
        started = time.perf_counter()
        # 注入检索器 / 重排器 / LLM，编译状态图
        graph = build_graph(
            PgVectorRetriever(session, get_embedding_provider()), get_reranker(), get_llm_provider()
        )
        state = {
            "conversation_id": conversation.id,
            "principal": principal,
            "knowledge_base_id": payload.knowledge_base_id,
            "question": payload.message,
            "rewrite_rounds": 0,
            "retrieved_documents": [],
            "reranked_documents": [],
            "citations": [],
        }
        answer = ""
        citations = []
        metrics = {
            "trace_id": trace_id,
            "query": payload.message[:500],
            "retrieval_used": False,
            "top_k_results": 0,
            "top_n_results": 0,
            "rewrite_rounds": 0,
        }
        previous = time.perf_counter()
        try:
            # stream_mode="updates"：每执行完一个节点就 yield 该节点的状态更新
            async for update in graph.astream(state, stream_mode="updates"):
                node, values = next(iter(update.items()))
                now = time.perf_counter()
                metrics[f"{node}_latency_ms"] = round((now - previous) * 1000, 1)
                previous = now
                # 先推送节点名，前端据此更新进度
                yield sse("status", {"stage": node, "trace_id": trace_id})
                if node == "route":
                    metrics["retrieval_used"] = values.get("requires_retrieval", False)
                elif node == "retrieve":
                    metrics["top_k_results"] = len(values.get("retrieved_documents", []))
                elif node == "rerank":
                    metrics["top_n_results"] = len(values.get("reranked_documents", []))
                elif node == "rewrite":
                    metrics["rewrite_rounds"] = values.get("rewrite_rounds", 0)
                elif node == "generate":
                    answer = values.get("answer", "")
                    citations = [item.model_dump() for item in values.get("citations", [])]
            # 逐条推送引用，再把回答按小段流式推给前端
            for citation in citations:
                yield sse("citation", citation)
            for index in range(0, len(answer), 12):
                yield sse("token", {"text": answer[index : index + 12]})
            # 持久化助手消息，记录总耗时日志，最后发送 done 结束事件
            session.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=answer,
                    citations=citations,
                )
            )
            await session.commit()
            metrics["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
            logger.info(json.dumps(metrics))
            yield sse("done", {"conversation_id": conversation.id, "trace_id": trace_id})
        except Exception:
            logger.exception("chat_failed trace_id=%s", trace_id)
            yield sse("error", {"message": "Unable to complete the answer", "trace_id": trace_id})

    # 以 SSE 流返回：禁用缓存与反向代理缓冲，保证逐字推送
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
