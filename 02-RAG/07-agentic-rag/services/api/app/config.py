from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# 全局配置：从 .env 读取，未设置则用默认值
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 基础设施连接
    database_url: str = "postgresql+asyncpg://agentic_rag:agentic_rag@localhost:5432/agentic_rag"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "agentic-rag"

    # 认证：JWT 由前端 Better Auth 签发，这里通过 JWKS 验证
    auth_jwt_issuer: str = "http://localhost:3000"
    auth_jwt_audience: str = "http://localhost:3000"
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_disabled: bool = False
    demo_user_id: str = "demo-user"

    # 模型 Provider（配置后切换到远端，否则走本地 fallback）
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1024
    rerank_api_base: str = ""
    rerank_api_key: str = ""
    rerank_model: str = ""

    # 检索与切块参数
    retrieval_top_k: int = 20          # 向量检索召回条数
    rerank_top_n: int = 5              # 重排后保留条数
    relevance_threshold: float = 0.35  # grade 判断证据充分的相关性阈值
    chunk_size: int = 800              # 切块大小
    chunk_overlap: int = 120           # 切块重叠
    max_rewrite_rounds: int = 2        # 查询改写最大轮次


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
