"""Template and Prompt Library Manager.

Main service for managing reusable templates, prompt templates, and ADRs.
"""

import re
from typing import List, Optional, Dict, Any, Union
from uuid import uuid4
from pathlib import Path

from backend.db.session import get_db
from .repositories.module_templates import ModuleTemplateRepository, FileTemplateRepository, ParameterRepository
from .repositories.prompt_templates import PromptTemplateRepository
from .repositories.adr_templates import ADRRepository
from backend.db.models.entities import ReusableModule, PromptTemplate, ADR
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility, ADRStatus


class TemplateManager:
    """Main service for managing template library."""
    
    def __init__(self, db_session=None):
        """Initialize template manager."""
        self.db = db_session or next(get_db())
        
        # Initialize repositories
        self.module_repo = ModuleTemplateRepository(self.db)
        self.file_repo = FileTemplateRepository(self.db)
        self.param_repo = ParameterRepository(self.db)
        self.prompt_repo = PromptTemplateRepository(self.db)
        self.adr_repo = ADRRepository(self.db)
    
    # Module Template Operations
    
    async def create_module_template(
        self,
        name: str,
        category: TemplateCategory,
        description: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ReusableModule:
        """Create a complete module template with files and parameters."""
        # Create the module
        module = await self.module_repo.create_module(
            name=name,
            category=category,
            description=description,
            **kwargs,
        )
        
        # Add file templates
        if files:
            for file_data in files:
                await self.file_repo.create_file_template(
                    module_id=module.id,
                    path=file_data["path"],
                    content=file_data["content"],
                    language=file_data.get("language"),
                    is_test=file_data.get("is_test", False),
                    is_config=file_data.get("is_config", False),
                    priority=file_data.get("priority", 0),
                )
        
        # Add parameters
        if parameters:
            for param_data in parameters:
                await self.param_repo.create_parameter(
                    module_id=module.id,
                    name=param_data["name"],
                    param_type=param_data["type"],
                    default_value=param_data.get("default"),
                    description=param_data.get("description"),
                    required=param_data.get("required", False),
                    validation_rules=param_data.get("validation", {}),
                )
        
        return module
    
    async def apply_module_template(
        self,
        module_id: str,
        parameters: Dict[str, Any],
        output_path: str,
    ) -> Dict[str, Any]:
        """Apply a module template with parameters to generate files."""
        # Get module with files and parameters
        module = await self.module_repo.get_module(module_id)
        if not module:
            raise ValueError(f"Module template {module_id} not found")
        
        # Get file templates
        files = await self.file_repo.get_files_by_module(module_id)
        
        # Get parameters for validation
        module_params = await self.param_repo.get_parameters_by_module(module_id)
        
        # Validate required parameters
        missing_params = []
        for param in module_params:
            if param.required and param.name not in parameters:
                missing_params.append(param.name)
        
        if missing_params:
            raise ValueError(f"Missing required parameters: {missing_params}")
        
        # Increment usage count
        await self.module_repo.increment_usage(module_id)
        
        # Render files
        rendered_files = []
        for file_template in files:
            # Apply parameter substitution
            content = self._render_template_content(
                file_template.content, 
                parameters
            )
            
            file_info = {
                "path": self._render_template_content(file_template.path, parameters),
                "content": content,
                "language": file_template.language,
                "is_test": file_template.is_test,
                "is_config": file_template.is_config,
                "priority": file_template.priority,
            }
            rendered_files.append(file_info)
        
        # Create output directory structure
        self._create_file_structure(output_path, rendered_files)
        
        return {
            "module_name": module.name,
            "files_generated": len(rendered_files),
            "files": rendered_files,
            "parameters_used": parameters,
        }
    
    async def list_module_templates(
        self,
        category: Optional[TemplateCategory] = None,
        tech_stack: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ReusableModule], int]:
        """List module templates with filtering."""
        return await self.module_repo.list_modules(
            category=category,
            tech_stack=tech_stack,
            search=search,
            tags=tags,
            limit=limit,
            offset=offset,
        )
    
    async def get_module_template_details(self, module_id: str) -> Dict[str, Any]:
        """Get complete module template details including files and parameters."""
        module = await self.module_repo.get_module(module_id)
        if not module:
            return None
        
        files = await self.file_repo.get_files_by_module(module_id)
        parameters = await self.param_repo.get_parameters_by_module(module_id)
        
        return {
            "module": module,
            "files": files,
            "parameters": parameters,
            "total_files": len(files),
            "total_parameters": len(parameters),
        }
    
    # Prompt Template Operations
    
    async def create_prompt_template(
        self,
        name: str,
        category: TemplateCategory,
        template: str,
        output_format: PromptOutputFormat,
        context_required: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        **kwargs,
    ) -> PromptTemplate:
        """Create a prompt template."""
        return await self.prompt_repo.create_prompt_template(
            name=name,
            category=category,
            template=template,
            output_format=output_format,
            context_required=context_required,
            examples=examples,
            **kwargs,
        )
    
    async def generate_prompt(
        self,
        template_id: str,
        variables: Dict[str, Any],
    ) -> str:
        """Generate a prompt from template with variables."""
        # Increment usage count
        await self.prompt_repo.increment_usage(template_id)
        
        return await self.prompt_repo.generate_prompt(template_id, variables)
    
    async def list_prompt_templates(
        self,
        category: Optional[TemplateCategory] = None,
        output_format: Optional[PromptOutputFormat] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[PromptTemplate], int]:
        """List prompt templates with filtering."""
        return await self.prompt_repo.list_prompt_templates(
            category=category,
            output_format=output_format,
            search=search,
            limit=limit,
            offset=offset,
        )
    
    # ADR Operations
    
    async def create_adr(
        self,
        workspace_id: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        status: ADRStatus = ADRStatus.PROPOSED,
        **kwargs,
    ) -> ADR:
        """Create a new ADR."""
        return await self.adr_repo.create_adr(
            workspace_id=workspace_id,
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            status=status,
            **kwargs,
        )
    
    async def list_workspace_adrs(
        self,
        workspace_id: str,
        status: Optional[ADRStatus] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ADR], int]:
        """List ADRs for a workspace."""
        return await self.adr_repo.list_adrs_by_workspace(
            workspace_id=workspace_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
    
    async def get_adr_timeline(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get ADR timeline for a workspace."""
        return await self.adr_repo.get_adr_timeline(workspace_id)
    
    # Template Marketplace
    
    async def get_popular_templates(
        self,
        template_type: str = "module",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get popular templates based on usage and rating."""
        if template_type == "module":
            modules, _ = await self.module_repo.list_modules(
                visibility=TemplateVisibility.PUBLIC,
                limit=limit,
            )
            return [{"type": "module", "data": module} for module in modules]
        elif template_type == "prompt":
            templates, _ = await self.prompt_repo.list_prompt_templates(
                visibility=TemplateVisibility.PUBLIC,
                limit=limit,
            )
            return [{"type": "prompt", "data": template} for template in templates]
        return []
    
    async def search_templates(
        self,
        query: str,
        template_type: str = "all",
        category: Optional[TemplateCategory] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search across all templates."""
        results = []
        
        if template_type in ["all", "module"]:
            modules, _ = await self.module_repo.list_modules(
                search=query,
                category=category,
                visibility=TemplateVisibility.PUBLIC,
                limit=limit // 2 if template_type == "all" else limit,
            )
            for module in modules:
                results.append({
                    "type": "module",
                    "id": module.id,
                    "name": module.name,
                    "description": module.description,
                    "category": module.category.value,
                    "rating": module.rating,
                    "usage_count": module.usage_count,
                })
        
        if template_type in ["all", "prompt"]:
            prompts, _ = await self.prompt_repo.list_prompt_templates(
                search=query,
                category=category,
                visibility=TemplateVisibility.PUBLIC,
                limit=limit // 2 if template_type == "all" else limit,
            )
            for prompt in prompts:
                results.append({
                    "type": "prompt",
                    "id": prompt.id,
                    "name": prompt.name,
                    "description": prompt.template[:200] + "...",
                    "category": prompt.category.value,
                    "output_format": prompt.output_format.value,
                    "rating": prompt.rating,
                    "usage_count": prompt.usage_count,
                })
        
        return results[:limit]
    
    # Private helper methods
    
    def _render_template_content(self, content: str, parameters: Dict[str, Any]) -> str:
        """Render template content with parameter substitution."""
        rendered = content
        for key, value in parameters.items():
            placeholder = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder, str(value))
        return rendered
    
    def _create_file_structure(self, output_path: str, files: List[Dict[str, Any]]) -> None:
        """Create file structure from rendered files."""
        base_path = Path(output_path)
        base_path.mkdir(parents=True, exist_ok=True)
        
        for file_info in files:
            file_path = base_path / file_info["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w") as f:
                f.write(file_info["content"])


class TemplateEnhancer:
    """Service for enhancing generated projects with templates."""
    
    def __init__(self, db_session=None):
        """Initialize template enhancer."""
        self.db = db_session or next(get_db())
        self.template_manager = TemplateManager(self.db)
    
    async def apply_templates_to_project(
        self,
        project_id: str,
        modules: List[str],
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Apply module templates to a generated project."""
        results = []
        
        for module_name in modules:
            # Get module template
            module = await self.template_manager.module_repo.get_module_by_name(module_name)
            if not module:
                continue
            
            # Get module-specific parameters
            module_params = parameters.get(module_name, {}) if parameters else {}
            
            # Apply template
            try:
                result = await self.template_manager.apply_module_template(
                    module_id=module.id,
                    parameters=module_params,
                    output_path=f"/tmp/project_{project_id}/{module_name}",
                )
                results.append({
                    "module": module_name,
                    "success": True,
                    "files_generated": result["files_generated"],
                })
            except Exception as e:
                results.append({
                    "module": module_name,
                    "success": False,
                    "error": str(e),
                })
        
        return {
            "project_id": project_id,
            "templates_applied": len(modules),
            "results": results,
        }