# -*- coding: utf-8 -*-
"""Knowledge Base & RAG Service Package.

Provides comprehensive knowledge base management with vector database integration
for semantic search and retrieval-augmented generation (RAG).

Modules:
- vector_db: Abstract vector database interface and implementations
- rag_service: Main RAG service for knowledge retrieval and prompt enhancement
- ingester: Document ingestion and processing for knowledge base
- retriever: Semantic search and retrieval functionality
- indexer: Background indexing and maintenance
"""

from .vector_db import VectorDB, SearchResult, VectorDBError
from .rag_service import RAGService
from .ingester import KnowledgeIngester
from .retriever import KnowledgeRetriever
from .indexer import KnowledgeIndexer

__all__ = [
    "VectorDB",
    "SearchResult", 
    "VectorDBError",
    "RAGService",
    "KnowledgeIngester",
    "KnowledgeRetriever",
    "KnowledgeIndexer",
]