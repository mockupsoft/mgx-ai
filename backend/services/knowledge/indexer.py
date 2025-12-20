# -*- coding: utf-8 -*-
"""Knowledge Indexer Service.

Provides background indexing and maintenance functionality for the knowledge base.
Handles bulk indexing, deduplication, and optimization tasks.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.orm import selectinload

from backend.db.models.entities import KnowledgeItem, Workspace
from backend.db.models.enums import KnowledgeItemStatus, EmbeddingModel
from .vector_db import VectorDB, VectorDBError
from .embedding import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class IndexingTask:
    """Represents an indexing task."""
    
    id: str
    workspace_id: str
    task_type: str
    status: str = "pending"
    progress: float = 0.0
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class KnowledgeIndexer:
    """Service for background indexing and knowledge base maintenance."""
    
    def __init__(
        self,
        db_session: AsyncSession,
        vector_db: VectorDB,
        embedding_service: EmbeddingService
    ):
        """Initialize knowledge indexer.
        
        Args:
            db_session: Database session
            vector_db: Vector database instance
            embedding_service: Embedding service
        """
        self.db_session = db_session
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        
        logger.info("Knowledge Indexer initialized")
    
    async def create_indexing_task(
        self,
        workspace_id: str,
        task_type: str,
        **kwargs
    ) -> IndexingTask:
        """Create a new indexing task.
        
        Args:
            workspace_id: Workspace ID
            task_type: Type of indexing task
            **kwargs: Additional task parameters
            
        Returns:
            Created indexing task
        """
        task = IndexingTask(
            id=str(uuid4()),
            workspace_id=workspace_id,
            task_type=task_type,
            metadata=kwargs
        )
        
        # TODO: Store task in database for tracking
        logger.info(f"Created indexing task {task.id} for workspace {workspace_id}")
        return task
    
    async def bulk_index_workspace(
        self,
        workspace_id: str,
        force_reindex: bool = False,
        batch_size: int = 100
    ) -> IndexingTask:
        """Bulk index all items in a workspace.
        
        Args:
            workspace_id: Workspace ID
            force_reindex: Whether to reindex items that already have embeddings
            batch_size: Number of items to process per batch
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="bulk_index",
            force_reindex=force_reindex,
            batch_size=batch_size
        )
        
        await self._execute_bulk_index(task)
        return task
    
    async def fix_missing_embeddings(
        self,
        workspace_id: str,
        batch_size: int = 50
    ) -> IndexingTask:
        """Index items that are missing embeddings.
        
        Args:
            workspace_id: Workspace ID
            batch_size: Number of items to process per batch
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="fix_missing_embeddings",
            batch_size=batch_size
        )
        
        await self._execute_fix_missing_embeddings(task)
        return task
    
    async def deduplicate_knowledge_items(
        self,
        workspace_id: str,
        similarity_threshold: float = 0.95
    ) -> IndexingTask:
        """Find and handle duplicate knowledge items.
        
        Args:
            workspace_id: Workspace ID
            similarity_threshold: Threshold for considering items similar
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="deduplicate",
            similarity_threshold=similarity_threshold
        )
        
        await self._execute_deduplication(task)
        return task
    
    async def optimize_search_index(
        self,
        workspace_id: str
    ) -> IndexingTask:
        """Optimize the search index for better performance.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="optimize_index"
        )
        
        await self._execute_index_optimization(task)
        return task
    
    async def rebuild_embeddings(
        self,
        workspace_id: str,
        old_model: EmbeddingModel,
        new_model: EmbeddingModel
    ) -> IndexingTask:
        """Rebuild embeddings using a new model.
        
        Args:
            workspace_id: Workspace ID
            old_model: Previous embedding model
            new_model: New embedding model to use
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="rebuild_embeddings",
            old_model=old_model.value,
            new_model=new_model.value
        )
        
        await self._execute_embedding_rebuild(task, new_model)
        return task
    
    async def cleanup_orphaned_embeddings(
        self,
        workspace_id: str
    ) -> IndexingTask:
        """Remove embeddings that no longer have corresponding database records.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Created indexing task
        """
        task = await self.create_indexing_task(
            workspace_id=workspace_id,
            task_type="cleanup_orphaned"
        )
        
        await self._execute_orphaned_cleanup(task)
        return task
    
    async def get_indexing_status(
        self,
        workspace_id: str
    ) -> Dict[str, Any]:
        """Get the current status of indexing operations for a workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Status information
        """
        try:
            # Get workspace stats
            total_items_stmt = select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE
            )
            total_result = await self.db_session.execute(total_items_stmt)
            total_items = total_result.scalar() or 0
            
            # Get items with embeddings
            embedded_stmt = select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                KnowledgeItem.embedding_id.isnot(None)
            )
            embedded_result = await self.db_session.execute(embedded_stmt)
            embedded_items = embedded_result.scalar() or 0
            
            # Get items without embeddings
            not_embedded_stmt = select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                KnowledgeItem.embedding_id.is_(None)
            )
            not_embedded_result = await self.db_session.execute(not_embedded_stmt)
            not_embedded_items = not_embedded_result.scalar() or 0
            
            # Get recent activity
            recent_stmt = select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.updated_at >= datetime.now() - timedelta(days=7)
            )
            recent_result = await self.db_session.execute(recent_stmt)
            recent_items = recent_result.scalar() or 0
            
            # Get vector database stats
            vector_stats = await self._get_vector_db_stats(workspace_id)
            
            return {
                'workspace_id': workspace_id,
                'total_items': total_items,
                'items_with_embeddings': embedded_items,
                'items_without_embeddings': not_embedded_items,
                'embedding_coverage': embedded_items / total_items if total_items > 0 else 0,
                'recent_items': recent_items,
                'vector_database': vector_stats,
                'last_indexing_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get indexing status: {e}")
            return {}
    
    async def _execute_bulk_index(self, task: IndexingTask) -> None:
        """Execute bulk indexing task.
        
        Args:
            task: Indexing task
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Get all items that need indexing
            query = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == task.workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE
            )
            
            # Exclude items that already have embeddings if not forcing reindex
            if not task.metadata.get('force_reindex', False):
                query = query.where(KnowledgeItem.embedding_id.is_(None))
            
            result = await self.db_session.execute(query)
            items = result.scalars().all()
            
            task.total_items = len(items)
            batch_size = task.metadata.get('batch_size', 100)
            
            # Process items in batches
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                successful, failed = await self._index_batch(batch, task)
                
                task.processed_items += len(batch)
                task.successful_items += successful
                task.failed_items += failed
                task.progress = task.processed_items / task.total_items
                
                # Update task status periodically
                if i % (batch_size * 5) == 0:
                    await self._update_task_status(task)
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Bulk indexing task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _execute_fix_missing_embeddings(self, task: IndexingTask) -> None:
        """Execute fix missing embeddings task.
        
        Args:
            task: Indexing task
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Get items without embeddings
            query = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == task.workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                KnowledgeItem.embedding_id.is_(None)
            )
            
            result = await self.db_session.execute(query)
            items = result.scalars().all()
            
            task.total_items = len(items)
            batch_size = task.metadata.get('batch_size', 50)
            
            # Process items in batches
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                successful, failed = await self._index_batch(batch, task)
                
                task.processed_items += len(batch)
                task.successful_items += successful
                task.failed_items += failed
                task.progress = task.processed_items / task.total_items
                
                # Update task status periodically
                if i % (batch_size * 5) == 0:
                    await self._update_task_status(task)
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Fix missing embeddings task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _execute_deduplication(self, task: IndexingTask) -> None:
        """Execute deduplication task.
        
        Args:
            task: Indexing task
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Get all active items in workspace
            query = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == task.workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE
            )
            
            result = await self.db_session.execute(query)
            items = result.scalars().all()
            
            task.total_items = len(items)
            
            # Group items by similarity (simplified approach)
            groups = self._group_similar_items(items, task.metadata.get('similarity_threshold', 0.95))
            
            duplicates_found = 0
            duplicates_merged = 0
            
            for group in groups:
                if len(group) > 1:
                    duplicates_found += len(group) - 1
                    # Merge duplicates (keep the most recent one)
                    merged_item = self._merge_duplicate_items(group)
                    duplicates_merged += len(group) - 1
                    
                    # Mark others as archived
                    for item in group[1:]:
                        item.status = KnowledgeItemStatus.ARCHIVED
                        item.updated_at = datetime.now()
            
            await self.db_session.commit()
            
            task.successful_items = duplicates_merged
            task.processed_items = duplicates_found
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Deduplication task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _execute_index_optimization(self, task: IndexingTask) -> None:
        """Execute index optimization task.
        
        Args:
            task: Indexing task
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Optimize vector database collection
            collection_name = self.vector_db._get_collection_name(task.workspace_id)
            
            # TODO: Implement vector database specific optimization
            # This would include tasks like:
            # - Index compaction
            # - Vacuum operations
            # - Statistics updates
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Index optimization task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _execute_embedding_rebuild(
        self,
        task: IndexingTask,
        new_model: EmbeddingModel
    ) -> None:
        """Execute embedding rebuild task.
        
        Args:
            task: Indexing task
            new_model: New embedding model
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Get all items with embeddings
            query = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == task.workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                KnowledgeItem.embedding_id.isnot(None)
            )
            
            result = await self.db_session.execute(query)
            items = result.scalars().all()
            
            task.total_items = len(items)
            batch_size = 25  # Smaller batch for embedding generation
            
            # Process items in batches
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                successful, failed = await self._rebuild_embeddings_batch(batch, new_model, task)
                
                task.processed_items += len(batch)
                task.successful_items += successful
                task.failed_items += failed
                task.progress = task.processed_items / task.total_items
                
                # Update task status periodically
                if i % (batch_size * 5) == 0:
                    await self._update_task_status(task)
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Embedding rebuild task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _execute_orphaned_cleanup(self, task: IndexingTask) -> None:
        """Execute orphaned embeddings cleanup task.
        
        Args:
            task: Indexing task
        """
        task.started_at = datetime.now()
        task.status = "running"
        
        try:
            # Get collection name
            collection_name = self.vector_db._get_collection_name(task.workspace_id)
            
            # Get all embedding IDs from database
            query = select(KnowledgeItem.embedding_id).where(
                KnowledgeItem.workspace_id == task.workspace_id,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                KnowledgeItem.embedding_id.isnot(None)
            )
            
            result = await self.db_session.execute(query)
            valid_embedding_ids = set(row[0] for row in result.all() if row[0])
            
            # TODO: Get all embedding IDs from vector database
            # This would require implementing a list method in VectorDB
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Orphaned cleanup task {task.id} failed: {e}")
        
        await self._update_task_status(task)
    
    async def _index_batch(
        self,
        items: List[KnowledgeItem],
        task: IndexingTask
    ) -> Tuple[int, int]:
        """Index a batch of knowledge items.
        
        Args:
            items: Knowledge items to index
            task: Indexing task
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0
        
        for item in items:
            try:
                await self._index_single_item(item)
                successful += 1
            except Exception as e:
                logger.error(f"Failed to index item {item.id}: {e}")
                failed += 1
        
        await self.db_session.commit()
        return successful, failed
    
    async def _index_single_item(self, item: KnowledgeItem) -> None:
        """Index a single knowledge item.
        
        Args:
            item: Knowledge item to index
        """
        try:
            # Generate embedding
            embedding = await self.embedding_service.embed_text(
                f"{item.title}\n{item.content}"
            )
            item.vector_dimension = len(embedding)
            
            # Store in vector database
            embedding_id = self.vector_db._generate_embedding_id(
                f"{item.title}\n{item.content}", item.workspace_id
            )
            
            success = await self.vector_db.store_embedding(
                text_id=embedding_id,
                embedding=embedding,
                metadata={
                    'title': item.title,
                    'category': item.category.value,
                    'language': item.language,
                    'tags': item.tags,
                    'workspace_id': item.workspace_id,
                    'knowledge_item_id': item.id,
                    'created_at': item.created_at.isoformat() if item.created_at else None,
                    'updated_at': item.updated_at.isoformat() if item.updated_at else None
                },
                collection_name=self.vector_db._get_collection_name(item.workspace_id)
            )
            
            if success:
                item.embedding_id = embedding_id
                item.embedding_model = EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL
            else:
                logger.warning(f"Failed to store embedding for item {item.id}")
                
        except Exception as e:
            logger.error(f"Failed to index item {item.id}: {e}")
            raise
    
    async def _rebuild_embeddings_batch(
        self,
        items: List[KnowledgeItem],
        new_model: EmbeddingModel,
        task: IndexingTask
    ) -> Tuple[int, int]:
        """Rebuild embeddings for a batch of items.
        
        Args:
            items: Knowledge items to rebuild embeddings for
            new_model: New embedding model
            task: Indexing task
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0
        
        for item in items:
            try:
                # Delete old embedding
                if item.embedding_id:
                    await self.vector_db.delete(item.embedding_id)
                
                # Generate new embedding
                embedding = await self.embedding_service.embed_text(
                    f"{item.title}\n{item.content}",
                    model=new_model
                )
                item.vector_dimension = len(embedding)
                
                # Store new embedding
                embedding_id = self.vector_db._generate_embedding_id(
                    f"{item.title}\n{item.content}", item.workspace_id
                )
                
                success = await self.vector_db.store_embedding(
                    text_id=embedding_id,
                    embedding=embedding,
                    metadata={
                        'title': item.title,
                        'category': item.category.value,
                        'language': item.language,
                        'tags': item.tags,
                        'workspace_id': item.workspace_id,
                        'knowledge_item_id': item.id
                    },
                    collection_name=self.vector_db._get_collection_name(item.workspace_id)
                )
                
                if success:
                    item.embedding_id = embedding_id
                    item.embedding_model = new_model
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Failed to rebuild embedding for item {item.id}: {e}")
                failed += 1
        
        await self.db_session.commit()
        return successful, failed
    
    def _group_similar_items(
        self,
        items: List[KnowledgeItem],
        threshold: float
    ) -> List[List[KnowledgeItem]]:
        """Group similar items together.
        
        Args:
            items: Knowledge items to group
            threshold: Similarity threshold
            
        Returns:
            Groups of similar items
        """
        # Simplified grouping based on title similarity
        groups = []
        
        for item in items:
            placed = False
            for group in groups:
                # Check similarity with first item in group
                if self._calculate_similarity(item.title, group[0].title) >= threshold:
                    group.append(item)
                    placed = True
                    break
            
            if not placed:
                groups.append([item])
        
        return groups
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        # Simple Jaccard similarity based on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _merge_duplicate_items(self, items: List[KnowledgeItem]) -> KnowledgeItem:
        """Merge duplicate items into a single item.
        
        Args:
            items: List of duplicate items
            
        Returns:
            Merged item
        """
        # Keep the most recently updated item
        merged = max(items, key=lambda x: x.updated_at or x.created_at)
        
        # Merge additional information from other items
        all_tags = set()
        for item in items:
            all_tags.update(item.tags)
        
        merged.tags = list(all_tags)
        
        # Update usage count
        merged.usage_count = max(item.usage_count for item in items)
        
        return merged
    
    async def _get_vector_db_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get vector database statistics.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Vector database statistics
        """
        try:
            collection_name = self.vector_db._get_collection_name(workspace_id)
            
            return {
                'collection_name': collection_name,
                'embedding_count': await self.vector_db.count(collection_name),
                'healthy': await self.vector_db.health_check(),
                'provider': self.vector_db.provider.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get vector DB stats: {e}")
            return {
                'embedding_count': 0,
                'healthy': False,
                'error': str(e)
            }
    
    async def _update_task_status(self, task: IndexingTask) -> None:
        """Update indexing task status.
        
        Args:
            task: Indexing task to update
        """
        # TODO: Store task updates in database
        task.updated_at = datetime.now()
        logger.info(f"Task {task.id}: {task.progress:.2%} complete ({task.processed_items}/{task.total_items})")