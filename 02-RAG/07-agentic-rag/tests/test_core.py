from __future__ import annotations

import base64
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from sqlalchemy.dialects import postgresql

import app.auth as auth_module
from app.agent.graph import build_graph
from app.auth import verify_token
from app.config import settings
from app.ingestion.parser import parse_document
from app.ingestion.splitter import split_elements
from app.providers.embeddings import LocalHashEmbeddings
from app.providers.llm import LLMProvider
from app.providers.reranker import LexicalReranker
from app.retrieval.retriever import build_retrieval_statement
from app.schemas import Principal, SearchResult
from app.main import app

pytestmark = pytest.mark.asyncio


class FakeRetriever:
    def __init__(self, results: list[SearchResult]):
        self.results = results
        self.calls = 0

    async def retrieve(self, query, principal, knowledge_base_id, top_k=20):
        self.calls += 1
        return self.results


class FakeLLM(LLMProvider):
    async def invoke(self, messages):
        return "rewritten query" if "REWRITE_QUERY" in messages[-1]["content"] else "Grounded answer"

    async def stream(self, messages):
        yield await self.invoke(messages)


def result(score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk_id="chunk-a",
        document_id="doc-a",
        filename="guide.pdf",
        content="LangGraph checkpoints persist graph state.",
        score=score,
        page=12,
    )


async def test_text_parser_and_splitter(monkeypatch):
    monkeypatch.setattr(settings, "chunk_size", 24)
    monkeypatch.setattr(settings, "chunk_overlap", 4)
    elements = await parse_document("# Intro\n\nAgentic RAG retrieves evidence. More details follow.".encode(), "guide.md")
    chunks = split_elements(elements, "guide.md")
    assert len(chunks) >= 2
    assert chunks[0].metadata["h1"] == "Intro"


async def test_local_embedding_is_deterministic():
    provider = LocalHashEmbeddings()
    assert await provider.embed_query("same text") == await provider.embed_query("same text")


async def test_permission_filter_is_inside_vector_query():
    statement = build_retrieval_statement(
        [0.0] * settings.embedding_dimensions,
        Principal(user_id="user-a"),
        "kb-b",
        20,
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "knowledge_bases.user_id" in sql
    assert "knowledge_bases.id" in sql
    assert "LIMIT" in sql


async def test_graph_returns_only_reranked_citations(monkeypatch):
    monkeypatch.setattr(settings, "relevance_threshold", 0.35)
    graph = build_graph(FakeRetriever([result()]), LexicalReranker(), FakeLLM())
    state = await graph.ainvoke(
        {
            "conversation_id": "c",
            "principal": Principal(user_id="user-a"),
            "knowledge_base_id": "kb-a",
            "question": "What are checkpoints?",
            "rewrite_rounds": 0,
        }
    )
    assert state["answer"] == "Grounded answer"
    assert [citation.chunk_id for citation in state["citations"]] == ["chunk-a"]


async def test_rewrite_stops_after_configured_limit(monkeypatch):
    monkeypatch.setattr(settings, "max_rewrite_rounds", 2)
    monkeypatch.setattr(settings, "relevance_threshold", 0.99)
    retriever = FakeRetriever([])
    graph = build_graph(retriever, LexicalReranker(), FakeLLM())
    state = await graph.ainvoke(
        {
            "conversation_id": "c",
            "principal": Principal(user_id="user-a"),
            "knowledge_base_id": "kb-a",
            "question": "Unknown topic",
            "rewrite_rounds": 0,
        }
    )
    assert state["rewrite_rounds"] == 2
    assert retriever.calls == 3
    assert state["answer"].startswith("知识库证据不足")
    assert state["citations"] == []


def _jwt_material(claims: dict) -> tuple[str, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    numbers = private_key.public_key().public_numbers()

    def encoded(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    public_jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": encoded(numbers.n),
        "e": encoded(numbers.e),
    }
    token = jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": "test-key"})
    return token, public_jwk


async def _stub_jwks(monkeypatch, key: dict) -> None:
    async def load_jwks(force: bool = False):
        return {"keys": [key]}

    monkeypatch.setattr(auth_module, "_load_jwks", load_jwks)


async def test_jwt_verification(monkeypatch):
    token, key = _jwt_material(
        {
            "sub": "user-a",
            "email": "a@example.com",
            "iss": settings.auth_jwt_issuer,
            "aud": settings.auth_jwt_audience,
            "exp": int(time.time()) + 60,
        }
    )
    await _stub_jwks(monkeypatch, key)
    assert (await verify_token(token)).user_id == "user-a"


@pytest.mark.parametrize(
    ("audience", "expires"),
    [("wrong-audience", 60), (None, -60)],
)
async def test_jwt_rejects_invalid_audience_or_expiry(monkeypatch, audience, expires):
    token, key = _jwt_material(
        {
            "sub": "user-a",
            "iss": settings.auth_jwt_issuer,
            "aud": audience or settings.auth_jwt_audience,
            "exp": int(time.time()) + expires,
        }
    )
    await _stub_jwks(monkeypatch, key)
    with pytest.raises(JWTError):
        await verify_token(token)


async def test_protected_api_rejects_anonymous_requests(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/knowledge-bases")
    assert response.status_code == 401


async def test_health_is_public():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.json() == {"status": "ok"}
