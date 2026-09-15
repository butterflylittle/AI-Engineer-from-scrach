# Fieldnote — Agentic RAG Knowledge Base

一个可直接运行的个人 / 小团队知识库：上传 PDF、DOCX、Markdown 或 TXT，后台异步解析并写入 pgvector；显式 LangGraph 根据问题决定是否检索，在证据不足时最多改写查询两次，最后通过 SSE 返回答案和文件 / 页码引用。

## 运行

要求 Docker Desktop（Compose v2）。

```bash
cp .env.example .env
# 至少把 BETTER_AUTH_SECRET 改成 32 位以上随机值
docker compose up --build
```

打开 <http://localhost:3000>。API 文档位于 <http://localhost:8000/docs>，MinIO 控制台位于 <http://localhost:9001>。

未配置模型密钥时，项目自动使用确定性的本地 Hash Embedding、词法 Reranker 和本地回答器，方便验收完整链路；配置 OpenAI-compatible 环境变量后会自动切换到远端 Provider。这个本地 fallback 只适合开发，不代表语义检索质量。

## 组成

```text
Next.js 16 + Better Auth + TanStack Query
                  │ JWT / JWKS
                  ▼
FastAPI ── PostgreSQL 17 + pgvector
   │      └─ LangGraph: route → retrieve → rerank → grade ↔ rewrite → generate
   ├─ MinIO（原文件）
   └─ Redis → Celery（解析、切块、Embedding、入库）
```

检索 SQL 在向量排序与 `LIMIT` 之前连接 `knowledge_bases` 并过滤 `user_id`。前端传入的任何用户标识都不会被信任；身份只来自 Better Auth 签发、FastAPI 通过 JWKS 验证的 15 分钟 JWT。

## 配置认证

- 邮箱注册、验证、忘记密码：配置 `RESEND_API_KEY` 与 `EMAIL_FROM`。
- Google OAuth：配置 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`，回调地址为 `http://localhost:3000/api/auth/callback/google`。
- 本地调 API 可临时设置 `AUTH_DISABLED=true`；不要在共享或生产环境启用。

Better Auth 主会话继续使用 HttpOnly Cookie；JWT 只用于 Web → FastAPI。认证表和业务表都由 `services/api/migrations` 下的 Alembic migration 创建。

## 常用命令

```bash
make up       # 构建并启动六个服务
make test     # 在 API 容器中运行核心测试
make logs     # 跟随 web / api / worker 日志
make down
```

测试覆盖解析与结构化切块、确定性 Embedding、SQL 权限过滤、LangGraph Citation 约束以及 Rewrite 上限。生产化前还应接入真实邮件域名、对象存储生命周期、API 限流持久化、Langfuse / OpenTelemetry，并补齐 OAuth 与数据库集成测试。
