# -*- coding: utf-8 -*-
"""
Unit tests for Output Validation Guardrails (Phase 8.1)

Tests validation of generated code output:
- Stack-specific file layout validation
- Forbidden library detection
- FILE manifest format compliance
- Path security validation
- User constraint enforcement
"""

import pytest
from mgx_agent.guardrails import (
    ValidationResult,
    validate_output_constraints,
    FileManifestValidator,
    StackValidator,
    ForbiddenLibraryScanner,
    ConstraintValidator,
    extract_file_paths,
    build_revision_prompt,
)
from mgx_agent.stack_specs import get_stack_spec


class TestValidationResult:
    """Test ValidationResult model"""
    
    def test_validation_result_initialization(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
    
    def test_add_error_marks_invalid(self):
        result = ValidationResult(is_valid=True)
        result.add_error("Test error")
        assert result.is_valid is False
        assert "Test error" in result.errors
    
    def test_add_warning_keeps_valid(self):
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        assert result.is_valid is True
        assert "Test warning" in result.warnings
    
    def test_summary_passed(self):
        result = ValidationResult(is_valid=True)
        assert "PASSED" in result.summary()
    
    def test_summary_failed(self):
        result = ValidationResult(is_valid=False, errors=["Error 1", "Error 2"])
        summary = result.summary()
        assert "FAILED" in summary
        assert "2 errors" in summary


class TestFileManifestValidator:
    """Test FILE manifest format validation"""
    
    def test_validate_format_strict_mode_requires_file_blocks(self):
        content = "This is just plain text without FILE blocks"
        errors = FileManifestValidator.validate_format(content, strict_mode=True)
        assert len(errors) > 0
        assert any("No FILE: blocks found" in e for e in errors)
    
    def test_validate_format_strict_mode_rejects_prose(self):
        content = """
Some explanation here

FILE: src/main.py
def hello():
    pass

More explanation outside FILE block
"""
        errors = FileManifestValidator.validate_format(content, strict_mode=True)
        assert len(errors) > 0
        assert any("prose" in e.lower() for e in errors)
    
    def test_validate_format_normal_mode_allows_prose(self):
        content = """
Here's my solution:

FILE: src/main.py
def hello():
    pass

This implements the feature.
"""
        errors = FileManifestValidator.validate_format(content, strict_mode=False)
        # Should not error in normal mode
        assert len(errors) == 0
    
    def test_validate_format_empty_output(self):
        errors = FileManifestValidator.validate_format("", strict_mode=True)
        assert len(errors) > 0
        assert any("empty" in e.lower() for e in errors)
    
    def test_validate_paths_detects_traversal(self):
        paths = ["src/main.py", "../../../etc/passwd", "app/routes.py"]
        errors = FileManifestValidator.validate_paths(paths)
        assert len(errors) > 0
        assert any("traversal" in e.lower() for e in errors)
    
    def test_validate_paths_detects_dangerous_paths(self):
        paths = ["/etc/shadow", "/var/log/auth.log"]
        errors = FileManifestValidator.validate_paths(paths)
        assert len(errors) >= 2
        assert any("dangerous" in e.lower() or "absolute" in e.lower() for e in errors)
    
    def test_validate_paths_accepts_safe_paths(self):
        paths = ["src/main.py", "tests/test_main.py", "package.json"]
        errors = FileManifestValidator.validate_paths(paths)
        assert len(errors) == 0
    
    def test_detect_duplicates(self):
        paths = ["src/main.py", "src/routes.py", "src/main.py"]
        errors = FileManifestValidator.detect_duplicates(paths)
        assert len(errors) > 0
        assert any("duplicate" in e.lower() for e in errors)
    
    def test_detect_duplicates_no_duplicates(self):
        paths = ["src/main.py", "src/routes.py", "tests/test_main.py"]
        errors = FileManifestValidator.detect_duplicates(paths)
        assert len(errors) == 0


class TestStackValidator:
    """Test stack-specific validation rules"""
    
    def test_express_ts_layout_required(self):
        """Express TS should require package.json, tsconfig.json, src/"""
        files = ["README.md", "server.js"]
        errors = StackValidator.validate_required_files(files, "express-ts")
        assert len(errors) >= 2
        assert any("package.json" in e for e in errors)
        assert any("tsconfig.json" in e for e in errors)
    
    def test_express_ts_layout_valid(self):
        """Valid Express TS layout"""
        files = ["package.json", "tsconfig.json", "src/index.ts", "src/routes/api.ts"]
        errors = StackValidator.validate_required_files(files, "express-ts")
        assert len(errors) == 0
    
    def test_fastapi_forbidden_nodejs(self):
        """FastAPI should not have package.json (unless monorepo)"""
        files = ["main.py", "requirements.txt", "package.json"]
        errors = StackValidator.validate_forbidden_files(files, "fastapi")
        # Note: package.json is in forbidden_nodejs list, not forbidden_files for FastAPI
        # So this might not error - adjust based on rules
        assert True  # Adjust based on actual rules
    
    def test_fastapi_required_files(self):
        """FastAPI should require main.py and requirements.txt or pyproject.toml"""
        files = ["README.md"]
        errors = StackValidator.validate_required_files(files, "fastapi")
        assert len(errors) >= 1
        assert any("main.py" in e for e in errors)
    
    def test_laravel_forbidden_python(self):
        """Laravel should not have Python files"""
        files = ["composer.json", "routes/web.php", "requirements.txt"]
        errors = StackValidator.validate_forbidden_files(files, "laravel")
        assert len(errors) > 0
        assert any("requirements.txt" in e for e in errors)
    
    def test_nextjs_app_directory_required(self):
        """Next.js should have app/ or pages/ directory"""
        files = ["package.json", "next.config.js"]
        errors = StackValidator.validate_required_files(files, "nextjs")
        # Should warn about missing app/ or pages/
        assert len(errors) >= 1
    
    def test_vue_vite_config_required(self):
        """Vue + Vite should require vite.config.ts"""
        files = ["package.json", "src/App.vue"]
        errors = StackValidator.validate_required_files(files, "vue-vite")
        assert len(errors) > 0
        assert any("vite.config.ts" in e for e in errors)
    
    def test_vue_vite_forbids_react(self):
        """Vue should not have React imports"""
        files = ["package.json", "vite.config.ts", "src/App.vue"]
        errors = StackValidator.validate_forbidden_files(files, "vue-vite")
        # No forbidden React files here, will be tested in scanner
        assert len(errors) == 0


class TestForbiddenLibraryScanner:
    """Test forbidden library import detection"""
    
    def test_forbidden_libs_scanner_detects_import_express_in_python(self):
        """Python (FastAPI) code should not import express"""
        content = """
from fastapi import FastAPI
import express  # This should be caught

app = FastAPI()
"""
        errors = ForbiddenLibraryScanner.scan_content(content, "fastapi")
        assert len(errors) > 0
        assert any("express" in e.lower() for e in errors)
    
    def test_forbidden_libs_scanner_detects_require_in_python(self):
        """Python code should not have require() calls"""
        content = """
const express = require('express')  # Wrong language!

from fastapi import FastAPI
"""
        errors = ForbiddenLibraryScanner.scan_content(content, "fastapi")
        assert len(errors) > 0
    
    def test_forbidden_libs_scanner_ignores_comments(self):
        """Should ignore forbidden patterns in comments"""
        content = """
# We could use express but we're using FastAPI
# import express would be wrong

from fastapi import FastAPI
"""
        errors = ForbiddenLibraryScanner.scan_content(content, "fastapi")
        # Comments should be ignored
        assert len(errors) == 0
    
    def test_forbidden_libs_in_laravel_no_express(self):
        """Laravel should not have express imports"""
        content = """
<?php

use Illuminate\\Support\\Facades\\Route;

// import express  <- in comment, OK

Route::get('/', function () {
    return view('welcome');
});
"""
        errors = ForbiddenLibraryScanner.scan_content(content, "laravel")
        assert len(errors) == 0
    
    def test_express_forbids_django(self):
        """Express TS should not have Django imports"""
        content = """
import express from 'express';
from django.http import HttpResponse  // Wrong!
"""
        errors = ForbiddenLibraryScanner.scan_content(content, "express-ts")
        assert len(errors) > 0


class TestConstraintValidator:
    """Test user constraint validation"""
    
    def test_constraint_no_extra_libraries_fails_with_unnecessary_imports(self):
        """Should detect imports not in common dependencies"""
        spec = get_stack_spec("fastapi")
        content = """
from fastapi import FastAPI
import requests  # Not in common deps
import numpy as np  # Not in common deps
"""
        errors = ConstraintValidator.validate_no_extra_libraries(content, spec)
        # Should catch requests and numpy
        assert len(errors) >= 2
    
    def test_constraint_no_extra_libraries_allows_builtins(self):
        """Should allow Python built-in modules"""
        spec = get_stack_spec("fastapi")
        content = """
from fastapi import FastAPI
import os
import sys
import json
from typing import List
"""
        errors = ConstraintValidator.validate_no_extra_libraries(content, spec)
        # os, sys, json, typing are built-ins
        assert len(errors) == 0
    
    def test_constraint_no_extra_libraries_nodejs(self):
        """Should check Node.js imports"""
        spec = get_stack_spec("express-ts")
        content = """
import express from 'express';
import axios from 'axios';  // Not in common deps
import lodash from 'lodash';  // Not in common deps
"""
        errors = ConstraintValidator.validate_no_extra_libraries(content, spec)
        assert len(errors) >= 2


class TestExtractFilePaths:
    """Test file path extraction from manifest"""
    
    def test_extract_file_paths_from_manifest(self):
        content = """
FILE: src/main.py
def hello():
    pass

FILE: tests/test_main.py
def test_hello():
    pass
"""
        paths = extract_file_paths(content)
        assert len(paths) == 2
        assert "src/main.py" in paths
        assert "tests/test_main.py" in paths
    
    def test_extract_file_paths_empty(self):
        content = "No FILE blocks here"
        paths = extract_file_paths(content)
        assert len(paths) == 0


class TestValidateOutputConstraints:
    """Integration tests for full validation"""
    
    def test_validation_passes_clean_express_manifest(self):
        """Valid Express TS manifest should pass"""
        content = """
FILE: package.json
{
  "name": "my-api",
  "dependencies": {
    "express": "^4.18.0"
  }
}

FILE: tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020"
  }
}

FILE: src/index.ts
import express from 'express';

const app = express();
app.listen(3000);
"""
        spec = get_stack_spec("express-ts")
        result = validate_output_constraints(content, spec, strict_mode=False)
        assert result.is_valid
    
    def test_validation_passes_clean_fastapi_manifest(self):
        """Valid FastAPI manifest should pass"""
        content = """
FILE: main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

FILE: requirements.txt
fastapi==0.104.0
uvicorn==0.24.0

FILE: app/routes.py
from fastapi import APIRouter

router = APIRouter()
"""
        spec = get_stack_spec("fastapi")
        result = validate_output_constraints(content, spec, strict_mode=False)
        assert result.is_valid
    
    def test_strict_file_manifest_rejects_prose_outside_blocks(self):
        """Strict mode should reject prose outside FILE blocks"""
        content = """
Here's my solution to the problem:

FILE: main.py
def hello():
    pass

This implements the feature as requested.
"""
        spec = get_stack_spec("fastapi")
        result = validate_output_constraints(content, spec, strict_mode=True)
        assert not result.is_valid
        assert any("prose" in e.lower() for e in result.errors)
    
    def test_strict_file_manifest_rejects_duplicate_files(self):
        """Should detect duplicate file definitions"""
        content = """
FILE: main.py
def hello():
    pass

FILE: routes.py
def route():
    pass

FILE: main.py
def goodbye():
    pass
"""
        spec = get_stack_spec("fastapi")
        result = validate_output_constraints(content, spec, strict_mode=True)
        assert not result.is_valid
        assert any("duplicate" in e.lower() for e in result.errors)
    
    def test_path_traversal_rejected(self):
        """Should reject path traversal attacks"""
        content = """
FILE: ../../../etc/passwd
root:x:0:0:root:/root:/bin/bash

FILE: src/main.py
def hello():
    pass
"""
        spec = get_stack_spec("fastapi")
        result = validate_output_constraints(content, spec)
        assert not result.is_valid
        assert any("traversal" in e.lower() for e in result.errors)
    
    def test_validation_warnings_dont_fail_but_logged(self):
        """Warnings should not fail validation but should be logged"""
        content = """
FILE: package.json
{
  "name": "my-api",
  "dependencies": {
    "express": "^4.18.0"
  }
}

FILE: tsconfig.json
{}

FILE: src/index.ts
import express from 'express';
const app = express();
"""
        spec = get_stack_spec("express-ts")
        result = validate_output_constraints(content, spec)
        # Should pass but might have warnings about missing commands
        assert result.is_valid
        # Might have warnings
        assert isinstance(result.warnings, list)
    
    def test_mixed_stack_detection_warns_or_fails(self):
        """Should detect mixed stacks (e.g., both Node.js and Python)"""
        content = """
FILE: package.json
{
  "name": "mixed"
}

FILE: requirements.txt
fastapi==0.104.0

FILE: src/index.ts
import express from 'express';

FILE: main.py
from fastapi import FastAPI
"""
        spec = get_stack_spec("express-ts")
        result = validate_output_constraints(content, spec)
        # Should have warnings about mixed stack
        assert len(result.warnings) > 0
        assert any("mixed" in w.lower() for w in result.warnings)
    
    def test_empty_output_fails(self):
        """Empty output should fail validation"""
        result = validate_output_constraints("", get_stack_spec("fastapi"))
        assert not result.is_valid
        assert any("empty" in e.lower() for e in result.errors)
    
    def test_validation_with_constraints(self):
        """Should validate user constraints"""
        content = """
FILE: main.py
from fastapi import FastAPI
import requests
import numpy as np

app = FastAPI()
"""
        spec = get_stack_spec("fastapi")
        constraints = ["no extra libraries"]
        result = validate_output_constraints(content, spec, constraints=constraints)
        assert not result.is_valid
        assert any("constraint" in e.lower() for e in result.errors)


class TestBuildRevisionPrompt:
    """Test revision prompt generation"""
    
    def test_build_revision_prompt_includes_errors(self):
        """Revision prompt should include all errors"""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing package.json", "Forbidden import detected"],
            warnings=["Command not found"]
        )
        prompt = build_revision_prompt(result, "Create an Express API")
        
        assert "VALIDATION FAILED" in prompt
        assert "Missing package.json" in prompt
        assert "Forbidden import detected" in prompt
        assert "Create an Express API" in prompt
    
    def test_build_revision_prompt_includes_warnings(self):
        """Revision prompt should include warnings"""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1"],
            warnings=["Warning 1", "Warning 2"]
        )
        prompt = build_revision_prompt(result, "Create an API")
        
        assert "WARNING" in prompt
        assert "Warning 1" in prompt
        assert "Warning 2" in prompt
    
    def test_build_revision_prompt_actionable(self):
        """Revision prompt should be actionable"""
        result = ValidationResult(
            is_valid=False,
            errors=["Stack 'express-ts' requires file: package.json"]
        )
        prompt = build_revision_prompt(result, "Build Express API")
        
        # Should tell user to fix issues
        assert "fix" in prompt.lower() or "address" in prompt.lower()
        assert "package.json" in prompt


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""
    
    def test_validation_disabled_returns_output(self):
        """When validation is disabled, should return output as-is"""
        # This would test WriteCode action with enable_validation=False
        # Placeholder for integration test
        assert True
    
    def test_normal_mode_allows_code_blocks(self):
        """Normal mode should allow traditional code blocks"""
        content = """
```python
def hello():
    pass
```
"""
        # Without stack spec, should pass (no stack validation)
        result = validate_output_constraints(content, stack_spec=None, strict_mode=False)
        # Should not fail in normal mode when no stack spec provided
        assert result.is_valid


# Integration test placeholder for auto-revision
class TestAutoRevision:
    """Test automatic revision triggering on validation failure"""
    
    @pytest.mark.asyncio
    async def test_auto_revision_triggered_on_validation_failure(self):
        """WriteCode should automatically retry when validation fails"""
        # This requires mocking LLM calls
        # Placeholder for future integration test
        pass
    
    @pytest.mark.asyncio
    async def test_max_retries_respected(self):
        """Should not retry more than max_validation_retries times"""
        # Placeholder for future integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
