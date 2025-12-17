# -*- coding: utf-8 -*-
"""Project Generator API Router."""

from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import (
    ProjectTemplate, 
    GeneratedProject, 
    TemplateFeature,
    StackType, 
    TemplateFeatureType,
    ProjectGenerationStatus
)
from backend.services.generator.generator import ProjectGenerator, ProjectGenerationError
from backend.services.generator.template_manager import TemplateManager

# Request/Response Schemas
class TemplateListResponse(BaseModel):
    """Response for template listing."""
    id: str
    name: str
    description: Optional[str]
    stack: str
    version: str
    status: str
    author: Optional[str]
    default_features: List[str]
    supported_features: List[str]
    environment_variables: List[str]
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ProjectGenerationRequest(BaseModel):
    """Request for project generation."""
    project_name: str
    stack: str
    features: List[str] = []
    custom_settings: Dict[str, Any] = {}
    description: Optional[str] = None


class ProjectGenerationResponse(BaseModel):
    """Response for project generation."""
    generation_id: str
    status: str
    progress: int
    project_name: str
    template_id: str
    files_created: Optional[int] = None
    project_path: Optional[str] = None
    repository_url: Optional[str] = None
    error_message: Optional[str] = None
    build_successful: Optional[bool] = None
    tests_passed: Optional[bool] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class GenerationStatusResponse(BaseModel):
    """Response for generation status."""
    generation_id: str
    status: str
    progress: int
    project_name: str
    error_message: Optional[str] = None
    files_created: Optional[int] = None
    build_successful: Optional[bool] = None
    completed_at: Optional[datetime] = None


class FeatureListResponse(BaseModel):
    """Response for feature listing."""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    feature_type: str
    compatible_stacks: List[str]
    dependencies: List[str]
    version: str
    author: Optional[str]
    tags: List[str]
    usage_count: int


# Initialize router
router = APIRouter(prefix="/api/generator", tags=["Project Generator"])


@router.get("/templates", response_model=List[TemplateListResponse])
async def list_templates(
    stack: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available project templates."""
    try:
        template_manager = TemplateManager(db)
        
        # Convert stack string to StackType if provided
        stack_type = None
        if stack:
            try:
                stack_type = StackType(stack)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid stack type: {stack}. Valid options: express_ts, fastapi, nextjs, laravel"
                )
        
        templates = await template_manager.list_templates(stack_type)
        return templates
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list templates: {str(e)}"
        )


@router.get("/templates/{template_id}", response_model=TemplateListResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific template by ID."""
    try:
        template_manager = TemplateManager(db)
        template = await template_manager.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found"
            )
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template: {str(e)}"
        )


@router.post("/generate", response_model=ProjectGenerationResponse)
async def generate_project(
    request: ProjectGenerationRequest,
    background_tasks: BackgroundTasks,
    workspace_id: UUID,  # This would come from authentication
    current_user_id: Optional[str] = None,  # This would come from authentication
    db: Session = Depends(get_db)
):
    """Start a new project generation."""
    try:
        # Validate stack type
        try:
            stack_type = StackType(request.stack)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stack type: {request.stack}. Valid options: express_ts, fastapi, nextjs, laravel"
            )
        
        # Initialize generator
        generator = ProjectGenerator(db)
        
        # Start generation in background
        background_tasks.add_task(
            generator.generate_project,
            workspace_id=workspace_id,
            project_name=request.project_name,
            stack=request.stack,
            features=request.features,
            custom_settings=request.custom_settings,
            description=request.description,
            generated_by=current_user_id
        )
        
        # Return initial response (generation will start in background)
        return {
            "generation_id": "pending",  # Will be updated when generation starts
            "status": "pending",
            "progress": 0,
            "project_name": request.project_name,
            "template_id": "",  # Will be updated when template is found
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start project generation: {str(e)}"
        )


