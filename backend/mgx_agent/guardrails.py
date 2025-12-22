# -*- coding: utf-8 -*-
"""
MGX Agent Output Validation Guardrails

Production-stable validation for generated code output:
- Stack-specific file layout validation
- Forbidden library detection
- FILE manifest format compliance
- Path security validation
- User constraint enforcement
"""

import re
from typing import List, Dict, Optional, Set, Tuple
from pydantic import BaseModel, Field
from metagpt.logs import logger

from mgx_agent.stack_specs import StackSpec, get_stack_spec

__all__ = [
    'ValidationResult',
    'validate_output_constraints',
]


class ValidationResult(BaseModel):
    """Result of output validation"""
    is_valid: bool = Field(..., description="Whether output passed all validations")
    errors: List[str] = Field(default_factory=list, description="Critical errors (must fix)")
    warnings: List[str] = Field(default_factory=list, description="Non-critical warnings")
    
    class Config:
        use_enum_values = True
    
    def add_error(self, error: str):
        """Add a validation error"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a validation warning"""
        self.warnings.append(warning)
    
    def summary(self) -> str:
        """Get human-readable summary"""
        if self.is_valid:
            msg = "✅ Validation PASSED"
            if self.warnings:
                msg += f" ({len(self.warnings)} warnings)"
            return msg
        else:
            return f"❌ Validation FAILED: {len(self.errors)} errors, {len(self.warnings)} warnings"


# ============================================
# STACK-SPECIFIC VALIDATION RULES
# ============================================

STACK_VALIDATION_RULES = {
    "express-ts": {
        "required_files": ["package.json", "tsconfig.json"],
        "required_dirs": ["src/"],
        "forbidden_files": ["requirements.txt", "composer.json", "pyproject.toml", "Gemfile"],
        "required_commands": ["npm run dev", "npm run build", "npm test"],
        "forbidden_imports": [
            r"from\s+django",
            r"from\s+flask",
            r"import\s+laravel",
            r"require\s*\(\s*['\"]laravel",
        ],
    },
    "nestjs": {
        "required_files": ["package.json", "tsconfig.json", "nest-cli.json"],
        "required_dirs": ["src/"],
        "forbidden_files": ["requirements.txt", "composer.json", "pyproject.toml"],
        "required_commands": ["npm run start:dev", "npm run build", "npm test"],
        "forbidden_imports": [
            r"from\s+django",
            r"from\s+flask",
            r"import\s+express\b",  # NestJS doesn't use express directly
        ],
    },
    "fastapi": {
        "required_files": ["main.py"],
        "required_patterns": [r"(requirements\.txt|pyproject\.toml)", r"app/"],
        "forbidden_files": ["composer.json", "Gemfile"],
        "required_commands": ["uvicorn", "pytest"],
        "forbidden_imports": [
            r"import\s+express",
            r"require\s*\(",
            r"use\s+Illuminate",
            r"from\s+django",
        ],
        "forbidden_nodejs": ["package.json"],  # Unless it's a monorepo
    },
    "laravel": {
        "required_files": ["composer.json", ".env.example"],
        "required_dirs": ["app/", "routes/"],
        "forbidden_files": ["pyproject.toml", "requirements.txt", "Gemfile"],
        "required_commands": ["php artisan", "composer test"],
        "forbidden_imports": [
            r"import\s+express",
            r"from\s+fastapi",
            r"from\s+django",
            r"import\s+React",
        ],
    },
    "nextjs": {
        "required_files": ["package.json", "next.config.js", "tsconfig.json"],
        "required_patterns": [r"(app/|pages/)"],
        "forbidden_files": ["requirements.txt", "composer.json", "vite.config"],
        "required_commands": ["npm run dev", "npm run build"],
        "forbidden_imports": [
            r"from\s+['\"]react-router",  # Next.js has built-in routing
            r"import\s+\{.*createBrowserRouter",
            r"from\s+['\"]vite",
        ],
    },
    "vue-vite": {
        "required_files": ["package.json", "vite.config.ts"],
        "required_dirs": ["src/"],
        "forbidden_files": ["next.config", "nuxt.config", "requirements.txt"],
        "required_commands": ["npm run dev", "npm run build"],
        "forbidden_imports": [
            r"from\s+['\"]next",
            r"import\s+React\b",
            r"from\s+['\"]react\b",
        ],
    },
    "react-vite": {
        "required_files": ["package.json", "vite.config.ts"],
        "required_dirs": ["src/"],
        "forbidden_files": ["next.config", "requirements.txt", "composer.json"],
        "required_commands": ["npm run dev", "npm run build"],
        "forbidden_imports": [
            r"from\s+['\"]next",
            r"from\s+['\"]vue",
        ],
    },
    "dotnet-api": {
        "required_patterns": [r"\.csproj$", r"Program\.cs"],
        "required_files": ["appsettings.json"],
        "forbidden_files": ["package.json", "requirements.txt", "composer.json"],
        "required_commands": ["dotnet run", "dotnet build", "dotnet test"],
        "forbidden_imports": [
            r"import\s+express",
            r"from\s+fastapi",
            r"use\s+Illuminate",
        ],
    },
}


