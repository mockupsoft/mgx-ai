# -*- coding: utf-8 -*-
"""Knowledge Base API Routes.

Provides REST API endpoints for knowledge base management, search, and RAG functionality.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi.responses import JSONResponse

from backend.db.session import get_async_session
from backend.db.models.entities import KnowledgeItem, Workspace
from backend.db.models.enums import KnowledgeCategory, KnowledgeSourceType, KnowledgeItemStatus
from backend.services.knowledge.factory import create_knowledge_base_services, cleanup_knowledge_base_services
from backend.schemas import (
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    KnowledgeItemResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    KnowledgeSearchResponse,
    EnhancedPromptRequest,
    EnhancedPromptResponse,
    IngestionRequest,
    IngestionResponse,
    KnowledgeStatsResponse,
)
from backend.services.knowledge.rag_service import KnowledgeSearchRequest as RAGSearchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["knowledge-base"])


# Dependency to get knowledge base services
async def get_knowledge_services(db_session: AsyncSession = Depends(get_async_session)):
    """Get knowledge base services."""
    try:
        services = await create_knowledge_base_services(db_session)
        yield services
    finally:
        await cleanup_knowledge_base_services(db_session)


@router.get("/workspaces/{workspace_id}/knowledge", response_model=List[KnowledgeItemResponse])
async def list_knowledge_items(
    workspace_id: str,
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    db_session: AsyncSession = Depends(get_async_session)
):
    """List knowledge items for a workspace."""
    try:
        # Validate workspace exists
        workspace_result = await db_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # Build query
        query = select(KnowledgeItem).where(KnowledgeItem.workspace_id == workspace_id)
        
        # Apply filters
        if category:
            try:
                query = query.where(KnowledgeItem.category == KnowledgeCategory(category))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        if status:
            try:
                query = query.where(KnowledgeItem.status == KnowledgeItemStatus(status))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        if language:
            query = query.where(KnowledgeItem.language == language)
        
        # Order by relevance score and usage count
        query = query.order_by(
            KnowledgeItem.relevance_score.desc(),
            KnowledgeItem.usage_count.desc(),
            KnowledgeItem.updated_at.desc()
        ).offset(skip).limit(limit)
        
        result = await db_session.execute(query)
        items = result.scalars().all()
        
        return [KnowledgeItemResponse.from_orm(item) for item in items]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list knowledge items: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge items")


@router.post("/workspaces/{workspace_id}/knowledge", response_model=KnowledgeItemResponse)
async def create_knowledge_item(
    workspace_id: str,
    item_data: KnowledgeItemCreate,
    db_session: AsyncSession = Depends(get_async_session)
):
    """Create a new knowledge item."""
    try:
        # Validate workspace exists
        workspace_result = await db_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # Create knowledge item
        item = KnowledgeItem(
            workspace_id=workspace_id,
            title=item_data.title,
            content=item_data.content,
            category=KnowledgeCategory(item_data.category),
            language=item_data.language,
            tags=item_data.tags,
            source=KnowledgeSourceType(item_data.source),
            author=item_data.author,
            status=KnowledgeItemStatus.ACTIVE
        )
        
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        return KnowledgeItemResponse.from_orm(item)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {e}")
    except Exception as e:
        logger.error(f"Failed to create knowledge item: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create knowledge item")


@router.get("/workspaces/{workspace_id}/knowledge/{item_id}", response_model=KnowledgeItemResponse)
async def get_knowledge_item(
    workspace_id: str,
    item_id: str,
    db_session: AsyncSession = Depends(get_async_session)
):
    """Get a specific knowledge item."""
    try:
        result = await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id == item_id,
                KnowledgeItem.workspace_id == workspace_id
            )
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        
        return KnowledgeItemResponse.from_orm(item)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge item: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge item")


@router.put("/workspaces/{workspace_id}/knowledge/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    workspace_id: str,
    item_id: str,
    item_data: KnowledgeItemUpdate,
    db_session: AsyncSession = Depends(get_async_session)
):
    """Update a knowledge item."""
    try:
        result = await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id == item_id,
                KnowledgeItem.workspace_id == workspace_id
            )
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        
        # Update fields
        if item_data.title is not None:
            item.title = item_data.title
        if item_data.content is not None:
            item.content = item_data.content
        if item_data.category is not None:
            try:
                item.category = KnowledgeCategory(item_data.category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {item_data.category}")
        if item_data.language is not None:
            item.language = item_data.language
        if item_data.tags is not None:
            item.tags = item_data.tags
        if item_data.status is not None:
            try:
                item.status = KnowledgeItemStatus(item_data.status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {item_data.status}")
        
        await db_session.commit()
        await db_session.refresh(item)
        
        return KnowledgeItemResponse.from_orm(item)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {e}")
    except Exception as e:
        logger.error(f"Failed to update knowledge item: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail="Failed to update knowledge item")


@router.delete("/workspaces/{workspace_id}/knowledge/{item_id}")
async def delete_knowledge_item(
    workspace_id: str,
    item_id: str,
    services: dict = Depends(get_knowledge_services),
    db_session: AsyncSession = Depends(get_async_session)
):
    """Delete a knowledge item."""
    try:
        result = await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id == item_id,
                KnowledgeItem.workspace_id == workspace_id
            )
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        
        # Delete from vector database if embedding exists
        if item.embedding_id:
            try:
                await services['vector_db'].delete(
                    item.embedding_id,
                    collection_name=services['vector_db']._get_collection_name(workspace_id)
                )
            except Exception as e:
                logger.warning(f"Failed to delete embedding: {e}")
        
        # Delete from database
        await db_session.delete(item)
        await db_session.commit()
        
        return {"message": "Knowledge item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete knowledge item: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete knowledge item")


@router.post("/workspaces/{workspace_id}/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    workspace_id: str,
    search_request: KnowledgeSearchRequest,
    services: dict = Depends(get_knowledge_services)
):
    """Search knowledge base using semantic search."""
    try:
        # Convert to RAG service search request
        rag_search_request = RAGSearchRequest(
            query=search_request.query,
            workspace_id=workspace_id,
            top_k=search_request.top_k,
            category_filter=KnowledgeCategory(search_request.category_filter) if search_request.category_filter else None,
            language_filter=search_request.language_filter,
            tags_filter=search_request.tags_filter,
            min_relevance_score=search_request.min_relevance_score
        )
        
        # Perform search
        search_result = await services['retriever'].search_knowledge(rag_search_request)
        
        # Convert to response format
        items = [
            KnowledgeSearchResult(
                id=item.id,
                title=item.title,
                content_preview=item.content[:200] + "..." if len(item.content) > 200 else item.content,
                category=item.category.value,
                language=item.language,
                tags=item.tags,
                author=item.author,
                relevance_score=item.relevance_score,
                source=item.source.value,
                file_path=item.file_path
            )
            for item in search_result.items
        ]
        
        return KnowledgeSearchResponse(
            items=items,
            total_count=search_result.total_count,
            search_time_ms=search_result.search_time_ms,
            metadata=search_result.metadata
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid search parameters: {e}")
    except Exception as e:
        logger.error(f"Failed to search knowledge: {e}")
        raise HTTPException(status_code=500, detail="Failed to search knowledge base")


@router.post("/workspaces/{workspace_id}/knowledge/enhance-prompt", response_model=EnhancedPromptResponse)
async def enhance_prompt(
    workspace_id: str,
    prompt_request: EnhancedPromptRequest,
    services: dict = Depends(get_knowledge_services)
):
    """Enhance a prompt with relevant knowledge examples."""
    try:
        # Get category filter if provided
        category_filter = None
        if prompt_request.category_filter:
            try:
                category_filter = KnowledgeCategory(prompt_request.category_filter)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {prompt_request.category_filter}")
        
        # Enhance prompt
        enhanced = await services['rag_service'].enhance_prompt(
            base_prompt=prompt_request.base_prompt,
            query=prompt_request.query,
            workspace_id=workspace_id,
            num_examples=prompt_request.num_examples,
            category_filter=category_filter,
            language_filter=prompt_request.language_filter
        )
        
        return EnhancedPromptResponse(
            original_prompt=enhanced.original_prompt,
            enhanced_prompt=enhanced.enhanced_prompt,
            retrieved_items=enhanced.retrieved_items,
            search_metadata=enhanced.search_metadata
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")
    except Exception as e:
        logger.error(f"Failed to enhance prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to enhance prompt")


@router.post("/workspaces/{workspace_id}/knowledge/ingest", response_model=IngestionResponse)
async def ingest_knowledge(
    workspace_id: str,
    ingestion_request: IngestionRequest,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_async_session)
):
    """Start knowledge ingestion from various sources."""
    try:
        # Validate workspace exists
        workspace_result = await db_session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # Validate source type
        try:
            source_type = KnowledgeSourceType(ingestion_request.source_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source type: {ingestion_request.source_type}")
        
        # Create and start ingestion job (simplified)
        job_id = str(UUID.random())
        
        # For demonstration, we'll return a mock response
        # In a real implementation, this would start a background task
        response = IngestionResponse(
            job_id=job_id,
            status="completed",
            progress=1.0,
            items_processed=0,
            items_created=0,
            items_updated=0,
            created_at=None
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start ingestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to start knowledge ingestion")


@router.get("/workspaces/{workspace_id}/knowledge/ingest/{job_id}/status", response_model=IngestionResponse)
async def get_ingestion_status(
    workspace_id: str,
    job_id: str,
    db_session: AsyncSession = Depends(get_async_session)
):
    """Get the status of an ingestion job."""
    try:
        # This would typically fetch from a job tracking table
        # For now, return a mock response
        return IngestionResponse(
            job_id=job_id,
            status="completed",
            progress=1.0,
            items_processed=0,
            items_created=0,
            items_updated=0,
            created_at=None
        )
        
    except Exception as e:
        logger.error(f"Failed to get ingestion status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ingestion status")


@router.get("/workspaces/{workspace_id}/knowledge/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    workspace_id: str,
    services: dict = Depends(get_knowledge_services)
):
    """Get knowledge base statistics for a workspace."""
    try:
        stats = await services['rag_service'].get_knowledge_stats(workspace_id)
        
        return KnowledgeStatsResponse(
            total_items=stats.get('total_items', 0),
            category_distribution=stats.get('category_distribution', {}),
            status_distribution=stats.get('status_distribution', {}),
            top_used_items=stats.get('top_used_items', []),
            recent_items=stats.get('recent_items', []),
            embedding_stats=stats.get('embedding_stats', {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get knowledge stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get knowledge statistics")


@router.get("/workspaces/{workspace_id}/knowledge/health")
async def health_check(
    workspace_id: str,
    services: dict = Depends(get_knowledge_services)
):
    """Perform health check on knowledge base services."""
    try:
        health_status = await services['factory'].health_check()
        
        return JSONResponse(
            content=health_status,
            status_code=200 if health_status.get('overall') == 'healthy' else 503
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                'overall': 'unhealthy',
                'error': str(e),
                'timestamp': None
            },
            status_code=503
        )