@router.get("/generate/{generation_id}/status", response_model=GenerationStatusResponse)
async def get_generation_status(
    generation_id: str,
    db: Session = Depends(get_db)
):
    """Get the status of a project generation."""
    try:
        generator = ProjectGenerator(db)
        generation = await generator.get_generation_status(generation_id)
        
        if not generation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation with ID {generation_id} not found"
            )
        
        return {
            "generation_id": generation.id,
            "status": generation.status.value,
            "progress": generation.progress,
            "project_name": generation.name,
            "error_message": generation.error_message,
            "files_created": generation.files_created,
            "build_successful": generation.build_successful,
            "completed_at": generation.completed_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get generation status: {str(e)}"
        )


@router.get("/generations", response_model=List[ProjectGenerationResponse])
async def list_generations(
    workspace_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List project generations for a workspace."""
    try:
        generator = ProjectGenerator(db)
        generations = await generator.list_generations(workspace_id, limit, offset)
        
        return [
            {
                "generation_id": gen.id,
                "status": gen.status.value,
                "progress": gen.progress,
                "project_name": gen.name,
                "template_id": gen.template_id,
                "files_created": gen.files_created,
                "project_path": gen.project_path,
                "repository_url": gen.repository_url,
                "error_message": gen.error_message,
                "build_successful": gen.build_successful,
                "tests_passed": gen.tests_passed,
                "completed_at": gen.completed_at,
                "created_at": gen.created_at,
                "updated_at": gen.updated_at
            }
            for gen in generations
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list generations: {str(e)}"
        )


@router.get("/features", response_model=List[FeatureListResponse])
async def list_features(
    stack: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available template features."""
    try:
        template_manager = TemplateManager(db)
        
        # Convert stack string to StackType if provided
        stack_type = None
        if stack:
            try:
                stack_type = StackType(stack)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid stack type: {stack}. Valid options: express_ts, fastapi, nextjs, laravel"
                )
        
        features = await template_manager.list_features(stack_type)
        return features
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list features: {str(e)}"
        )


@router.get("/features/{feature_name}", response_model=FeatureListResponse)
async def get_feature(
    feature_name: str,
    db: Session = Depends(get_db)
):
    """Get a specific feature by name."""
    try:
        template_manager = TemplateManager(db)
        feature = await template_manager.get_feature(feature_name)
        
        if not feature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature with name {feature_name} not found"
            )
        
        return feature
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feature: {str(e)}"
        )


@router.get("/stacks")
async def list_available_stacks():
    """List all available stack types."""
    return [
        {
            "id": stack.value,
            "name": stack.value.replace('_', '-').title(),
            "description": get_stack_description(stack.value)
        }
        for stack in StackType
    ]


def get_stack_description(stack: str) -> str:
    """Get description for a stack type."""
    descriptions = {
        "express_ts": "Express.js with TypeScript - RESTful API server",
        "fastapi": "FastAPI Python framework - Modern Python web framework",
        "nextjs": "Next.js React framework - Full-stack React framework",
        "laravel": "Laravel PHP framework - PHP web application framework"
    }
    return descriptions.get(stack, "Unknown stack type")


@router.get("/stats")
async def get_generator_stats(db: Session = Depends(get_db)):
    """Get generator usage statistics."""
    try:
        template_count = db.query(ProjectTemplate).count()
        feature_count = db.query(TemplateFeature).count()
        generation_count = db.query(GeneratedProject).count()
        
        # Get recent generations
        recent_generations = db.query(GeneratedProject).order_by(
            GeneratedProject.created_at.desc()
        ).limit(5).all()
        
        return {
            "template_count": template_count,
            "feature_count": feature_count,
            "generation_count": generation_count,
            "recent_generations": [
                {
                    "id": gen.id,
                    "name": gen.name,
                    "status": gen.status.value,
                    "created_at": gen.created_at
                }
                for gen in recent_generations
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get generator stats: {str(e)}"
        )