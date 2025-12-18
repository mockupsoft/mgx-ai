# -*- coding: utf-8 -*-
"""Knowledge Retriever Service.

Provides semantic search and retrieval functionality for the knowledge base.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from backend.db.models.entities import KnowledgeItem, Workspace
from backend.db.models.enums import KnowledgeCategory, KnowledgeItemStatus
from .vector_db import VectorDB, SearchResult, VectorDBError
from .rag_service import KnowledgeSearchRequest, KnowledgeSearchResult, EmbeddingService

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """Service for retrieving knowledge items with semantic search."""
    
    def __init__(self, db_session: AsyncSession, vector_db: VectorDB):
        """Initialize knowledge retriever.
        
        Args:
            db_session: Database session
            vector_db: Vector database instance
        """
        self.db_session = db_session
        self.vector_db = vector_db
        self.embedding_service = EmbeddingService()
        
        logger.info("Knowledge Retriever initialized")
    
    async def search_knowledge(
        self,
        search_request: KnowledgeSearchRequest
    ) -> KnowledgeSearchResult:
        """Search knowledge base with semantic similarity.
        
        Args:
            search_request: Search request parameters
            
        Returns:
            Search results with metadata
        """
        start_time = datetime.now()
        
        try:
            # Generate embedding for the search query
            query_embedding = await self.embedding_service.embed_text(search_request.query)
            
            # Prepare metadata filters for vector search
            vector_filters = self._build_vector_filters(search_request)
            
            # Search in vector database
            collection_name = self._get_collection_name(search_request.workspace_id)
            vector_results = await self.vector_db.search(
                query_embedding=query_embedding,
                top_k=search_request.top_k * 2,  # Get more results for filtering
                collection_name=collection_name,
                filter_metadata=vector_filters
            )
            
            # Get knowledge items from database
            knowledge_items = await self._get_knowledge_items_by_embedding_ids(
                [result.id for result in vector_results],
                search_request.workspace_id
            )
            
            # Apply additional filtering
            filtered_items = self._apply_filters(
                knowledge_items,
                search_request
            )
            
            # Sort by relevance score and limit results
            sorted_items = sorted(
                filtered_items,
                key=lambda item: item.relevance_score,
                reverse=True
            )[:search_request.top_k]
            
            # Update usage statistics
            await self._update_search_stats([item.id for item in sorted_items])
            
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return KnowledgeSearchResult(
                items=sorted_items,
                total_count=len(sorted_items),
                search_time_ms=search_time,
                metadata={
                    'query': search_request.query,
                    'vector_results_count': len(vector_results),
                    'database_items_found': len(knowledge_items),
                    'filtered_items': len(filtered_items),
                    'final_results': len(sorted_items)
                }
            )
            
        except VectorDBError as e:
            logger.warning(f"Vector search failed, falling back to text search: {e}")
            return await self._fallback_text_search(search_request)
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return KnowledgeSearchResult(
                items=[],
                total_count=0,
                search_time_ms=0,
                metadata={'error': str(e)}
            )
    
    async def _fallback_text_search(
        self,
        search_request: KnowledgeSearchRequest
    ) -> KnowledgeSearchResult:
        """Fallback to text-based search when vector search fails.
        
        Args:
            search_request: Search request parameters
            
        Returns:
            Search results using text matching
        """
        start_time = datetime.now()
        
        try:
            # Build query for text search
            query_conditions = []
            
            # Search in title and content
            search_terms = search_request.query.lower().split()
            for term in search_terms:
                query_conditions.append(
                    or_(
                        func.lower(KnowledgeItem.title).like(f'%{term}%'),
                        func.lower(KnowledgeItem.content).like(f'%{term}%')
                    )
                )
            
            # Build base query
            stmt = select(KnowledgeItem).where(
                and_(
                    KnowledgeItem.workspace_id == search_request.workspace_id,
                    KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                    *query_conditions
                )
            )
            
            # Apply filters
            if search_request.category_filter:
                stmt = stmt.where(KnowledgeItem.category == search_request.category_filter)
            
            if search_request.language_filter:
                stmt = stmt.where(KnowledgeItem.language == search_request.language_filter)
            
            # Execute query
            result = await self.db_session.execute(stmt)
            items = result.scalars().all()
            
            # Calculate relevance scores based on text matches
            scored_items = []
            for item in items:
                score = self._calculate_text_relevance(search_request.query, item)
                if score >= search_request.min_relevance_score:
                    scored_items.append(item)
            
            # Sort by relevance and limit
            sorted_items = sorted(
                scored_items,
                key=lambda item: self._calculate_text_relevance(search_request.query, item),
                reverse=True
            )[:search_request.top_k]
            
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return KnowledgeSearchResult(
                items=sorted_items,
                total_count=len(sorted_items),
                search_time_ms=search_time,
                metadata={'search_type': 'text_fallback'}
            )
            
        except Exception as e:
            logger.error(f"Text search fallback failed: {e}")
            return KnowledgeSearchResult(
                items=[],
                total_count=0,
                search_time_ms=0,
                metadata={'error': str(e)}
            )
    
    async def _get_knowledge_items_by_embedding_ids(
        self,
        embedding_ids: List[str],
        workspace_id: str
    ) -> List[KnowledgeItem]:
        """Get knowledge items by their embedding IDs.
        
        Args:
            embedding_ids: List of embedding IDs
            workspace_id: Workspace ID
            
        Returns:
            Knowledge items
        """
        if not embedding_ids:
            return []
        
        stmt = select(KnowledgeItem).where(
            and_(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.embedding_id.in_(embedding_ids),
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE
            )
        )
        
        result = await self.db_session.execute(stmt)
        return result.scalars().all()
    
    def _apply_filters(
        self,
        items: List[KnowledgeItem],
        search_request: KnowledgeSearchRequest
    ) -> List[KnowledgeItem]:
        """Apply additional filters to knowledge items.
        
        Args:
            items: Knowledge items to filter
            search_request: Search request with filters
            
        Returns:
            Filtered knowledge items
        """
        filtered = items.copy()
        
        # Apply category filter
        if search_request.category_filter:
            filtered = [
                item for item in filtered
                if item.category == search_request.category_filter
            ]
        
        # Apply language filter
        if search_request.language_filter:
            filtered = [
                item for item in filtered
                if item.language == search_request.language_filter
            ]
        
        # Apply tags filter
        if search_request.tags_filter:
            filtered = [
                item for item in filtered
                if any(tag in item.tags for tag in search_request.tags_filter)
            ]
        
        # Apply minimum relevance score
        filtered = [
            item for item in filtered
            if item.relevance_score >= search_request.min_relevance_score
        ]
        
        return filtered
    
    def _build_vector_filters(
        self,
        search_request: KnowledgeSearchRequest
    ) -> Dict[str, Any]:
        """Build metadata filters for vector search.
        
        Args:
            search_request: Search request
            
        Returns:
            Metadata filters dictionary
        """
        filters = {}
        
        if search_request.category_filter:
            filters['category'] = search_request.category_filter.value
        
        if search_request.language_filter:
            filters['language'] = search_request.language_filter
        
        if search_request.tags_filter and len(search_request.tags_filter) == 1:
            filters['tags'] = search_request.tags_filter[0]
        
        return filters
    
    def _get_collection_name(self, workspace_id: str) -> str:
        """Get collection name for workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Collection name
        """
        return f"knowledge_{workspace_id}"
    
    def _calculate_text_relevance(
        self,
        query: str,
        item: KnowledgeItem
    ) -> float:
        """Calculate text-based relevance score.
        
        Args:
            query: Search query
            item: Knowledge item
            
        Returns:
            Relevance score (0-1)
        """
        query_lower = query.lower()
        title_lower = item.title.lower()
        content_lower = item.content.lower()
        
        # Score based on title matches (higher weight)
        title_matches = sum(1 for term in query_lower.split() if term in title_lower)
        title_score = min(title_matches / len(query_lower.split()), 1.0) * 0.6
        
        # Score based on content matches (lower weight)
        content_matches = sum(1 for term in query_lower.split() if term in content_lower)
        content_score = min(content_matches / len(query_lower.split()), 1.0) * 0.4
        
        # Boost score for exact phrase matches
        phrase_boost = 0.0
        if query_lower in title_lower:
            phrase_boost = 0.2
        elif query_lower in content_lower:
            phrase_boost = 0.1
        
        return min(title_score + content_score + phrase_boost, 1.0)
    
    async def _update_search_stats(self, item_ids: List[str]) -> None:
        """Update search statistics for knowledge items.
        
        Args:
            item_ids: IDs of items that were accessed
        """
        if not item_ids:
            return
        
        try:
            # Update usage count and last accessed time
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.id.in_(item_ids)
            )
            
            result = await self.db_session.execute(stmt)
            items = result.scalars().all()
            
            current_time = datetime.now()
            for item in items:
                item.usage_count += 1
                item.last_accessed = current_time
            
            await self.db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update search stats: {e}")
    
    async def get_knowledge_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a specific knowledge item by ID.
        
        Args:
            item_id: Knowledge item ID
            
        Returns:
            Knowledge item or None
        """
        stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_usage_stats(
        self,
        knowledge_item_id: str,
        usage_type: str,
        **metadata
    ) -> None:
        """Update usage statistics for a knowledge item.
        
        Args:
            knowledge_item_id: Knowledge item ID
            usage_type: Type of usage
            **metadata: Additional metadata
        """
        try:
            item = await self.get_knowledge_item(knowledge_item_id)
            if not item:
                return
            
            # Update usage count
            item.usage_count += 1
            item.last_accessed = datetime.now()
            
            # Update relevance score based on usage
            if usage_type == "reference":
                item.relevance_score = min(item.relevance_score + 0.1, 1.0)
            elif usage_type == "search":
                item.relevance_score = min(item.relevance_score + 0.05, 1.0)
            
            await self.db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update usage stats: {e}")
    
    async def get_workspace_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get knowledge base statistics for a workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Statistics dictionary
        """
        try:
            # Get total items count
            total_stmt = select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.workspace_id == workspace_id
            )
            total_result = await self.db_session.execute(total_stmt)
            total_items = total_result.scalar() or 0
            
            # Get items by category
            category_stmt = select(
                KnowledgeItem.category,
                func.count(KnowledgeItem.id)
            ).where(
                KnowledgeItem.workspace_id == workspace_id
            ).group_by(KnowledgeItem.category)
            
            category_result = await self.db_session.execute(category_stmt)
            category_counts = dict(category_result.all())
            
            # Get items by status
            status_stmt = select(
                KnowledgeItem.status,
                func.count(KnowledgeItem.id)
            ).where(
                KnowledgeItem.workspace_id == workspace_id
            ).group_by(KnowledgeItem.status)
            
            status_result = await self.db_session.execute(status_stmt)
            status_counts = dict(status_result.all())
            
            # Get top used items
            top_used_stmt = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == workspace_id
            ).order_by(
                KnowledgeItem.usage_count.desc()
            ).limit(10)
            
            top_used_result = await self.db_session.execute(top_used_stmt)
            top_used_items = [
                {
                    'id': item.id,
                    'title': item.title,
                    'usage_count': item.usage_count,
                    'category': item.category.value
                }
                for item in top_used_result.scalars().all()
            ]
            
            # Get recent items
            recent_stmt = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == workspace_id
            ).order_by(
                KnowledgeItem.created_at.desc()
            ).limit(10)
            
            recent_result = await self.db_session.execute(recent_stmt)
            recent_items = [
                {
                    'id': item.id,
                    'title': item.title,
                    'created_at': item.created_at,
                    'category': item.category.value
                }
                for item in recent_result.scalars().all()
            ]
            
            return {
                'total_items': total_items,
                'category_distribution': category_counts,
                'status_distribution': status_counts,
                'top_used_items': top_used_items,
                'recent_items': recent_items,
                'embedding_stats': await self._get_embedding_stats(workspace_id)
            }
            
        except Exception as e:
            logger.error(f"Failed to get workspace stats: {e}")
            return {}
    
    async def _get_embedding_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get embedding-related statistics.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Embedding statistics
        """
        try:
            # Count items with embeddings
            embedded_stmt = select(func.count(KnowledgeItem.id)).where(
                and_(
                    KnowledgeItem.workspace_id == workspace_id,
                    KnowledgeItem.embedding_id.isnot(None)
                )
            )
            embedded_result = await self.db_session.execute(embedded_stmt)
            embedded_count = embedded_result.scalar() or 0
            
            # Count items without embeddings
            not_embedded_stmt = select(func.count(KnowledgeItem.id)).where(
                and_(
                    KnowledgeItem.workspace_id == workspace_id,
                    KnowledgeItem.embedding_id.is_(None)
                )
            )
            not_embedded_result = await self.db_session.execute(not_embedded_stmt)
            not_embedded_count = not_embedded_result.scalar() or 0
            
            # Get vector database stats if available
            vector_stats = {}
            try:
                collection_name = self._get_collection_name(workspace_id)
                vector_count = await self.vector_db.count(collection_name)
                vector_stats = {
                    'vector_db_count': vector_count,
                    'vector_db_healthy': await self.vector_db.health_check()
                }
            except Exception as e:
                logger.warning(f"Failed to get vector DB stats: {e}")
                vector_stats = {
                    'vector_db_count': 0,
                    'vector_db_healthy': False,
                    'error': str(e)
                }
            
            return {
                'items_with_embeddings': embedded_count,
                'items_without_embeddings': not_embedded_count,
                'embedding_coverage': embedded_count / (embedded_count + not_embedded_count) if (embedded_count + not_embedded_count) > 0 else 0,
                **vector_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {}