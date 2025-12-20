# -*- coding: utf-8 -*-
"""Embedding Service.

Service for generating embeddings using various models.
"""

import logging
from typing import List, Optional, Dict, Any
from backend.db.models.enums import EmbeddingModel

logger = logging.getLogger(__name__)

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
