# -*- coding: utf-8 -*-
"""RAG (Retrieval-Augmented Generation) Service.

Provides semantic search and prompt enhancement for AI agents using
knowledge base items. Integrates with vector databases and embedding models.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import KnowledgeItem
from backend.db.models.enums import KnowledgeCategory, EmbeddingModel
from .vector_db import VectorDB, SearchResult, VectorDBError, create_vector_db
from .retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)


@dataclass
class EnhancedPrompt:
    """Enhanced prompt with retrieved knowledge."""
    
    original_prompt: str
    enhanced_prompt: str
    retrieved_items: List[Dict[str, Any]]
    search_metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate enhanced prompt."""
        if not self.original_prompt:
            raise ValueError("Original prompt cannot be empty")
        if not self.enhanced_prompt:
            raise ValueError("Enhanced prompt cannot be empty")


@dataclass 
class KnowledgeSearchRequest:
    """Request for knowledge search."""
    
    query: str
    workspace_id: str
    top_k: int = 5
    category_filter: Optional[KnowledgeCategory] = None
    language_filter: Optional[str] = None
    tags_filter: Optional[List[str]] = None
    min_relevance_score: float = 0.0
    include_metadata: bool = True


@dataclass
class KnowledgeSearchResult:
    """Result from knowledge search."""
    
    items: List[KnowledgeItem]
    total_count: int
    search_time_ms: float
    metadata: Dict[str, Any]


class EmbeddingService:
    """Service for generating embeddings using various models."""
    
    def __init__(self, default_model: EmbeddingModel = EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL):
        """Initialize embedding service.
        
        Args:
            default_model: Default embedding model to use
        """
        self.default_model = default_model
        self._initialized = False
        
    async def embed_text(
        self,
        text: str,
        model: Optional[EmbeddingModel] = None,
        **kwargs
    ) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            model: Embedding model to use (uses default if not specified)
            **kwargs: Additional model-specific parameters
            
        Returns:
            Embedding vector
        """
        model = model or self.default_model
        
        if model.value.startswith('openai'):
            return await self._embed_openai(text, model, **kwargs)
        elif model.value.startswith('anthropic'):
            return await self._embed_anthropic(text, model, **kwargs)
        elif model.value.startswith('huggingface'):
            return await self._embed_huggingface(text, model, **kwargs)
        elif model.value.startswith('sentence-transformers'):
            return await self._embed_sentence_transformers(text, model, **kwargs)
        elif model.value.startswith('local'):
            return await self._embed_local(text, model, **kwargs)
        else:
            raise ValueError(f"Unsupported embedding model: {model}")
    
    async def _embed_openai(
        self,
        text: str,
        model: EmbeddingModel,
        **kwargs
    ) -> List[float]:
        """Generate embedding using OpenAI models."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(
                api_key=kwargs.get('api_key')
            )
            
            response = await client.embeddings.create(
                model=model.value,
                input=text
            )
            
            return response.data[0].embedding
            
        except ImportError:
            raise RuntimeError("OpenAI client not installed. Run: pip install openai")
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise
    
    async def _embed_anthropic(
        self,
        text: str,
        model: EmbeddingModel,
        **kwargs
    ) -> List[float]:
        """Generate embedding using Anthropic models."""
        try:
            # Anthropic doesn't currently offer embedding models
            # This is a placeholder for future implementation
            raise NotImplementedError("Anthropic embedding models not yet available")
            
        except Exception as e:
            logger.error(f"Anthropic embedding failed: {e}")
            raise
    
    async def _embed_huggingface(
        self,
        text: str,
        model: EmbeddingModel,
        **kwargs
    ) -> List[float]:
        """Generate embedding using Hugging Face models."""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Load model cache
            model_cache = kwargs.get('model_cache', {})
            model_name = model.value.replace('huggingface-', '')
            
            if model_name not in model_cache:
                model_cache[model_name] = SentenceTransformer(model_name)
                kwargs['model_cache'] = model_cache  # Update cache
            
            embedding = model_cache[model_name].encode(text)
            return embedding.tolist()
            
        except ImportError:
            raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"Hugging Face embedding failed: {e}")
            raise
    
    async def _embed_sentence_transformers(
        self,
        text: str,
        model: EmbeddingModel,
        **kwargs
    ) -> List[float]:
        """Generate embedding using Sentence Transformers."""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Load model cache
            model_cache = kwargs.get('model_cache', {})
            model_name = model.value.replace('sentence-transformers-', '')
            
            if model_name not in model_cache:
                model_cache[model_name] = SentenceTransformer(model_name)
                kwargs['model_cache'] = model_cache  # Update cache
            
            embedding = model_cache[model_name].encode(text)
            return embedding.tolist()
            
        except ImportError:
            raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"Sentence Transformers embedding failed: {e}")
            raise
    
    async def _embed_local(
        self,
        text: str,
        model: EmbeddingModel,
        **kwargs
    ) -> List[float]:
        """Generate embedding using local models."""
        try:
            # Use a local sentence transformer model
            return await self._embed_sentence_transformers(text, model, **kwargs)
            
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            raise


