from __future__ import annotations

import time

import httpx
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.config import settings
from app.schemas import Principal

# JWKS 缓存：避免每次请求都去拉取签名公钥
_jwks: dict = {"keys": []}
_jwks_loaded_at = 0.0


# 加载（并缓存 1 小时）前端 Better Auth 暴露的 JWKS 公钥集合
async def _load_jwks(force: bool = False) -> dict:
    global _jwks, _jwks_loaded_at
    if not force and _jwks["keys"] and time.monotonic() - _jwks_loaded_at < 3600:
        return _jwks
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(settings.auth_jwks_url)
        response.raise_for_status()
        _jwks = response.json()
        _jwks_loaded_at = time.monotonic()
        return _jwks


# 验证 JWT：先按 kid 找公钥，再用 RS256 校验签名/签发方/受众/过期时间，最终返回用户身份
async def verify_token(token: str) -> Principal:
    header = jwt.get_unverified_header(token)
    keys = (await _load_jwks()).get("keys", [])
    key = next((candidate for candidate in keys if candidate.get("kid") == header.get("kid")), None)
    if key is None:
        # 缓存未命中则强制刷新一次再找（处理密钥轮换）
        keys = (await _load_jwks(force=True)).get("keys", [])
        key = next((candidate for candidate in keys if candidate.get("kid") == header.get("kid")), None)
    if key is None:
        raise JWTError("Unknown signing key")
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=settings.auth_jwt_issuer,
        audience=settings.auth_jwt_audience,
        options={"require_exp": True, "require_sub": True},
    )
    return Principal(user_id=claims["sub"], email=claims.get("email", ""))


# FastAPI 依赖：从 Authorization 头取 Bearer Token 并验证，返回 Principal（用户身份）
async def get_current_user(authorization: str | None = Header(default=None)) -> Principal:
    if settings.auth_disabled:
        return Principal(user_id=settings.demo_user_id, email="demo@example.com")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        return await verify_token(authorization.removeprefix("Bearer ").strip())
    except (JWTError, httpx.HTTPError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
