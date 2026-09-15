import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# FastAPI 应用入口：创建应用、挂 CORS、注册路由
app = FastAPI(title="Agentic RAG API", version="0.1.0")
# CORS：只允许 Next.js 前端(http://localhost:3000)跨域访问，且带凭据
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
