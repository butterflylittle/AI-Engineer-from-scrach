from typing import TypedDict

from app.schemas import Citation, Principal, SearchResult


# LangGraph 共享状态：节点间通过它传递数据。
# total=False 表示字段可选，节点只返回需要更新的字段即可。
class RagState(TypedDict, total=False):
    conversation_id: str                        # 当前会话 ID
    principal: Principal                        # 认证后的用户身份（user_id / email）
    knowledge_base_id: str                      # 目标知识库 ID
    question: str                               # 用户原始问题
    rewritten_query: str | None                 # rewrite 节点改写后的查询
    retrieved_documents: list[SearchResult]     # 向量检索 top-k 候选
    reranked_documents: list[SearchResult]      # 重排后的 top-n 结果
    rewrite_rounds: int                         # 已改写的轮次
    requires_retrieval: bool                    # route 判断：是否需要检索
    evidence_sufficient: bool                   # grade 判断：证据是否充分
    answer: str | None                          # generate 生成的回答
    citations: list[Citation]                   # 回答引用的文档/页码