# ============================================
# FILE MANIFEST PARSER
# ============================================

def parse_file_manifest(content: str) -> Tuple[List[str], List[str]]:
    """
    Parse FILE manifest and extract file paths and prose blocks.
    
    Args:
        content: Generated output string
    
    Returns:
        Tuple of (file_paths, prose_blocks)
    """
    file_paths = []
    prose_blocks = []
    
    lines = content.split('\n')
    current_block = []
    in_file_block = False
    current_file = None
    
    for line in lines:
        if line.startswith('FILE:'):
            # Save previous prose block if any
            if current_block and not in_file_block:
                prose_blocks.append('\n'.join(current_block).strip())
                current_block = []
            
            # Extract file path
            file_path = line[5:].strip()
            file_paths.append(file_path)
            current_file = file_path
            in_file_block = True
            current_block = []
        elif line.startswith('FILE:') or (current_file and line.strip() and not line.startswith(' ') and not line.startswith('\t')):
            # Next FILE block or end of current file
            if in_file_block:
                in_file_block = False
                current_block = []
        else:
            current_block.append(line)
    
    # Handle any remaining prose
    if current_block and not in_file_block:
        prose = '\n'.join(current_block).strip()
        if prose:
            prose_blocks.append(prose)
    
    return file_paths, prose_blocks


def extract_file_paths(content: str) -> List[str]:
    """Extract file paths from FILE manifest"""
    paths = []
    for line in content.split('\n'):
        if line.strip().startswith('FILE:'):
            path = line.strip()[5:].strip()
            paths.append(path)
    return paths


# ============================================
# VALIDATORS
# ============================================

class FileManifestValidator:
    """Validates FILE manifest format compliance"""
    
    @staticmethod
    def validate_format(content: str, strict_mode: bool) -> List[str]:
        """
        Validate FILE manifest format.
        
        In strict mode:
        - Every non-FILE block is an error
        - FILE: prefix must be exact
        
        In normal mode:
        - Allow explanations outside FILE blocks
        - More lenient parsing
        """
        errors = []
        
        if not content or not content.strip():
            errors.append("Output is empty")
            return errors
        
        # Check for FILE: prefix
        has_file_blocks = 'FILE:' in content
        
        if strict_mode and not has_file_blocks:
            errors.append("No FILE: blocks found in strict mode - output must use FILE manifest format")
            return errors
        
        if strict_mode:
            # In strict mode, check for prose outside FILE blocks
            lines = content.split('\n')
            in_file = False
            prose_lines = []
            
            for i, line in enumerate(lines):
                if line.startswith('FILE:'):
                    in_file = True
                elif not in_file and line.strip() and not line.startswith('```'):
                    # Found prose outside FILE block
                    if not line.strip().startswith('#') and not line.strip().startswith('//'):
                        prose_lines.append((i + 1, line.strip()[:80]))
            
            if prose_lines:
                errors.append(
                    f"Strict mode: Found {len(prose_lines)} lines of prose/explanation outside FILE blocks. "
                    f"Examples: Line {prose_lines[0][0]}: '{prose_lines[0][1]}'"
                )
        
        return errors
    
    @staticmethod
    def validate_paths(file_paths: List[str]) -> List[str]:
        """Validate file paths for security and validity"""
        errors = []
        
        for path in file_paths:
            # Check for path traversal
            if '..' in path:
                errors.append(f"Path traversal detected: {path}")
            
            # Check for absolute paths that might be dangerous
            if path.startswith('/etc/') or path.startswith('/var/') or path.startswith('/root/'):
                errors.append(f"Dangerous absolute path: {path}")
            
            # Check for empty paths
            if not path or not path.strip():
                errors.append("Empty file path found")
        
        return errors
    
    @staticmethod
    def detect_duplicates(file_paths: List[str]) -> List[str]:
        """Detect duplicate file definitions"""
        errors = []
        seen = {}
        
        for path in file_paths:
            if path in seen:
                errors.append(f"Duplicate file definition: {path} (defined {seen[path] + 1} times)")
                seen[path] += 1
            else:
                seen[path] = 1
        
        return errors


