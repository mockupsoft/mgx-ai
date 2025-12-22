"""Prompt template repository.

Data access for prompt templates used in code generation.
"""

from typing import List, Optional, Dict, Any
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from fastapi import HTTPException, status

from backend.db.models.entities import PromptTemplate
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility


class PromptTemplateRepository:
    """Repository for managing prompt templates."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    async def create_prompt_template(
        self,
        name: str,
        category: TemplateCategory,
        template: str,
        output_format: PromptOutputFormat,
        context_required: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        author: Optional[str] = None,
        version: str = "1.0.0",
        visibility: TemplateVisibility = TemplateVisibility.PUBLIC,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
    ) -> PromptTemplate:
        """Create a new prompt template."""
        # Check if name already exists
        existing = self.db.query(PromptTemplate).filter(
            PromptTemplate.name == name
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompt template with name '{name}' already exists"
            )
        
        prompt_template = PromptTemplate(
            id=str(uuid4()),
            name=name,
            category=category,
            template=template,
            context_required=context_required or [],
            output_format=output_format,
            examples=examples or [],
            author=author,
            version=version,
            visibility=visibility,
            tags=tags or [],
            created_by=created_by,
        )
        
        self.db.add(prompt_template)
        self.db.commit()
        self.db.refresh(prompt_template)
        return prompt_template
    
    async def get_prompt_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get prompt template by ID."""
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id
        ).first()
    
    async def get_prompt_template_by_name(self, name: str) -> Optional[PromptTemplate]:
        """Get prompt template by name."""
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.name == name
        ).first()
    
    async def list_prompt_templates(
        self,
        category: Optional[TemplateCategory] = None,
        output_format: Optional[PromptOutputFormat] = None,
        visibility: Optional[TemplateVisibility] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[PromptTemplate], int]:
        """List prompt templates with filtering and pagination."""
        query = self.db.query(PromptTemplate)
        
        # Apply filters
        if category:
            query = query.filter(PromptTemplate.category == category)
        
        if output_format:
            query = query.filter(PromptTemplate.output_format == output_format)
        
        if visibility:
            query = query.filter(PromptTemplate.visibility == visibility)
        
        if search:
            search_filter = or_(
                PromptTemplate.name.contains(search),
                PromptTemplate.template.contains(search),
                PromptTemplate.author.contains(search)
            )
            query = query.filter(search_filter)
        
        if tags:
            for tag in tags:
                query = query.filter(PromptTemplate.tags.contains([tag]))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        templates = query.order_by(
            desc(PromptTemplate.rating),
            desc(PromptTemplate.usage_count),
            desc(PromptTemplate.created_at)
        ).offset(offset).limit(limit).all()
        
        return templates, total
    
    async def update_prompt_template(
        self,
        template_id: str,
        **kwargs,
    ) -> Optional[PromptTemplate]:
        """Update prompt template."""
        template = await self.get_prompt_template(template_id)
        if not template:
            return None
        
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        template.updated_at = func.now()
        self.db.commit()
        self.db.refresh(template)
        return template
    
    async def delete_prompt_template(self, template_id: str) -> bool:
        """Delete prompt template."""
        template = await self.get_prompt_template(template_id)
        if not template:
            return False
        
        self.db.delete(template)
        self.db.commit()
        return True
    
    async def increment_usage(self, template_id: str) -> None:
        """Increment usage count for a template."""
        self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id
        ).update({
            PromptTemplate.usage_count: PromptTemplate.usage_count + 1,
            PromptTemplate.updated_at: func.now()
        })
        self.db.commit()
    
    async def rate_prompt_template(self, template_id: str, rating: float) -> Optional[PromptTemplate]:
        """Rate a prompt template."""
        template = await self.get_prompt_template(template_id)
        if not template:
            return None
        
        # Update rating (simple average for now)
        if template.rating > 0:
            template.rating = (template.rating + rating) / 2
        else:
            template.rating = rating
        
        self.db.commit()
        self.db.refresh(template)
        return template
    
    async def generate_prompt(
        self,
        template_id: str,
        variables: Dict[str, Any],
    ) -> str:
        """Generate a prompt from template with variables."""
        template = await self.get_prompt_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt template not found"
            )
        
        # Replace variables in template
        prompt = template.template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            prompt = prompt.replace(placeholder, str(value))
        
        return prompt