# -*- coding: utf-8 -*-
"""Knowledge Base Service Factory.

Provides factory functions for creating and initializing knowledge base services
with proper dependency injection and configuration.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models.enums import VectorDBProvider, EmbeddingModel
from .vector_db import VectorDB, create_vector_db
from .rag_service import RAGService, EmbeddingService
from .retriever import KnowledgeRetriever
from .ingester import KnowledgeIngester
from .indexer import KnowledgeIndexer

logger = logging.getLogger(__name__)


class KnowledgeBaseServiceFactory:
    """Factory for creating knowledge base services."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize factory.
        
        Args:
            db_session: Database session
        """
        self.db_session = db_session
        self._vector_db: Optional[VectorDB] = None
        self._embedding_service: Optional[EmbeddingService] = None
        self._rag_service: Optional[RAGService] = None
    
    async def get_vector_db(self) -> VectorDB:
        """Get or create vector database instance.
        
        Returns:
            Vector database instance
        """
        if not self._vector_db:
            self._vector_db = await self._create_vector_db()
        return self._vector_db
    
    async def get_embedding_service(self) -> EmbeddingService:
        """Get or create embedding service instance.
        
        Returns:
            Embedding service instance
        """
        if not self._embedding_service:
            model = EmbeddingModel(settings.embedding_model)
            self._embedding_service = EmbeddingService(default_model=model)
        return self._embedding_service
    
    async def get_rag_service(self) -> RAGService:
        """Get or create RAG service instance.
        
        Returns:
            RAG service instance
        """
        if not self._rag_service:
            vector_db = await self.get_vector_db()
            embedding_service = await self.get_embedding_service()
            self._rag_service = RAGService(
                db_session=self.db_session,
                vector_db=vector_db,
                embedding_service=embedding_service
            )
        return self._rag_service
    
    async def get_knowledge_retriever(self) -> KnowledgeRetriever:
        """Get knowledge retriever service.
        
        Returns:
            Knowledge retriever service
        """
        vector_db = await self.get_vector_db()
        return KnowledgeRetriever(self.db_session, vector_db)
    
    async def get_knowledge_ingester(self) -> KnowledgeIngester:
        """Get knowledge ingester service.
        
        Returns:
            Knowledge ingester service
        """
        vector_db = await self.get_vector_db()
        embedding_service = await self.get_embedding_service()
        return KnowledgeIngester(
            db_session=self.db_session,
            vector_db=vector_db,
            embedding_service=embedding_service
        )
    
    async def get_knowledge_indexer(self) -> KnowledgeIndexer:
        """Get knowledge indexer service.
        
        Returns:
            Knowledge indexer service
        """
        vector_db = await self.get_vector_db()
        embedding_service = await self.get_embedding_service()
        return KnowledgeIndexer(
            db_session=self.db_session,
            vector_db=vector_db,
            embedding_service=embedding_service
        )
    
    async def _create_vector_db(self) -> VectorDB:
        """Create vector database instance based on configuration.
        
        Returns:
            Vector database instance
        """
        if not settings.vector_db_enabled:
            raise RuntimeError("Vector database is disabled in configuration")
        
        provider = VectorDBProvider(settings.vector_db_provider)
        config = self._get_vector_db_config(provider)
        
        logger.info(f"Creating vector database: {provider.value}")
        vector_db = create_vector_db(provider, config)
        await vector_db.initialize()
        
        return vector_db
    
    def _get_vector_db_config(self, provider: VectorDBProvider) -> Dict[str, Any]:
        """Get configuration for vector database provider.
        
        Args:
            provider: Vector database provider
            
        Returns:
            Configuration dictionary
        """
        if provider == VectorDBProvider.PINECONE:
            return {
                'api_key': settings.pinecone_api_key,
                'environment': settings.pinecone_environment,
                'index_name': settings.pinecone_index_name,
                'collection_prefix': 'knowledge'
            }
        
        elif provider == VectorDBProvider.WEAVIATE:
            return {
                'url': settings.weaviate_url,
                'username': settings.weaviate_username,
                'password': settings.weaviate_password,
                'class_name': settings.weaviate_class_name,
                'headers': {}
            }
        
        elif provider == VectorDBProvider.CHROMA:
            return {
                'path': settings.chromadb_path,
                'collection_name': settings.chromadb_collection_name,
                'collection_prefix': 'knowledge'
            }
        
        elif provider == VectorDBProvider.MILVUS:
            return {
                'host': settings.milvus_host,
                'port': settings.milvus_port,
                'collection_name': settings.milvus_collection_name,
                'collection_prefix': 'knowledge'
            }
        
        elif provider == VectorDBProvider.QDRANT:
            return {
                'host': settings.qdrant_host,
                'port': settings.qdrant_port,
                'collection_name': settings.qdrant_collection_name,
                'collection_prefix': 'knowledge'
            }
        
        else:
            raise ValueError(f"Unsupported vector database provider: {provider}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all knowledge base services.
        
        Returns:
            Health check results
        """
        health_status = {
            'overall': 'healthy',
            'timestamp': settings.get_current_time().isoformat(),
            'services': {}
        }
        
        try:
            # Check vector database
            vector_db = await self.get_vector_db()
            vector_healthy = await vector_db.health_check()
            health_status['services']['vector_db'] = {
                'status': 'healthy' if vector_healthy else 'unhealthy',
                'provider': vector_db.provider.value
            }
            
            if not vector_healthy:
                health_status['overall'] = 'degraded'
            
            # Check embedding service (basic check)
            embedding_service = await self.get_embedding_service()
            health_status['services']['embedding'] = {
                'status': 'healthy',
                'model': embedding_service.default_model.value
            }
            
            # Check database connection
            try:
                from sqlalchemy import text
                await self.db_session.execute(text("SELECT 1"))
                health_status['services']['database'] = {
                    'status': 'healthy',
                    'provider': 'postgresql'
                }
            except Exception as e:
                health_status['services']['database'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['overall'] = 'unhealthy'
            
        except Exception as e:
            health_status['overall'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status
    
    async def close(self) -> None:
        """Close all service connections."""
        try:
            if self._vector_db:
                await self._vector_db.close()
            
            if self.db_session:
                await self.db_session.close()
                
            logger.info("Knowledge base services closed")
            
        except Exception as e:
            logger.error(f"Error closing knowledge base services: {e}")


# Global factory instances (one per database session)
_factories: Dict[str, KnowledgeBaseServiceFactory] = {}


async def get_knowledge_base_factory(db_session: AsyncSession) -> KnowledgeBaseServiceFactory:
    """Get or create knowledge base service factory for a database session.
    
    Args:
        db_session: Database session
        
    Returns:
        Knowledge base service factory
    """
    session_id = id(db_session)
    
    if session_id not in _factories:
        _factories[session_id] = KnowledgeBaseServiceFactory(db_session)
    
    return _factories[session_id]


async def create_knowledge_base_services(db_session: AsyncSession) -> Dict[str, Any]:
    """Create all knowledge base services for a database session.
    
    Args:
        db_session: Database session
        
    Returns:
        Dictionary of service instances
    """
    factory = await get_knowledge_base_factory(db_session)
    
    services = {
        'factory': factory,
        'rag_service': await factory.get_rag_service(),
        'retriever': await factory.get_knowledge_retriever(),
        'ingester': await factory.get_knowledge_ingester(),
        'indexer': await factory.get_knowledge_indexer(),
        'vector_db': await factory.get_vector_db(),
        'embedding_service': await factory.get_embedding_service()
    }
    
    return services


async def cleanup_knowledge_base_services(db_session: AsyncSession) -> None:
    """Cleanup knowledge base services for a database session.
    
    Args:
        db_session: Database session
    """
    session_id = id(db_session)
    
    if session_id in _factories:
        await _factories[session_id].close()
        del _factories[session_id]