class StackValidator:
    """Validates stack-specific requirements"""
    
    @staticmethod
    def validate_required_files(file_paths: List[str], stack_id: str) -> List[str]:
        """Check for required files based on stack"""
        errors = []
        rules = STACK_VALIDATION_RULES.get(stack_id, {})
        
        required_files = rules.get('required_files', [])
        required_dirs = rules.get('required_dirs', [])
        required_patterns = rules.get('required_patterns', [])
        
        # Check required files
        for req_file in required_files:
            found = any(req_file in path for path in file_paths)
            if not found:
                errors.append(f"Stack '{stack_id}' requires file: {req_file}")
        
        # Check required directories
        for req_dir in required_dirs:
            found = any(path.startswith(req_dir) or f"/{req_dir}" in path for path in file_paths)
            if not found:
                errors.append(f"Stack '{stack_id}' requires directory: {req_dir}")
        
        # Check required patterns (regex)
        for pattern in required_patterns:
            found = any(re.search(pattern, path) for path in file_paths)
            if not found:
                errors.append(f"Stack '{stack_id}' requires pattern: {pattern}")
        
        return errors
    
    @staticmethod
    def validate_forbidden_files(file_paths: List[str], stack_id: str) -> List[str]:
        """Check for forbidden files based on stack"""
        errors = []
        rules = STACK_VALIDATION_RULES.get(stack_id, {})
        
        forbidden_files = rules.get('forbidden_files', [])
        
        for forbidden in forbidden_files:
            for path in file_paths:
                if forbidden in path:
                    errors.append(
                        f"Stack '{stack_id}' forbids file: {path} "
                        f"(contains forbidden pattern '{forbidden}')"
                    )
        
        return errors
    
    @staticmethod
    def validate_commands(content: str, stack_id: str) -> List[str]:
        """Check if expected commands are mentioned (warnings only)"""
        warnings = []
        rules = STACK_VALIDATION_RULES.get(stack_id, {})
        
        required_commands = rules.get('required_commands', [])
        
        for cmd in required_commands:
            if cmd not in content:
                warnings.append(
                    f"Stack '{stack_id}' typically uses command: {cmd} "
                    f"(not found in output)"
                )
        
        return warnings


class ForbiddenLibraryScanner:
    """Scans for forbidden library imports/usages"""
    
    @staticmethod
    def scan_content(content: str, stack_id: str) -> List[str]:
        """
        Scan content for forbidden library patterns.
        Context-aware: ignores comments in most cases.
        """
        errors = []
        rules = STACK_VALIDATION_RULES.get(stack_id, {})
        
        forbidden_patterns = rules.get('forbidden_imports', [])
        
        for pattern in forbidden_patterns:
            # Search with case-insensitive flag
            matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
            
            for match in matches:
                # Get context (line where match was found)
                start = content.rfind('\n', 0, match.start()) + 1
                end = content.find('\n', match.end())
                if end == -1:
                    end = len(content)
                line = content[start:end]
                
                # Skip if it's clearly a comment (basic heuristic)
                line_stripped = line.strip()
                if line_stripped.startswith('#') or line_stripped.startswith('//') or line_stripped.startswith('/*'):
                    continue
                
                # Check if inside a string (very basic check)
                # Count quotes before match on same line
                before_match = content[start:match.start()]
                single_quotes = before_match.count("'")
                double_quotes = before_match.count('"')
                
                # If odd number of quotes, might be inside string - skip
                if single_quotes % 2 == 1 or double_quotes % 2 == 1:
                    continue
                
                errors.append(
                    f"Forbidden import/usage in stack '{stack_id}': "
                    f"'{match.group(0)}' at line: {line.strip()[:100]}"
                )
        
        return errors


