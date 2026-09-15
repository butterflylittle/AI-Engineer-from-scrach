from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, KnowledgeBase
from app.providers import EmbeddingProvider
from app.schemas import Principal, SearchResult


# 构造向量检索 SQL：按余弦距离排序取 top_k，并强制过滤到当前用户的知识库。
def build_retrieval_statement(
    query_vector: list[float], principal: Principal, knowledge_base_id: str, top_k: int
) -> Select:
    distance = Chunk.embedding.cosine_distance(query_vector)
    return (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Document.filename,
            Chunk.content,
            (1 - distance).label("score"),          # 距离转相似度分数（越近越高）
            Chunk.page_number.label("page"),
            Chunk.chunk_metadata.label("metadata"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .join(KnowledgeBase, KnowledgeBase.id == Chunk.knowledge_base_id)
        .where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == principal.user_id,   # 权限过滤：只看本人知识库
            Document.status == "ready",                    # 只看已入库完成的文档
        )
        .order_by(distance)
        .limit(top_k)
    )


class PgVectorRetriever:
    def __init__(self, session: AsyncSession, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.embeddings = embeddings

    # 检索主流程：查询向量化 → 执行相似度 SQL → 转成 SearchResult 列表
    async def retrieve(
        self,
        query: str,
        principal: Principal,
        knowledge_base_id: str,
        top_k: int = 20,
    ) -> list[SearchResult]:
        vector = await self.embeddings.embed_query(query)
        rows = (
            await self.session.execute(
                build_retrieval_statement(vector, principal, knowledge_base_id, top_k)
            )
        ).mappings()
        return [SearchResult.model_validate(dict(row)) for row in rows]