class RAGService:
    """Main RAG service for knowledge retrieval and prompt enhancement."""
    
    def __init__(
        self,
        db_session: AsyncSession,
        vector_db: VectorDB,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """Initialize RAG service.
        
        Args:
            db_session: Database session
            vector_db: Vector database instance
            embedding_service: Embedding service (creates default if not provided)
        """
        self.db_session = db_session
        self.vector_db = vector_db
        self.embedding_service = embedding_service or EmbeddingService()
        self.retriever = KnowledgeRetriever(db_session, vector_db)
        
        logger.info("RAG Service initialized")
    
    async def enhance_prompt(
        self,
        base_prompt: str,
        query: str,
        workspace_id: str,
        num_examples: int = 3,
        category_filter: Optional[KnowledgeCategory] = None,
        language_filter: Optional[str] = None,
        **kwargs
    ) -> EnhancedPrompt:
        """Enhance prompt with relevant knowledge.
        
        Args:
            base_prompt: Original prompt to enhance
            query: Search query for finding relevant knowledge
            workspace_id: Workspace ID
            num_examples: Number of knowledge examples to include
            category_filter: Filter by knowledge category
            language_filter: Filter by programming language
            **kwargs: Additional search parameters
            
        Returns:
            Enhanced prompt with knowledge examples
        """
        start_time = datetime.now()
        
        try:
            # Search for relevant knowledge
            search_request = KnowledgeSearchRequest(
                query=query,
                workspace_id=workspace_id,
                top_k=num_examples,
                category_filter=category_filter,
                language_filter=language_filter,
                **kwargs
            )
            
            search_result = await self.retriever.search_knowledge(search_request)
            
            # Build enhanced prompt
            enhanced_prompt = self._build_enhanced_prompt(
                base_prompt,
                search_result.items
            )
            
            # Prepare retrieved items metadata
            retrieved_items = [
                {
                    'id': item.id,
                    'title': item.title,
                    'category': item.category.value,
                    'content_preview': item.content[:200] + "..." if len(item.content) > 200 else item.content,
                    'relevance_score': getattr(item, 'relevance_score', 0.0),
                    'tags': item.tags,
                    'author': item.author
                }
                for item in search_result.items
            ]
            
            search_metadata = {
                'search_time_ms': search_result.search_time_ms,
                'total_found': search_result.total_count,
                'num_examples_included': len(search_result.items)
            }
            
            return EnhancedPrompt(
                original_prompt=base_prompt,
                enhanced_prompt=enhanced_prompt,
                retrieved_items=retrieved_items,
                search_metadata=search_metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to enhance prompt: {e}")
            # Return original prompt if enhancement fails
            return EnhancedPrompt(
                original_prompt=base_prompt,
                enhanced_prompt=base_prompt,
                retrieved_items=[],
                search_metadata={'error': str(e)}
            )
    
    async def search_knowledge(
        self,
        search_request: KnowledgeSearchRequest
    ) -> KnowledgeSearchResult:
        """Search knowledge base for relevant items.
        
        Args:
            search_request: Search request parameters
            
        Returns:
            Search results
        """
        return await self.retriever.search_knowledge(search_request)
    
    async def get_recommendations(
        self,
        knowledge_item_id: str,
        workspace_id: str,
        num_recommendations: int = 5
    ) -> List[KnowledgeItem]:
        """Get recommendations based on a knowledge item.
        
        Args:
            knowledge_item_id: ID of the knowledge item to base recommendations on
            workspace_id: Workspace ID
            num_recommendations: Number of recommendations to return
            
        Returns:
            Recommended knowledge items
        """
        try:
            # Get the original knowledge item
            knowledge_item = await self.retriever.get_knowledge_item(knowledge_item_id)
            if not knowledge_item:
                return []
            
            # Create a query based on the item's content and tags
            query = f"{knowledge_item.title} {knowledge_item.content[:100]}"
            if knowledge_item.tags:
                query += f" {' '.join(knowledge_item.tags[:5])}"  # Limit tags to prevent overly long queries
            
            # Search for similar items
            search_request = KnowledgeSearchRequest(
                query=query,
                workspace_id=workspace_id,
                top_k=num_recommendations + 1,  # +1 to exclude the original item
                category_filter=knowledge_item.category,
                language_filter=knowledge_item.language
            )
            
            search_result = await self.retriever.search_knowledge(search_request)
            
            # Filter out the original item and limit results
            recommendations = [
                item for item in search_result.items
                if item.id != knowledge_item_id
            ][:num_recommendations]
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            return []
    
    async def track_usage(
        self,
        knowledge_item_id: str,
        usage_type: str = "search",
        **metadata
    ) -> None:
        """Track knowledge item usage for analytics.
        
        Args:
            knowledge_item_id: ID of the knowledge item
            usage_type: Type of usage (search, reference, etc.)
            **metadata: Additional metadata about the usage
        """
        try:
            await self.retriever.update_usage_stats(knowledge_item_id, usage_type, **metadata)
        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
    
    def _build_enhanced_prompt(
        self,
        base_prompt: str,
        knowledge_items: List[KnowledgeItem]
    ) -> str:
        """Build enhanced prompt with knowledge examples.
        
        Args:
            base_prompt: Original prompt
            knowledge_items: Retrieved knowledge items
            
        Returns:
            Enhanced prompt string
        """
        if not knowledge_items:
            return base_prompt
        
        # Build knowledge examples section
        examples_section = "\n\n## Relevant Knowledge Examples:\n"
        
        for i, item in enumerate(knowledge_items, 1):
            examples_section += f"\n### Example {i}: {item.title}\n"
            examples_section += f"**Category:** {item.category.value.replace('_', ' ').title()}\n"
            if item.language:
                examples_section += f"**Language:** {item.language}\n"
            if item.tags:
                examples_section += f"**Tags:** {', '.join(item.tags)}\n"
            examples_section += f"**Content:**\n{item.content}\n"
        
        # Add instruction for using examples
        instruction = "\n\nUse these examples as reference patterns and best practices when creating your response. " \
                     "Adapt the concepts and patterns to the specific requirements of this task."
        
        return base_prompt + examples_section + instruction
    
    async def get_knowledge_stats(
        self,
        workspace_id: str
    ) -> Dict[str, Any]:
        """Get knowledge base statistics for a workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Knowledge base statistics
        """
        try:
            return await self.retriever.get_workspace_stats(workspace_id)
        except Exception as e:
            logger.error(f"Failed to get knowledge stats: {e}")
            return {}


# Factory function for creating RAG service
async def create_rag_service(
    db_session: AsyncSession,
    vector_db_provider: str,
    vector_db_config: Dict[str, Any],
    default_embedding_model: EmbeddingModel = EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL
) -> RAGService:
    """Create and initialize a RAG service.
    
    Args:
        db_session: Database session
        vector_db_provider: Vector database provider name
        vector_db_config: Vector database configuration
        default_embedding_model: Default embedding model
        
    Returns:
        Initialized RAG service
    """
    from backend.db.models.enums import VectorDBProvider
    
    # Create vector database
    provider = VectorDBProvider(vector_db_provider)
    vector_db = create_vector_db(provider, vector_db_config)
    await vector_db.initialize()
    
    # Create embedding service
    embedding_service = EmbeddingService(default_embedding_model)
    
    # Create RAG service
    rag_service = RAGService(db_session, vector_db, embedding_service)
    
    return rag_service