class ConstraintValidator:
    """Validates user-provided constraints"""
    
    @staticmethod
    def validate_no_extra_libraries(content: str, stack_spec: StackSpec) -> List[str]:
        """
        Check if output uses only common dependencies for the stack.
        This is a heuristic check.
        """
        errors = []
        
        if not stack_spec:
            return errors
        
        common_deps = set(stack_spec.common_dependencies)
        
        # Extract import/require statements (basic heuristic)
        if stack_spec.language in ['ts', 'js']:
            # Find all import/require statements
            # Pattern 1: import X from 'package'
            import_from_pattern = r"import\s+(?:\w+|\{[^}]+\})\s+from\s+['\"]([^'\"]+)['\"]"
            # Pattern 2: require('package')
            require_pattern = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
            
            imports_from = re.findall(import_from_pattern, content)
            imports_require = re.findall(require_pattern, content)
            imports = imports_from + imports_require
            
            for imp in imports:
                # Get base package name
                base_pkg = imp.split('/')[0]
                if base_pkg.startswith('@'):
                    # Scoped package like @nestjs/core
                    base_pkg = '/'.join(imp.split('/')[:2])
                
                # Check if it's a common dep or built-in (case-insensitive)
                is_common = any(base_pkg.lower() == dep.lower() for dep in common_deps)
                
                if not is_common and not base_pkg.startswith('.'):
                    # Ignore relative imports
                    errors.append(
                        f"Constraint 'no extra libraries': Found import '{imp}' "
                        f"which is not in common dependencies: {list(common_deps)}"
                    )
        
        elif stack_spec.language == 'py':
            # Find all "import X" statements (not "from X import Y")
            import_pattern = r"^import\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            imports = re.findall(import_pattern, content, re.MULTILINE)
            
            # Python built-ins to ignore
            builtins = {'os', 'sys', 'json', 're', 'typing', 'dataclasses', 'datetime', 'pathlib', 
                       'collections', 'itertools', 'functools', 'copy', 'math', 'random', 'time'}
            
            # Also get base package from "from X import Y" statements
            from_pattern = r"^from\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            from_imports = re.findall(from_pattern, content, re.MULTILINE)
            
            # Combine and check
            all_imports = set(imports + from_imports)
            
            for imp in all_imports:
                # Check if it's a common dep (case-insensitive comparison for package names)
                is_common = any(imp.lower() == dep.lower() for dep in common_deps)
                
                if not is_common and imp not in builtins:
                    errors.append(
                        f"Constraint 'no extra libraries': Found import '{imp}' "
                        f"which is not in common dependencies: {list(common_deps)}"
                    )
        
        return errors


# ============================================
# MAIN VALIDATION FUNCTION
# ============================================

