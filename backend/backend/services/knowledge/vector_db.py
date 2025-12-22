# -*- coding: utf-8 -*-
"""Vector Database Interface and Implementations.

Provides abstract interface and implementations for various vector databases
including Pinecone, Weaviate, Milvus, Qdrant, and others.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
import hashlib
import asyncio

from backend.db.models.enums import VectorDBProvider, EmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector database search."""
    
    id: str
    score: float
    metadata: Dict[str, Any]
    vector: Optional[List[float]] = None
    text: Optional[str] = None
    
    def __post_init__(self):
        """Validate search result."""
        if not self.id:
            raise ValueError("Search result must have an id")
        if not 0 <= self.score <= 1:
            raise ValueError(f"Invalid similarity score: {self.score}. Must be between 0 and 1")


class VectorDBError(Exception):
    """Base exception for vector database operations."""
    pass


class ConfigurationError(VectorDBError):
    """Raised when vector database configuration is invalid."""
    pass


class ConnectionError(VectorDBError):
    """Raised when vector database connection fails."""
    pass


class VectorDB(ABC):
    """Abstract base class for vector database operations."""
    
    def __init__(self, provider: VectorDBProvider, config: Dict[str, Any]):
        """Initialize vector database.
        
        Args:
            provider: Vector database provider
            config: Configuration dictionary
        """
        self.provider = provider
        self.config = config
        self._initialized = False
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector database connection."""
        pass
    
    @abstractmethod
    async def store_embedding(
        self,
        text_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Store an embedding in the vector database.
        
        Args:
            text_id: Unique identifier for the text/embedding
            embedding: Vector embedding
            metadata: Associated metadata
            collection_name: Optional collection/namespace name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar embeddings.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            collection_name: Optional collection/namespace name
            filter_metadata: Optional metadata filters
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    async def delete(self, text_id: str, collection_name: Optional[str] = None) -> bool:
        """Delete an embedding from the vector database.
        
        Args:
            text_id: ID of the embedding to delete
            collection_name: Optional collection/namespace name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_metadata(
        self,
        text_id: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Update metadata for an existing embedding.
        
        Args:
            text_id: ID of the embedding to update
            metadata: New metadata
            collection_name: Optional collection/namespace name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_embedding(
        self,
        text_id: str,
        collection_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve an embedding by ID.
        
        Args:
            text_id: ID of the embedding to retrieve
            collection_name: Optional collection/namespace name
            
        Returns:
            Embedding data or None if not found
        """
        pass
    
    @abstractmethod
    async def count(self, collection_name: Optional[str] = None) -> int:
        """Count embeddings in the database.
        
        Args:
            collection_name: Optional collection/namespace name
            
        Returns:
            Number of embeddings
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the vector database is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the vector database connection."""
        pass
    
    def _generate_embedding_id(self, text: str, workspace_id: str) -> str:
        """Generate a unique embedding ID.
        
        Args:
            text: Text content
            workspace_id: Workspace ID
            
        Returns:
            Unique embedding ID
        """
        content = f"{workspace_id}:{text}"
        hash_obj = hashlib.sha256(content.encode())
        return f"{self.provider.value}:{hash_obj.hexdigest()}"
    
    def _get_collection_name(self, workspace_id: str) -> str:
        """Get collection name for workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Collection name
        """
        return self.config.get('collection_prefix', 'knowledge') + '_' + workspace_id


class PineconeVectorDB(VectorDB):
    """Pinecone vector database implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(VectorDBProvider.PINECONE, config)
        self.client = None
        
    async def initialize(self) -> None:
        """Initialize Pinecone connection."""
        try:
            import pinecone
            pinecone.init(
                api_key=self.config.get('api_key'),
                environment=self.config.get('environment', 'us-west1-gcp')
            )
            
            # Test connection
            pinecone.whoami()
            self._initialized = True
            logger.info(f"Initialized Pinecone connection to {self.config.get('environment', 'us-west1-gcp')}")
            
        except ImportError:
            raise ConfigurationError("pinecone-client not installed. Run: pip install pinecone-client")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Pinecone: {e}")
    
    async def store_embedding(
        self,
        text_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Store embedding in Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            # Prepare vectors for upsert
            vectors = [{
                'id': text_id,
                'values': embedding,
                'metadata': metadata
            }]
            
            pinecone_index.upsert(vectors=vectors)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store embedding in Pinecone: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search in Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            query_params = {
                'vector': query_embedding,
                'topK': top_k,
                'includeMetadata': True
            }
            
            if filter_metadata:
                query_params['filter'] = filter_metadata
                
            response = pinecone_index.query(**query_params)
            
            results = []
            for match in response.matches:
                results.append(SearchResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata or {}
                ))
                
            return results
            
        except Exception as e:
            logger.error(f"Search failed in Pinecone: {e}")
            return []
    
    async def delete(self, text_id: str, collection_name: Optional[str] = None) -> bool:
        """Delete from Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            pinecone_index.delete(ids=[text_id])
            return True
            
        except Exception as e:
            logger.error(f"Delete failed in Pinecone: {e}")
            return False
    
    async def update_metadata(
        self,
        text_id: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Update metadata in Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            # Pinecone doesn't support direct metadata updates,
            # so we need to update the full vector
            vector_data = await self.get_embedding(text_id, collection_name)
            if not vector_data:
                return False
                
            vectors = [{
                'id': text_id,
                'values': vector_data['vector'],
                'metadata': metadata
            }]
            
            pinecone_index.upsert(vectors=vectors)
            return True
            
        except Exception as e:
            logger.error(f"Update metadata failed in Pinecone: {e}")
            return False
    
    async def get_embedding(
        self,
        text_id: str,
        collection_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get embedding from Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            response = pinecone_index.fetch(ids=[text_id])
            
            if text_id in response.vectors:
                vector_data = response.vectors[text_id]
                return {
                    'id': vector_data.id,
                    'vector': vector_data.values,
                    'metadata': vector_data.metadata
                }
            return None
            
        except Exception as e:
            logger.error(f"Get embedding failed in Pinecone: {e}")
            return None
    
    async def count(self, collection_name: Optional[str] = None) -> int:
        """Count embeddings in Pinecone."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            index_name = collection_name or self.config.get('index_name', 'knowledge-base')
            pinecone_index = pinecone.Index(index_name)
            
            response = pinecone_index.describe_index_stats()
            return response.total_vector_count
            
        except Exception as e:
            logger.error(f"Count failed in Pinecone: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Pinecone health."""
        try:
            import pinecone
            
            if not self._initialized:
                await self.initialize()
                
            pinecone.whoami()
            return True
            
        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Pinecone connection."""
        # Pinecone doesn't require explicit connection closing
        logger.info("Pinecone connection closed")


class WeaviateVectorDB(VectorDB):
    """Weaviate vector database implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(VectorDBProvider.WEAVIATE, config)
        self.client = None
        
    async def initialize(self) -> None:
        """Initialize Weaviate connection."""
        try:
            import weaviate
            
            self.client = weaviate.Client(
                url=self.config.get('url'),
                auth_client_secret=weaviate.AuthClientPassword(
                    self.config.get('username'),
                    self.config.get('password')
                ) if self.config.get('username') and self.config.get('password') else None,
                additional_headers=self.config.get('headers', {})
            )
            
            # Test connection
            if self.client.is_ready():
                self._initialized = True
                logger.info("Initialized Weaviate connection")
            else:
                raise ConnectionError("Weaviate client not ready")
                
        except ImportError:
            raise ConfigurationError("weaviate-client not installed. Run: pip install weaviate-client")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Weaviate: {e}")
    
    async def store_embedding(
        self,
        text_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Store embedding in Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            # Create schema if it doesn't exist
            await self._ensure_schema(class_name)
            
            # Add object
            data_object = {
                'text_id': text_id,
                'vector': embedding,
                'metadata': metadata
            }
            
            # Add text and metadata fields
            data_object.update(metadata)
            
            result = self.client.data_object.create(
                data_object=data_object,
                class_name=class_name
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to store embedding in Weaviate: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search in Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            query = (
                self.client.query
                .get(class_name, ['text_id', 'metadata'])
                .with_near_vector({'vector': query_embedding})
                .with_limit(top_k)
            )
            
            # Add filters if provided
            if filter_metadata:
                where_filter = self._build_where_filter(filter_metadata)
                query = query.with_where(where_filter)
            
            response = query.do()
            
            results = []
            if 'data' in response and 'Get' in response['data']:
                for item in response['data']['Get'][class_name]:
                    results.append(SearchResult(
                        id=item['text_id'],
                        score=1.0,  # Weaviate doesn't provide similarity scores directly
                        metadata=item.get('metadata', {})
                    ))
                    
            return results
            
        except Exception as e:
            logger.error(f"Search failed in Weaviate: {e}")
            return []
    
    async def delete(self, text_id: str, collection_name: Optional[str] = None) -> bool:
        """Delete from Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            result = self.client.data_object.delete(
                text_id,
                class_name=class_name
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Delete failed in Weaviate: {e}")
            return False
    
    async def update_metadata(
        self,
        text_id: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Update metadata in Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            # Get current object
            current = self.client.data_object.get_by_id(
                text_id,
                class_name=class_name
            )
            
            if not current:
                return False
            
            # Merge with new metadata
            new_properties = {**current['properties'], **metadata}
            
            result = self.client.data_object.update(
                data_object={
                    'text_id': text_id,
                    'properties': new_properties
                },
                class_name=class_name
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Update metadata failed in Weaviate: {e}")
            return False
    
    async def get_embedding(
        self,
        text_id: str,
        collection_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get embedding from Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            response = self.client.data_object.get_by_id(
                text_id,
                class_name=class_name
            )
            
            if response:
                return {
                    'id': response['id'],
                    'vector': response.get('vector'),
                    'metadata': response['properties']
                }
            return None
            
        except Exception as e:
            logger.error(f"Get embedding failed in Weaviate: {e}")
            return None
    
    async def count(self, collection_name: Optional[str] = None) -> int:
        """Count embeddings in Weaviate."""
        try:
            if not self._initialized:
                await self.initialize()
                
            class_name = (collection_name or self.config.get('class_name', 'KnowledgeItem')).capitalize()
            
            query = self.client.query.aggregate(class_name).with_meta_count()
            response = query.do()
            
            if 'data' in response and 'Aggregate' in response['data']:
                return response['data']['Aggregate'][class_name][0]['meta']['count']
            return 0
            
        except Exception as e:
            logger.error(f"Count failed in Weaviate: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Weaviate health."""
        try:
            if not self._initialized:
                await self.initialize()
                
            return self.client.is_ready()
            
        except Exception as e:
            logger.error(f"Weaviate health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Weaviate connection."""
        # Weaviate client doesn't require explicit closing
        logger.info("Weaviate connection closed")
    
    async def _ensure_schema(self, class_name: str) -> None:
        """Ensure schema exists for the class."""
        try:
            if not self.client.schema.get_class(class_name):
                # Create basic schema
                schema = {
                    'classes': [{
                        'class': class_name,
                        'vectorizer': 'none',  # We handle vectors manually
                        'properties': [
                            {
                                'name': 'text_id',
                                'dataType': ['string']
                            },
                            {
                                'name': 'metadata',
                                'dataType': ['object']
                            }
                        ]
                    }]
                }
                self.client.schema.create(schema)
        except Exception as e:
            logger.error(f"Failed to ensure schema: {e}")
    
    def _build_where_filter(self, filter_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build Weaviate where filter from metadata."""
        if not filter_metadata:
            return {}
            
        # Simple equality filter
        if len(filter_metadata) == 1:
            key, value = next(iter(filter_metadata.items()))
            return {
                'path': [key],
                'operator': 'Equal',
                'valueString': str(value)
            }
        
        # For multiple filters, use AND operator
        conditions = []
        for key, value in filter_metadata.items():
            conditions.append({
                'path': [key],
                'operator': 'Equal',
                'valueString': str(value)
            })
        
        return {
            'operator': 'And',
            'operands': conditions
        }


class ChromaVectorDB(VectorDB):
    """Chroma vector database implementation (local)."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(VectorDBProvider.CHROMA, config)
        self.client = None
        self.db = None
        
    async def initialize(self) -> None:
        """Initialize Chroma connection."""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Initialize client
            self.client = chromadb.PersistentClient(
                path=self.config.get('path', './chromadb')
            )
            
            # Create collection
            collection_name = self.config.get('collection_name', 'knowledge_items')
            self.db = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            self._initialized = True
            logger.info(f"Initialized Chroma DB at {self.config.get('path', './chromadb')}")
            
        except ImportError:
            raise ConfigurationError("chromadb not installed. Run: pip install chromadb")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Chroma: {e}")
    
    async def store_embedding(
        self,
        text_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Store embedding in Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            collection = self.db
            
            collection.add(
                ids=[text_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store embedding in Chroma: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search in Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            collection = self.db
            
            # Query with metadata filter if provided
            query_params = {
                'query_embeddings': [query_embedding],
                'n_results': top_k,
                'include': ['metadatas', 'distances']
            }
            
            if filter_metadata:
                # Chroma uses where clause for filtering
                query_params['where'] = filter_metadata
            
            results = collection.query(**query_params)
            
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    # Convert distance to similarity score (Chroma uses distance)
                    distance = results['distances'][0][i]
                    score = max(0, 1 - distance)  # Convert distance to similarity
                    
                    search_results.append(SearchResult(
                        id=doc_id,
                        score=score,
                        metadata=results['metadatas'][0][i] if results['metadatas'] else {}
                    ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed in Chroma: {e}")
            return []
    
    async def delete(self, text_id: str, collection_name: Optional[str] = None) -> bool:
        """Delete from Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            self.db.delete(ids=[text_id])
            return True
            
        except Exception as e:
            logger.error(f"Delete failed in Chroma: {e}")
            return False
    
    async def update_metadata(
        self,
        text_id: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> bool:
        """Update metadata in Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Get existing embedding
            existing = self.db.get(
                ids=[text_id],
                include=['embeddings', 'metadatas']
            )
            
            if not existing['ids']:
                return False
            
            # Update with new metadata
            self.db.update(
                ids=[text_id],
                metadatas=[metadata],
                embeddings=existing['embeddings']
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Update metadata failed in Chroma: {e}")
            return False
    
    async def get_embedding(
        self,
        text_id: str,
        collection_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get embedding from Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            result = self.db.get(
                ids=[text_id],
                include=['embeddings', 'metadatas']
            )
            
            if result['ids'] and result['ids'][0]:
                return {
                    'id': result['ids'][0],
                    'vector': result['embeddings'][0] if result['embeddings'] else None,
                    'metadata': result['metadatas'][0] if result['metadatas'] else {}
                }
            return None
            
        except Exception as e:
            logger.error(f"Get embedding failed in Chroma: {e}")
            return None
    
    async def count(self, collection_name: Optional[str] = None) -> int:
        """Count embeddings in Chroma."""
        try:
            if not self._initialized:
                await self.initialize()
            
            return self.db.count()
            
        except Exception as e:
            logger.error(f"Count failed in Chroma: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Chroma health."""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Try to count to verify database is accessible
            self.db.count()
            return True
            
        except Exception as e:
            logger.error(f"Chroma health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Chroma connection."""
        # Chroma doesn't require explicit connection closing
        logger.info("Chroma connection closed")


def create_vector_db(provider: VectorDBProvider, config: Dict[str, Any]) -> VectorDB:
    """Create a vector database instance.
    
    Args:
        provider: Vector database provider
        config: Configuration dictionary
        
    Returns:
        VectorDB instance
    """
    implementations = {
        VectorDBProvider.PINECONE: PineconeVectorDB,
        VectorDBProvider.WEAVIATE: WeaviateVectorDB,
        VectorDBProvider.CHROMA: ChromaVectorDB,
        # TODO: Add implementations for Milvus, Qdrant, etc.
        VectorDBProvider.MILVUS: lambda cfg: _raise_not_implemented("Milvus"),
        VectorDBProvider.QDRANT: lambda cfg: _raise_not_implemented("Qdrant"),
        VectorDBProvider.ELASTICSEARCH: lambda cfg: _raise_not_implemented("Elasticsearch"),
        VectorDBProvider.PGVECTOR: lambda cfg: _raise_not_implemented("pgvector"),
    }
    
    if provider not in implementations:
        raise ConfigurationError(f"Unsupported vector database provider: {provider}")
    
    return implementations[provider](config)


def _raise_not_implemented(provider_name: str) -> VectorDB:
    """Helper to raise not implemented for unsupported providers."""
    raise ConfigurationError(f"{provider_name} vector database implementation not yet supported")