"""ADR repository.

Data access for Architecture Decision Records.
"""

from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from fastapi import HTTPException, status

from backend.db.models.entities import ADR
from backend.db.models.enums import ADRStatus


class ADRRepository:
    """Repository for managing Architecture Decision Records."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    async def create_adr(
        self,
        workspace_id: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        status: ADRStatus = ADRStatus.PROPOSED,
        alternatives_considered: Optional[List[str]] = None,
        related_adrs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> ADR:
        """Create a new ADR."""
        adr = ADR(
            id=str(uuid4()),
            workspace_id=workspace_id,
            title=title,
            status=status,
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives_considered=alternatives_considered or [],
            related_adrs=related_adrs or [],
            tags=tags or [],
            created_by=created_by,
            updated_by=updated_by,
        )
        
        self.db.add(adr)
        self.db.commit()
        self.db.refresh(adr)
        return adr
    
    async def get_adr(self, adr_id: str) -> Optional[ADR]:
        """Get ADR by ID."""
        return self.db.query(ADR).filter(
            ADR.id == adr_id
        ).first()
    
    async def list_adrs_by_workspace(
        self,
        workspace_id: str,
        status: Optional[ADRStatus] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ADR], int]:
        """List ADRs for a workspace with filtering and pagination."""
        query = self.db.query(ADR).filter(
            ADR.workspace_id == workspace_id
        )
        
        # Apply filters
        if status:
            query = query.filter(ADR.status == status)
        
        if tags:
            for tag in tags:
                query = query.filter(ADR.tags.contains([tag]))
        
        if search:
            search_filter = or_(
                ADR.title.contains(search),
                ADR.context.contains(search),
                ADR.decision.contains(search),
                ADR.consequences.contains(search)
            )
            query = query.filter(search_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        adrs = query.order_by(
            desc(ADR.created_at)
        ).offset(offset).limit(limit).all()
        
        return adrs, total
    
    async def update_adr(
        self,
        adr_id: str,
        **kwargs,
    ) -> Optional[ADR]:
        """Update ADR."""
        adr = await self.get_adr(adr_id)
        if not adr:
            return None
        
        for key, value in kwargs.items():
            if hasattr(adr, key):
                setattr(adr, key, value)
        
        adr.updated_at = func.now()
        self.db.commit()
        self.db.refresh(adr)
        return adr
    
    async def update_adr_status(
        self,
        adr_id: str,
        status: ADRStatus,
        updated_by: Optional[str] = None,
    ) -> Optional[ADR]:
        """Update ADR status."""
        adr = await self.get_adr(adr_id)
        if not adr:
            return None
        
        adr.status = status
        adr.updated_at = func.now()
        if updated_by:
            adr.updated_by = updated_by
        
        self.db.commit()
        self.db.refresh(adr)
        return adr
    
    async def delete_adr(self, adr_id: str) -> bool:
        """Delete ADR."""
        adr = await self.get_adr(adr_id)
        if not adr:
            return False
        
        self.db.delete(adr)
        self.db.commit()
        return True
    
    async def get_adr_timeline(
        self,
        workspace_id: str,
    ) -> List[Dict[str, Any]]:
        """Get ADR decision timeline for a workspace."""
        adrs = self.db.query(ADR).filter(
            ADR.workspace_id == workspace_id,
            ADR.status.in_([ADRStatus.ACCEPTED, ADRStatus.DEPRECATED, ADRStatus.SUPERSEDED])
        ).order_by(ADR.created_at).all()
        
        timeline = []
        for adr in adrs:
            timeline.append({
                "id": adr.id,
                "title": adr.title,
                "status": adr.status.value,
                "date": adr.created_at.isoformat(),
                "summary": adr.decision[:200] + "..." if len(adr.decision) > 200 else adr.decision,
            })
        
        return timeline
    
    async def get_related_adrs(
        self,
        adr_id: str,
    ) -> List[ADR]:
        """Get ADRs related to a specific ADR."""
        adr = await self.get_adr(adr_id)
        if not adr or not adr.related_adrs:
            return []
        
        related_ids = adr.related_adrs
        return self.db.query(ADR).filter(
            ADR.id.in_(related_ids)
        ).all()
    
    async def link_adr(
        self,
        source_adr_id: str,
        target_adr_id: str,
    ) -> bool:
        """Link two ADRs as related."""
        source_adr = await self.get_adr(source_adr_id)
        target_adr = await self.get_adr(target_adr_id)
        
        if not source_adr or not target_adr:
            return False
        
        # Add target to source's related ADRs
        if target_adr_id not in source_adr.related_adrs:
            source_adr.related_adrs.append(target_adr_id)
        
        # Add source to target's related ADRs
        if source_adr_id not in target_adr.related_adrs:
            target_adr.related_adrs.append(source_adr_id)
        
        source_adr.updated_at = func.now()
        target_adr.updated_at = func.now()
        
        self.db.commit()
        return True