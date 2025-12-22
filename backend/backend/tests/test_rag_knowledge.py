# -*- coding: utf-8 -*-
"""Knowledge base + RAG tests.

The production knowledge base integrates with external embedding models and
vector databases. The test suite uses a deterministic in-memory VectorDB and
EmbeddingService to validate the orchestration logic without external services.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import KnowledgeItem, Workspace
from backend.db.models.enums import KnowledgeCategory, KnowledgeItemStatus, KnowledgeSourceType
from backend.services.knowledge.rag_service import RAGService, KnowledgeSearchRequest
from backend.services.knowledge.retriever import KnowledgeRetriever
from backend.services.knowledge.vector_db import SearchResult, VectorDBError


class FakeEmbeddingService:
    """Deterministic embedding stub.

    We purposely map a few keywords onto orthogonal axes so that "semantic" search
    can be verified.
    """

    async def embed_text(self, text: str, **_kwargs) -> List[float]:
        t = (text or "").lower()
        v = [0.0, 0.0, 0.0]
        if "jwt" in t or "auth" in t:
            v[0] += 1.0
        if "sql" in t or "injection" in t:
            v[1] += 1.0
        if "pytest" in t or "test" in t:
            v[2] += 1.0

        # Fallback: avoid zero vectors
        if v == [0.0, 0.0, 0.0]:
            v[0] = 0.1
        return v


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    # Map cosine from [-1, 1] -> [0, 1]
    return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1.0) / 2.0))


class InMemoryVectorDB:
    """Minimal in-memory VectorDB implementation for tests."""

    def __init__(self):
        self.provider = "in_memory"
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def store_embedding(
        self,
        text_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None,
    ) -> bool:
        collection = collection_name or "default"
        self._data.setdefault(collection, {})[text_id] = {
            "vector": embedding,
            "metadata": metadata,
        }
        return True

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        collection = collection_name or "default"
        results: List[SearchResult] = []
        for text_id, entry in self._data.get(collection, {}).items():
            md = entry["metadata"]
            if filter_metadata:
                matches = True
                for key, val in filter_metadata.items():
                    if key not in md:
                        matches = False
                        break
                    if md[key] != val:
                        matches = False
                        break
                if not matches:
                    continue

            score = _cosine_similarity(query_embedding, entry["vector"])
            results.append(SearchResult(id=text_id, score=score, metadata=md))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete(self, text_id: str, collection_name: Optional[str] = None) -> bool:
        collection = collection_name or "default"
        self._data.get(collection, {}).pop(text_id, None)
        return True

    async def update_metadata(self, text_id: str, metadata: Dict[str, Any], collection_name: Optional[str] = None) -> bool:
        collection = collection_name or "default"
        if text_id not in self._data.get(collection, {}):
            return False
        self._data[collection][text_id]["metadata"] = metadata
        return True

    async def get_embedding(self, text_id: str, collection_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        collection = collection_name or "default"
        return self._data.get(collection, {}).get(text_id)

    async def count(self, collection_name: Optional[str] = None) -> int:
        collection = collection_name or "default"
        return len(self._data.get(collection, {}))

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()


@pytest.fixture
async def workspace(db_session: AsyncSession) -> Workspace:
    ws = Workspace(name="KB Test", slug=f"kb-test-{uuid4()}", meta_data={})
    db_session.add(ws)
    await db_session.flush()
    return ws


async def _create_knowledge_item(
    session: AsyncSession,
    *,
    workspace_id: str,
    title: str,
    content: str,
    category: KnowledgeCategory,
    language: Optional[str],
    tags: Optional[list[str]] = None,
    relevance_score: float = 0.0,
    embedding_id: Optional[str] = None,
) -> KnowledgeItem:
    item = KnowledgeItem(
        workspace_id=workspace_id,
        category=category,
        title=title,
        content=content,
        language=language,
        tags=tags or [],
        source=KnowledgeSourceType.DOCUMENTATION,
        status=KnowledgeItemStatus.ACTIVE,
        relevance_score=relevance_score,
        usage_count=0,
        embedding_id=embedding_id,
    )
    session.add(item)
    await session.flush()
    return item


class TestKnowledgeRetriever:
    @pytest.mark.asyncio
    async def test_semantic_search_returns_relevant_results_with_filters(self, db_session: AsyncSession, workspace: Workspace):
        vector_db = InMemoryVectorDB()
        await vector_db.initialize()

        retriever = KnowledgeRetriever(db_session, vector_db)
        retriever.embedding_service = FakeEmbeddingService()

        jwt_embedding_id = f"emb-{uuid4()}"
        sql_embedding_id = f"emb-{uuid4()}"

        jwt_item = await _create_knowledge_item(
            db_session,
            workspace_id=workspace.id,
            title="FastAPI JWT authentication",
            content="Use PyJWT and a dependency to validate tokens.",
            category=KnowledgeCategory.BEST_PRACTICE,
            language="python",
            tags=["fastapi", "jwt"],
            relevance_score=0.9,
            embedding_id=jwt_embedding_id,
        )
        sql_item = await _create_knowledge_item(
            db_session,
            workspace_id=workspace.id,
            title="Prevent SQL injection",
            content="Always use parameterized queries.",
            category=KnowledgeCategory.SECURITY_GUIDELINE,
            language="python",
            tags=["sql"],
            relevance_score=0.1,
            embedding_id=sql_embedding_id,
        )

        await vector_db.store_embedding(
            jwt_embedding_id,
            await retriever.embedding_service.embed_text(jwt_item.content),
            {"category": jwt_item.category.value, "language": jwt_item.language},
            collection_name=f"knowledge_{workspace.id}",
        )
        await vector_db.store_embedding(
            sql_embedding_id,
            await retriever.embedding_service.embed_text(sql_item.content),
            {"category": sql_item.category.value, "language": sql_item.language},
            collection_name=f"knowledge_{workspace.id}",
        )

        req = KnowledgeSearchRequest(
            query="jwt auth",
            workspace_id=workspace.id,
            top_k=5,
            category_filter=KnowledgeCategory.BEST_PRACTICE,
            language_filter="python",
        )
        result = await retriever.search_knowledge(req)

        assert result.total_count == 1
        assert result.items[0].id == jwt_item.id
        assert result.items[0].category == KnowledgeCategory.BEST_PRACTICE

    @pytest.mark.asyncio
    async def test_search_gracefully_degrades_to_text_search_when_vector_db_fails(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        vector_db = InMemoryVectorDB()
        await vector_db.initialize()

        retriever = KnowledgeRetriever(db_session, vector_db)

        # Force vector DB failure
        async def _raise(*_args, **_kwargs):
            raise VectorDBError("vector db down")

        vector_db.search = _raise  # type: ignore[assignment]

        item = await _create_knowledge_item(
            db_session,
            workspace_id=workspace.id,
            title="Pytest basics",
            content="Use pytest fixtures and parametrize for concise tests.",
            category=KnowledgeCategory.BEST_PRACTICE,
            language="python",
            tags=["pytest"],
            relevance_score=0.0,
            embedding_id=None,
        )

        req = KnowledgeSearchRequest(query="pytest fixtures", workspace_id=workspace.id, top_k=3)
        result = await retriever.search_knowledge(req)

        assert result.total_count == 1
        assert result.items[0].id == item.id
        assert result.metadata.get("search_type") == "text_fallback"


class TestRAGService:
    @pytest.mark.asyncio
    async def test_enhance_prompt_includes_retrieved_examples(self, db_session: AsyncSession, workspace: Workspace):
        vector_db = InMemoryVectorDB()
        await vector_db.initialize()

        rag = RAGService(db_session=db_session, vector_db=vector_db, embedding_service=FakeEmbeddingService())
        rag.retriever.embedding_service = FakeEmbeddingService()

        jwt_embedding_id = f"emb-{uuid4()}"
        jwt_item = await _create_knowledge_item(
            db_session,
            workspace_id=workspace.id,
            title="JWT middleware pattern",
            content="Create a dependency that validates Authorization: Bearer <token>.",
            category=KnowledgeCategory.CODE_PATTERN,
            language="python",
            tags=["jwt", "fastapi"],
            relevance_score=0.8,
            embedding_id=jwt_embedding_id,
        )

        await vector_db.store_embedding(
            jwt_embedding_id,
            await rag.retriever.embedding_service.embed_text(jwt_item.content),
            {"category": jwt_item.category.value, "language": jwt_item.language},
            collection_name=f"knowledge_{workspace.id}",
        )

        enhanced = await rag.enhance_prompt(
            base_prompt="Write a FastAPI dependency for auth.",
            query="jwt auth fastapi",
            workspace_id=workspace.id,
            num_examples=1,
        )

        assert enhanced.original_prompt.startswith("Write a FastAPI")
        assert "Relevant Knowledge Examples" in enhanced.enhanced_prompt
        assert jwt_item.title in enhanced.enhanced_prompt
        assert len(enhanced.retrieved_items) == 1

        # Ensure we don't bloat the prompt drastically for a single small item.
        assert len(enhanced.enhanced_prompt) < 5000

    @pytest.mark.asyncio
    async def test_enhance_prompt_returns_original_prompt_on_failure(self, db_session: AsyncSession, workspace: Workspace):
        vector_db = InMemoryVectorDB()
        await vector_db.initialize()

        rag = RAGService(db_session=db_session, vector_db=vector_db, embedding_service=FakeEmbeddingService())

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("kb unavailable")

        rag.retriever.search_knowledge = _boom  # type: ignore[assignment]

        enhanced = await rag.enhance_prompt(
            base_prompt="Base prompt",
            query="anything",
            workspace_id=workspace.id,
            num_examples=2,
        )

        assert enhanced.enhanced_prompt == "Base prompt"
        assert enhanced.search_metadata.get("error")

    @pytest.mark.asyncio
    async def test_track_usage_updates_usage_count_and_relevance(self, db_session: AsyncSession, workspace: Workspace):
        vector_db = InMemoryVectorDB()
        await vector_db.initialize()

        rag = RAGService(db_session=db_session, vector_db=vector_db, embedding_service=FakeEmbeddingService())

        item = await _create_knowledge_item(
            db_session,
            workspace_id=workspace.id,
            title="Secure headers",
            content="Set security headers like CSP.",
            category=KnowledgeCategory.SECURITY_GUIDELINE,
            language="python",
            tags=["security"],
            relevance_score=0.0,
            embedding_id=None,
        )

        await rag.track_usage(item.id, usage_type="reference")
        await db_session.refresh(item)

        assert item.usage_count == 1
        assert item.relevance_score == pytest.approx(0.1)