def validate_output_constraints(
    generated_output: str,
    stack_spec: Optional[StackSpec] = None,
    constraints: Optional[List[str]] = None,
    strict_mode: bool = False,
) -> ValidationResult:
    """
    Validate generated output against stack specifications and constraints.
    
    Args:
        generated_output: Complete FILE manifest or code output
        stack_spec: Stack specification (from Phase 7)
        constraints: User-provided constraints (e.g., ["no extra libraries"])
        strict_mode: If True, enforce FILE-only format, no prose allowed
    
    Returns:
        ValidationResult with is_valid, errors, and warnings
    """
    result = ValidationResult(is_valid=True)
    
    if not generated_output or not generated_output.strip():
        result.add_error("Generated output is empty")
        return result
    
    # 1. FILE Manifest Format Validation
    format_errors = FileManifestValidator.validate_format(generated_output, strict_mode)
    for error in format_errors:
        result.add_error(error)
    
    # 2. Extract file paths
    file_paths = extract_file_paths(generated_output)
    
    if not file_paths and strict_mode:
        result.add_error("No files found in output (strict mode requires FILE: blocks)")
        return result
    
    # 3. Path Security Validation
    if file_paths:
        path_errors = FileManifestValidator.validate_paths(file_paths)
        for error in path_errors:
            result.add_error(error)
        
        # 4. Duplicate Detection
        dup_errors = FileManifestValidator.detect_duplicates(file_paths)
        for error in dup_errors:
            result.add_error(error)
    
    # 5. Stack-Specific Validation
    if stack_spec:
        stack_id = stack_spec.stack_id
        
        # Required files/dirs
        required_errors = StackValidator.validate_required_files(file_paths, stack_id)
        for error in required_errors:
            result.add_error(error)
        
        # Forbidden files
        forbidden_errors = StackValidator.validate_forbidden_files(file_paths, stack_id)
        for error in forbidden_errors:
            result.add_error(error)
        
        # Command mentions (warnings only)
        cmd_warnings = StackValidator.validate_commands(generated_output, stack_id)
        for warning in cmd_warnings:
            result.add_warning(warning)
        
        # Forbidden libraries
        lib_errors = ForbiddenLibraryScanner.scan_content(generated_output, stack_id)
        for error in lib_errors:
            result.add_error(error)
    
    # 6. User Constraint Validation
    if constraints and stack_spec:
        for constraint in constraints:
            constraint_lower = constraint.lower()
            
            if 'no extra librar' in constraint_lower:
                constraint_errors = ConstraintValidator.validate_no_extra_libraries(
                    generated_output, stack_spec
                )
                for error in constraint_errors:
                    result.add_error(error)
            
            # Add more constraint types as needed
    
    # 7. Mixed Stack Detection (heuristic)
    if stack_spec and file_paths:
        mixed_stack_warnings = _detect_mixed_stack(file_paths, stack_spec)
        for warning in mixed_stack_warnings:
            result.add_warning(warning)
    
    return result


def _detect_mixed_stack(file_paths: List[str], stack_spec: StackSpec) -> List[str]:
    """
    Detect if multiple stacks are mixed (e.g., both package.json and requirements.txt).
    Returns warnings.
    """
    warnings = []
    
    # Define stack indicators
    indicators = {
        'nodejs': ['package.json', 'node_modules'],
        'python': ['requirements.txt', 'pyproject.toml', 'setup.py'],
        'php': ['composer.json', 'vendor'],
        'ruby': ['Gemfile', 'Gemfile.lock'],
        'dotnet': ['.csproj', '.sln'],
    }
    
    # Expected stack based on spec
    expected_lang_map = {
        'ts': 'nodejs',
        'js': 'nodejs',
        'py': 'python',
        'php': 'php',
        'cs': 'dotnet',
        'rb': 'ruby',
    }
    
    expected = expected_lang_map.get(stack_spec.language)
    
    # Detect what's actually present
    detected = set()
    for stack_name, indicator_files in indicators.items():
        for indicator in indicator_files:
            if any(indicator in path for path in file_paths):
                detected.add(stack_name)
    
    # Check for unexpected stacks
    if expected and detected:
        unexpected = detected - {expected}
        if unexpected:
            warnings.append(
                f"Mixed stack detected: Expected '{expected}' (based on {stack_spec.stack_id}) "
                f"but also found indicators for: {', '.join(unexpected)}. "
                f"This might be intentional (monorepo) or a mistake."
            )
    
    return warnings


# ============================================
# HELPER: Build Revision Prompt
# ============================================

def build_revision_prompt(validation_result: ValidationResult, original_task: str) -> str:
    """
    Build a revision prompt based on validation errors.
    
    Args:
        validation_result: Failed validation result
        original_task: Original task description
    
    Returns:
        Revision prompt string for LLM
    """
    error_list = '\n'.join(f"- {error}" for error in validation_result.errors)
    warning_list = '\n'.join(f"- {warning}" for warning in validation_result.warnings) if validation_result.warnings else ""
    
    prompt = f"""⚠️ OUTPUT VALIDATION FAILED

The previous output did not pass validation checks. Please fix the following issues:

ERRORS (MUST FIX):
{error_list}
"""
    
    if warning_list:
        prompt += f"""
WARNINGS (RECOMMENDED TO FIX):
{warning_list}
"""
    
    prompt += f"""

Original Task: {original_task}

Please regenerate the output addressing ALL validation errors above.
Ensure:
1. All required files for the stack are present
2. No forbidden libraries or files are used
3. FILE manifest format is correct (if required)
4. All file paths are valid and secure
5. No duplicate file definitions

Generate the complete, corrected output now.
"""
    
    return prompt
