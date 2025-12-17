# -*- coding: utf-8 -*-
"""File generation engine for project templates."""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional


class FileEngine:
    """Handles generation of project files from templates."""

    def __init__(self, templates_path: Optional[Path] = None):
        self.templates_path = templates_path or Path(__file__).parent.parent / "templates"

    async def generate_file(
        self,
        project_path: Path,
        relative_path: str,
        template_name: str,
        custom_settings: Dict[str, Any]
    ):
        """Generate a single file from a template."""
        template_path = self._find_template(template_name)
        
        if not template_path or not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_name}")
        
        # Read template content
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        # Process template variables
        processed_content = self._process_template(template_content, custom_settings)
        
        # Create file in project
        target_path = project_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, 'w') as f:
            f.write(processed_content)

    def _find_template(self, template_name: str) -> Optional[Path]:
        """Find a template file by name across all template directories."""
        # Search in template subdirectories
        for template_dir in self.templates_path.iterdir():
            if template_dir.is_dir():
                template_path = template_dir / template_name
                if template_path.exists():
                    return template_path
        
        # If not found in subdirectories, check templates root
        template_path = self.templates_path / template_name
        if template_path.exists():
            return template_path
            
        return None

    def _process_template(self, template_content: str, custom_settings: Dict[str, Any]) -> str:
        """Process template variables and replace them with actual values."""
        processed = template_content
        
        # Replace common variables
        replacements = {
            "{{PROJECT_NAME}}": custom_settings.get("project_name", "my-project"),
            "{{PROJECT_VERSION}}": custom_settings.get("version", "1.0.0"),
            "{{DESCRIPTION}}": custom_settings.get("description", ""),
            "{{AUTHOR}}": custom_settings.get("author", ""),
            "{{PORT}}": str(custom_settings.get("port", 3000)),
            "{{NODE_ENV}}": custom_settings.get("node_env", "development"),
            "{{DATABASE_URL}}": custom_settings.get("database_url", ""),
            "{{LOG_LEVEL}}": custom_settings.get("log_level", "info"),
            "{{API_PREFIX}}": custom_settings.get("api_prefix", "/api"),
            "{{JWT_SECRET}}": custom_settings.get("jwt_secret", ""),
            "{{CORS_ORIGIN}}": custom_settings.get("cors_origin", "*"),
        }
        
        for placeholder, value in replacements.items():
            processed = processed.replace(placeholder, str(value))
        
        # Replace custom settings
        for key, value in custom_settings.items():
            placeholder = f"{{{{{key.upper()}}}}}"
            processed = processed.replace(placeholder, str(value))
        
        # Process conditional blocks
        processed = self._process_conditionals(processed, custom_settings)
        
        return processed

    def _process_conditionals(self, content: str, custom_settings: Dict[str, Any]) -> str:
        """Process conditional blocks in templates."""
        # Simple conditional processing for common patterns
        
        # Authentication feature
        if custom_settings.get("features", {}).get("auth", False):
            auth_imports = [
                "import jwt from 'jsonwebtoken';",
                "import bcrypt from 'bcrypt';",
                "import { authenticate, requireAuth } from './middleware/auth';"
            ]
            
            for auth_import in auth_imports:
                if f"{{{{#IF_AUTH}}}}}" in content and auth_import not in content:
                    content = content.replace(
                        f"{{{{#IF_AUTH}}}}}" + auth_import + "\n{{{{/IF_AUTH}}}}",
                        auth_import
                    )
        
        # Database feature
        if custom_settings.get("features", {}).get("database", False):
            db_imports = [
                "import { sequelize } from './database/connection';",
                "import { initializeModels } from './database/models';"
            ]
            
            for db_import in db_imports:
                if f"{{{{#IF_DATABASE}}}}}" in content and db_import not in content:
                    content = content.replace(
                        f"{{{{#IF_DATABASE}}}}}" + db_import + "\n{{{{/IF_DATABASE}}}}",
                        db_import
                    )
        
        # Remove unused conditional blocks
        content = re.sub(r'\{\{#IF_[^}]+\}\}.*?\{\{/IF_[^}]+\}\}', '', content, flags=re.DOTALL)
        
        return content