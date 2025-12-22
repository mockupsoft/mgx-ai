"""Templates API router.

Provides endpoints for managing reusable templates, prompt templates, and ADRs.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from backend.db.session import get_db
from backend.services.templates.template_manager import TemplateManager, TemplateEnhancer
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility, ADRStatus

from backend.schemas import (
    ModuleTemplateCreateRequest,
    ModuleTemplateResponse,
    ModuleTemplateDetailResponse,
    ApplyModuleTemplateRequest,
    ApplyModuleTemplateResponse,
    PromptTemplateCreateRequest,
    PromptTemplateResponse,
    GeneratePromptRequest,
    GeneratePromptResponse,
    ADRCreateRequest,
    ADRResponse,
    ADRTimelineResponse,
    TemplateSearchRequest,
    TemplateSearchResponse,
    TemplateListResponse,
    RateTemplateRequest,
    RateTemplateResponse,
    TemplateEnhancementRequest,
    TemplateEnhancementResponse,
    MarketplaceResponse,
)


router = APIRouter(prefix="/api/templates", tags=["templates"])


def get_template_manager(db: Session = Depends(get_db)) -> TemplateManager:
    """Get template manager instance."""
    return TemplateManager(db)


def get_template_enhancer(db: Session = Depends(get_db)) -> TemplateEnhancer:
    """Get template enhancer instance."""
    return TemplateEnhancer(db)


# Module Template Endpoints

@router.get("/modules", response_model=TemplateListResponse)
async def list_module_templates(
    category: Optional[TemplateCategory] = None,
    tech_stack: Optional[str] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    manager: TemplateManager = Depends(get_template_manager),
):
    """List module templates with filtering."""
    try:
        modules, total = await manager.list_module_templates(
            category=category,
            tech_stack=tech_stack,
            search=search,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = []
        for module in modules:
            items.append(ModuleTemplateResponse(
                id=module.id,
                name=module.name,
                category=module.category.value if hasattr(module.category, 'value') else module.category,
                description=module.description,
                version=module.version,
                tech_stacks=module.tech_stacks,
                dependencies=module.dependencies,
                documentation=module.documentation,
                params=module.params,
                author=module.author,
                usage_count=module.usage_count,
                rating=module.rating,
                visibility=module.visibility.value if hasattr(module.visibility, 'value') else module.visibility,
                is_active=module.is_active,
                tags=module.tags,
                created_at=module.created_at,
                updated_at=module.updated_at,
                created_by=module.created_by,
                updated_by=module.updated_by,
            ))
        
        return TemplateListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            template_type="module"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/modules", response_model=ModuleTemplateResponse)
async def create_module_template(
    request: ModuleTemplateCreateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Create a new module template."""
    try:
        module = await manager.create_module_template(
            name=request.name,
            category=TemplateCategory(request.category),
            description=request.description,
            version=request.version,
            tech_stacks=request.tech_stacks,
            dependencies=request.dependencies,
            documentation=request.documentation,
            params=request.params,
            author=request.author,
            visibility=TemplateVisibility(request.visibility),
            tags=request.tags,
            files=request.files,
            parameters=request.parameters,
        )
        
        return ModuleTemplateResponse(
            id=module.id,
            name=module.name,
            category=module.category.value if hasattr(module.category, 'value') else module.category,
            description=module.description,
            version=module.version,
            tech_stacks=module.tech_stacks,
            dependencies=module.dependencies,
            documentation=module.documentation,
            params=module.params,
            author=module.author,
            usage_count=module.usage_count,
            rating=module.rating,
            visibility=module.visibility.value if hasattr(module.visibility, 'value') else module.visibility,
            is_active=module.is_active,
            tags=module.tags,
            created_at=module.created_at,
            updated_at=module.updated_at,
            created_by=module.created_by,
            updated_by=module.updated_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{module_id}", response_model=ModuleTemplateDetailResponse)
async def get_module_template(
    module_id: str,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Get module template details including files and parameters."""
    try:
        details = await manager.get_module_template_details(module_id)
        if not details:
            raise HTTPException(status_code=404, detail="Module template not found")
        
        module = details["module"]
        files = details["files"]
        parameters = details["parameters"]
        
        # Convert to response format
        file_responses = []
        for file_template in files:
            from backend.schemas import FileTemplateResponse
            file_responses.append(FileTemplateResponse(
                id=file_template.id,
                module_id=file_template.module_id,
                path=file_template.path,
                content=file_template.content,
                language=file_template.language,
                is_test=file_template.is_test,
                is_config=file_template.is_config,
                priority=file_template.priority,
                created_at=file_template.created_at,
                updated_at=file_template.updated_at,
            ))
        
        param_responses = []
        for param in parameters:
            from backend.schemas import ParameterResponse
            param_responses.append(ParameterResponse(
                id=param.id,
                module_id=param.module_id,
                name=param.name,
                param_type=param.param_type,
                default_value=param.default_value,
                description=param.description,
                required=param.required,
                validation_rules=param.validation_rules,
                created_at=param.created_at,
                updated_at=param.updated_at,
            ))
        
        return ModuleTemplateDetailResponse(
            module=ModuleTemplateResponse(
                id=module.id,
                name=module.name,
                category=module.category.value if hasattr(module.category, 'value') else module.category,
                description=module.description,
                version=module.version,
                tech_stacks=module.tech_stacks,
                dependencies=module.dependencies,
                documentation=module.documentation,
                params=module.params,
                author=module.author,
                usage_count=module.usage_count,
                rating=module.rating,
                visibility=module.visibility.value if hasattr(module.visibility, 'value') else module.visibility,
                is_active=module.is_active,
                tags=module.tags,
                created_at=module.created_at,
                updated_at=module.updated_at,
                created_by=module.created_by,
                updated_by=module.updated_by,
            ),
            files=file_responses,
            parameters=param_responses,
            total_files=len(file_responses),
            total_parameters=len(param_responses),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/modules/{module_id}/apply", response_model=ApplyModuleTemplateResponse)
async def apply_module_template(
    module_id: str,
    request: ApplyModuleTemplateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Apply a module template to a project."""
    try:
        result = await manager.apply_module_template(
            module_id=module_id,
            parameters=request.parameters,
            output_path=f"/tmp/projects/{request.project_id}",
        )
        
        return ApplyModuleTemplateResponse(
            module_name=result["module_name"],
            files_generated=result["files_generated"],
            files=result["files"],
            parameters_used=result["parameters_used"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Prompt Template Endpoints

@router.get("/prompts", response_model=TemplateListResponse)
async def list_prompt_templates(
    category: Optional[TemplateCategory] = None,
    output_format: Optional[PromptOutputFormat] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    manager: TemplateManager = Depends(get_template_manager),
):
    """List prompt templates with filtering."""
    try:
        templates, total = await manager.list_prompt_templates(
            category=category,
            output_format=output_format,
            search=search,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = []
        for template in templates:
            items.append(PromptTemplateResponse(
                id=template.id,
                name=template.name,
                category=template.category.value if hasattr(template.category, 'value') else template.category,
                template=template.template,
                context_required=template.context_required,
                output_format=template.output_format.value if hasattr(template.output_format, 'value') else template.output_format,
                examples=template.examples,
                created_by=template.created_by,
                version=template.version,
                usage_count=template.usage_count,
                rating=template.rating,
                visibility=template.visibility.value if hasattr(template.visibility, 'value') else template.visibility,
                tags=template.tags,
                created_at=template.created_at,
                updated_at=template.updated_at,
            ))
        
        return TemplateListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            template_type="prompt"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts", response_model=PromptTemplateResponse)
async def create_prompt_template(
    request: PromptTemplateCreateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Create a new prompt template."""
    try:
        template = await manager.create_prompt_template(
            name=request.name,
            category=TemplateCategory(request.category),
            template=request.template,
            output_format=PromptOutputFormat(request.output_format),
            context_required=request.context_required,
            examples=request.examples,
            author=request.author,
            version=request.version,
            visibility=TemplateVisibility(request.visibility),
            tags=request.tags,
        )
        
        return PromptTemplateResponse(
            id=template.id,
            name=template.name,
            category=template.category.value if hasattr(template.category, 'value') else template.category,
            template=template.template,
            context_required=template.context_required,
            output_format=template.output_format.value if hasattr(template.output_format, 'value') else template.output_format,
            examples=template.examples,
            created_by=template.created_by,
            version=template.version,
            usage_count=template.usage_count,
            rating=template.rating,
            visibility=template.visibility.value if hasattr(template.visibility, 'value') else template.visibility,
            tags=template.tags,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/{template_id}/generate", response_model=GeneratePromptResponse)
async def generate_prompt(
    template_id: str,
    request: GeneratePromptRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Generate a prompt from template with variables."""
    try:
        prompt = await manager.generate_prompt(template_id, request.variables)
        
        return GeneratePromptResponse(
            prompt=prompt,
            template_id=template_id,
            variables_used=request.variables,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ADR Endpoints

@router.get("/workspaces/{workspace_id}/adrs", response_model=List[ADRResponse])
async def list_workspace_adrs(
    workspace_id: str,
    status: Optional[ADRStatus] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    manager: TemplateManager = Depends(get_template_manager),
):
    """List ADRs for a workspace."""
    try:
        adrs, total = await manager.list_workspace_adrs(
            workspace_id=workspace_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
        
        # Convert to response format
        items = []
        for adr in adrs:
            items.append(ADRResponse(
                id=adr.id,
                workspace_id=adr.workspace_id,
                title=adr.title,
                status=adr.status.value if hasattr(adr.status, 'value') else adr.status,
                context=adr.context,
                decision=adr.decision,
                consequences=adr.consequences,
                alternatives_considered=adr.alternatives_considered,
                related_adrs=adr.related_adrs,
                tags=adr.tags,
                created_by=adr.created_by,
                updated_by=adr.updated_by,
                created_at=adr.created_at,
                updated_at=adr.updated_at,
            ))
        
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspaces/{workspace_id}/adrs", response_model=ADRResponse)
async def create_adr(
    workspace_id: str,
    request: ADRCreateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Create a new ADR."""
    try:
        adr = await manager.create_adr(
            workspace_id=workspace_id,
            title=request.title,
            context=request.context,
            decision=request.decision,
            consequences=request.consequences,
            status=ADRStatus(request.status),
            alternatives_considered=request.alternatives_considered,
            related_adrs=request.related_adrs,
            tags=request.tags,
        )
        
        return ADRResponse(
            id=adr.id,
            workspace_id=adr.workspace_id,
            title=adr.title,
            status=adr.status.value if hasattr(adr.status, 'value') else adr.status,
            context=adr.context,
            decision=adr.decision,
            consequences=adr.consequences,
            alternatives_considered=adr.alternatives_considered,
            related_adrs=adr.related_adrs,
            tags=adr.tags,
            created_by=adr.created_by,
            updated_by=adr.updated_by,
            created_at=adr.created_at,
            updated_at=adr.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces/{workspace_id}/adrs/timeline", response_model=ADRTimelineResponse)
async def get_adr_timeline(
    workspace_id: str,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Get ADR timeline for a workspace."""
    try:
        timeline = await manager.get_adr_timeline(workspace_id)
        return ADRTimelineResponse(timeline=timeline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Template Marketplace & Search

@router.get("/search", response_model=TemplateSearchResponse)
async def search_templates(
    query: str = Query(..., min_length=1),
    template_type: str = Query("all", regex="^(all|module|prompt)$"),
    category: Optional[TemplateCategory] = None,
    limit: int = Query(20, ge=1, le=100),
    manager: TemplateManager = Depends(get_template_manager),
):
    """Search across all templates."""
    try:
        results = await manager.search_templates(
            query=query,
            template_type=template_type,
            category=category,
            limit=limit,
        )
        
        # Convert to response format
        search_results = []
        for result in results:
            from schemas import TemplateSearchResult
            search_results.append(TemplateSearchResult(
                type=result["type"],
                id=result["id"],
                name=result["name"],
                description=result["description"],
                category=result["category"],
                rating=result["rating"],
                usage_count=result["usage_count"],
            ))
        
        return TemplateSearchResponse(
            results=search_results,
            total=len(search_results),
            query=query,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace", response_model=MarketplaceResponse)
async def get_marketplace(
    limit: int = Query(10, ge=1, le=50),
    manager: TemplateManager = Depends(get_template_manager),
):
    """Get popular templates for marketplace."""
    try:
        popular_templates = await manager.get_popular_templates(limit=limit)
        
        modules = []
        prompts = []
        
        for template in popular_templates:
            if template["type"] == "module":
                data = template["data"]
                from schemas import MarketplaceTemplate
                modules.append(MarketplaceTemplate(
                    id=data.id,
                    name=data.name,
                    description=data.description or "",
                    category=data.category.value if hasattr(data.category, 'value') else data.category,
                    author=data.author,
                    version=data.version,
                    rating=data.rating,
                    usage_count=data.usage_count,
                    tags=data.tags,
                    visibility=data.visibility.value if hasattr(data.visibility, 'value') else data.visibility,
                ))
            elif template["type"] == "prompt":
                data = template["data"]
                prompts.append(MarketplaceTemplate(
                    id=data.id,
                    name=data.name,
                    description=data.template[:200] + "...",
                    category=data.category.value if hasattr(data.category, 'value') else data.category,
                    author=data.author,
                    version=data.version,
                    rating=data.rating,
                    usage_count=data.usage_count,
                    tags=data.tags,
                    visibility=data.visibility.value if hasattr(data.visibility, 'value') else data.visibility,
                ))
        
        categories = [cat.value for cat in TemplateCategory]
        
        return MarketplaceResponse(
            popular_modules=modules,
            popular_prompts=prompts,
            categories=categories,
            total_templates=len(modules) + len(prompts),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Template Enhancement

@router.post("/enhance", response_model=TemplateEnhancementResponse)
async def enhance_project_with_templates(
    request: TemplateEnhancementRequest,
    enhancer: TemplateEnhancer = Depends(get_template_enhancer),
):
    """Enhance a project with module templates."""
    try:
        result = await enhancer.apply_templates_to_project(
            project_id=request.project_id,
            modules=request.modules,
            parameters=request.parameters,
        )
        
        # Convert to response format
        enhancement_results = []
        for enhancement_result in result["results"]:
            from schemas import TemplateEnhancementResult
            enhancement_results.append(TemplateEnhancementResult(
                module=enhancement_result["module"],
                success=enhancement_result["success"],
                files_generated=enhancement_result.get("files_generated"),
                error=enhancement_result.get("error"),
            ))
        
        return TemplateEnhancementResponse(
            project_id=result["project_id"],
            templates_applied=result["templates_applied"],
            results=enhancement_results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Template Rating

@router.post("/modules/{module_id}/rate", response_model=RateTemplateResponse)
async def rate_module_template(
    module_id: str,
    request: RateTemplateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Rate a module template."""
    try:
        updated_module = await manager.module_repo.rate_module(module_id, request.rating)
        if not updated_module:
            raise HTTPException(status_code=404, detail="Module template not found")
        
        return RateTemplateResponse(
            template_id=module_id,
            template_type="module",
            new_rating=updated_module.rating,
            previous_rating=(updated_module.rating * 2 - request.rating),  # Calculate previous
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/{template_id}/rate", response_model=RateTemplateResponse)
async def rate_prompt_template(
    template_id: str,
    request: RateTemplateRequest,
    manager: TemplateManager = Depends(get_template_manager),
):
    """Rate a prompt template."""
    try:
        updated_template = await manager.prompt_repo.rate_prompt_template(template_id, request.rating)
        if not updated_template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        
        return RateTemplateResponse(
            template_id=template_id,
            template_type="prompt",
            new_rating=updated_template.rating,
            previous_rating=(updated_template.rating * 2 - request.rating),  # Calculate previous
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))