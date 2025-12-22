# -*- coding: utf-8 -*-
"""Knowledge Service Schemas.

Data structures and schemas used across the knowledge service.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from backend.db.models.entities import KnowledgeItem
from backend.db.models.enums import KnowledgeCategory

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
