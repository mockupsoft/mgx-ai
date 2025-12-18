"""Module template repository.

Data access for reusable module templates.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from fastapi import HTTPException, status

from backend.db.models.entities import ReusableModule, FileTemplate, Parameter
from backend.db.models.enums import TemplateCategory, TemplateVisibility


class ModuleTemplateRepository:
    """Repository for managing reusable module templates."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    async def create_module(
        self,
        name: str,
        category: TemplateCategory,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tech_stacks: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        documentation: Optional[str] = None,
        params: Optional[List[Dict[str, Any]]] = None,
        author: Optional[str] = None,
        visibility: TemplateVisibility = TemplateVisibility.PRIVATE,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> ReusableModule:
        """Create a new module template."""
        # Check if name already exists
        existing = self.db.query(ReusableModule).filter(
            ReusableModule.name == name
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module template with name '{name}' already exists"
            )
        
        module = ReusableModule(
            id=str(uuid4()),
            name=name,
            category=category,
            description=description,
            version=version,
            tech_stacks=tech_stacks or [],
            dependencies=dependencies or [],
            documentation=documentation,
            params=params or [],
            author=author,
            visibility=visibility,
            tags=tags or [],
            created_by=created_by,
            updated_by=updated_by,
        )
        
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return module
    
    async def get_module(self, module_id: str) -> Optional[ReusableModule]:
        """Get module template by ID."""
        return self.db.query(ReusableModule).filter(
            ReusableModule.id == module_id
        ).first()
    
    async def get_module_by_name(self, name: str) -> Optional[ReusableModule]:
        """Get module template by name."""
        return self.db.query(ReusableModule).filter(
            ReusableModule.name == name
        ).first()
    
    async def list_modules(
        self,
        category: Optional[TemplateCategory] = None,
        visibility: Optional[TemplateVisibility] = None,
        tech_stack: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ReusableModule], int]:
        """List module templates with filtering and pagination."""
        query = self.db.query(ReusableModule)
        
        # Apply filters
        if category:
            query = query.filter(ReusableModule.category == category)
        
        if visibility:
            query = query.filter(ReusableModule.visibility == visibility)
        
        if tech_stack:
            query = query.filter(
                ReusableModule.tech_stacks.contains([tech_stack])
            )
        
        if search:
            search_filter = or_(
                ReusableModule.name.contains(search),
                ReusableModule.description.contains(search),
                ReusableModule.author.contains(search)
            )
            query = query.filter(search_filter)
        
        if tags:
            for tag in tags:
                query = query.filter(ReusableModule.tags.contains([tag]))
        
        # Active modules only
        query = query.filter(ReusableModule.is_active == True)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        modules = query.order_by(
            desc(ReusableModule.rating),
            desc(ReusableModule.usage_count),
            desc(ReusableModule.created_at)
        ).offset(offset).limit(limit).all()
        
        return modules, total
    
    async def update_module(
        self,
        module_id: str,
        **kwargs,
    ) -> Optional[ReusableModule]:
        """Update module template."""
        module = await self.get_module(module_id)
        if not module:
            return None
        
        for key, value in kwargs.items():
            if hasattr(module, key):
                setattr(module, key, value)
        
        module.updated_at = func.now()
        self.db.commit()
        self.db.refresh(module)
        return module
    
    async def delete_module(self, module_id: str) -> bool:
        """Delete module template (soft delete)."""
        module = await self.get_module(module_id)
        if not module:
            return False
        
        module.is_active = False
        self.db.commit()
        return True
    
    async def increment_usage(self, module_id: str) -> None:
        """Increment usage count for a module."""
        self.db.query(ReusableModule).filter(
            ReusableModule.id == module_id
        ).update({
            ReusableModule.usage_count: ReusableModule.usage_count + 1,
            ReusableModule.updated_at: func.now()
        })
        self.db.commit()
    
    async def rate_module(self, module_id: str, rating: float) -> Optional[ReusableModule]:
        """Rate a module template."""
        module = await self.get_module(module_id)
        if not module:
            return None
        
        # Update rating (simple average for now)
        if module.rating > 0:
            module.rating = (module.rating + rating) / 2
        else:
            module.rating = rating
        
        self.db.commit()
        self.db.refresh(module)
        return module


class FileTemplateRepository:
    """Repository for managing file templates."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    async def create_file_template(
        self,
        module_id: str,
        path: str,
        content: str,
        language: Optional[str] = None,
        is_test: bool = False,
        is_config: bool = False,
        priority: int = 0,
    ) -> FileTemplate:
        """Create a new file template."""
        file_template = FileTemplate(
            id=str(uuid4()),
            module_id=module_id,
            path=path,
            content=content,
            language=language,
            is_test=is_test,
            is_config=is_config,
            priority=priority,
        )
        
        self.db.add(file_template)
        self.db.commit()
        self.db.refresh(file_template)
        return file_template
    
    async def get_files_by_module(self, module_id: str) -> List[FileTemplate]:
        """Get all file templates for a module."""
        return self.db.query(FileTemplate).filter(
            FileTemplate.module_id == module_id
        ).order_by(FileTemplate.priority.desc()).all()
    
    async def get_file_template(self, file_id: str) -> Optional[FileTemplate]:
        """Get file template by ID."""
        return self.db.query(FileTemplate).filter(
            FileTemplate.id == file_id
        ).first()


class ParameterRepository:
    """Repository for managing template parameters."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    async def create_parameter(
        self,
        module_id: str,
        name: str,
        param_type: str,
        default_value: Optional[Any] = None,
        description: Optional[str] = None,
        required: bool = False,
        validation_rules: Optional[Dict[str, Any]] = None,
    ) -> Parameter:
        """Create a new parameter."""
        parameter = Parameter(
            id=str(uuid4()),
            module_id=module_id,
            name=name,
            param_type=param_type,
            default_value=default_value,
            description=description,
            required=required,
            validation_rules=validation_rules or {},
        )
        
        self.db.add(parameter)
        self.db.commit()
        self.db.refresh(parameter)
        return parameter
    
    async def get_parameters_by_module(self, module_id: str) -> List[Parameter]:
        """Get all parameters for a module."""
        return self.db.query(Parameter).filter(
            Parameter.module_id == module_id
        ).all()
    
    async def get_parameter(self, parameter_id: str) -> Optional[Parameter]:
        """Get parameter by ID."""
        return self.db.query(Parameter).filter(
            Parameter.id == parameter_id
        ).first()