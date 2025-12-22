# -*- coding: utf-8 -*-
"""
Web Stack Support Tests (Phase E)

Stack specifications, file utilities, ve validation testleri.
"""

import pytest
import tempfile
import json
from pathlib import Path

# Import modules
from mgx_agent.stack_specs import (
    StackCategory,
    ProjectType,
    OutputMode,
    StackSpec,
    STACK_SPECS,
    get_stack_spec,
    infer_stack_from_task,
)
from mgx_agent.file_utils import (
    parse_file_manifest,
    validate_output_constraints,
    safe_write_file,
    create_backup,
    validate_stack_structure,
)
from mgx_agent.config import TeamConfig


class TestStackSpecs:
    """StackSpec testi"""
    
    def test_all_stacks_defined(self):
        """Tüm stack'lerin tanımlı olduğunu doğrula"""
        expected_stacks = [
            "express-ts",
            "nestjs",
            "laravel",
            "fastapi",
            "dotnet-api",
            "react-vite",
            "nextjs",
            "vue-vite",
            "devops-docker",
            "ci-github-actions",
        ]
        
        for stack_id in expected_stacks:
            assert stack_id in STACK_SPECS, f"Stack {stack_id} tanımlı değil"
            spec = STACK_SPECS[stack_id]
            assert isinstance(spec, StackSpec)
            assert spec.stack_id == stack_id
    
    def test_stack_categories(self):
        """Stack kategorilerini doğrula"""
        backend_stacks = [s for s in STACK_SPECS.values() if s.category == StackCategory.BACKEND]
        frontend_stacks = [s for s in STACK_SPECS.values() if s.category == StackCategory.FRONTEND]
        devops_stacks = [s for s in STACK_SPECS.values() if s.category == StackCategory.DEVOPS]
        
        assert len(backend_stacks) >= 4  # express-ts, nestjs, laravel, fastapi, dotnet-api
        assert len(frontend_stacks) >= 3  # react-vite, nextjs, vue-vite
        assert len(devops_stacks) >= 2  # devops-docker, ci-github-actions
    
    def test_get_stack_spec(self):
        """get_stack_spec fonksiyonunu test et"""
        spec = get_stack_spec("fastapi")
        assert spec is not None
        assert spec.stack_id == "fastapi"
        assert spec.category == StackCategory.BACKEND
        assert spec.language == "py"
        assert spec.test_framework == "pytest"
        
        # Geçersiz stack
        invalid = get_stack_spec("invalid-stack")
        assert invalid is None
    
    def test_infer_stack_from_task(self):
        """Stack inference'ı test et"""
        # Backend - specific framework names
        assert infer_stack_from_task("Build a NestJS backend") == "nestjs"
        assert infer_stack_from_task("Create Laravel authentication system") == "laravel"
        assert infer_stack_from_task("Build a FastAPI endpoint") == "fastapi"
        
        # Backend - general (defaults)
        assert infer_stack_from_task("Create a REST API") == "express-ts"  # Default backend
        assert infer_stack_from_task("Create a Python REST API") == "fastapi"
        assert infer_stack_from_task("Build a PHP API") == "laravel"
        
        # Frontend
        assert infer_stack_from_task("Create a dashboard UI") in ["react-vite", "nextjs", "vue-vite"]
        assert infer_stack_from_task("Build a Next.js page") == "nextjs"
        assert infer_stack_from_task("Vue component for data table") == "vue-vite"
        
        # DevOps
        assert infer_stack_from_task("Setup Docker containers") == "devops-docker"
        assert infer_stack_from_task("Configure GitHub Actions CI") == "ci-github-actions"
    
    def test_stack_spec_required_fields(self):
        """Her stack'in gerekli alanları olduğunu doğrula"""
        for stack_id, spec in STACK_SPECS.items():
            assert spec.name, f"{stack_id} name eksik"
            assert spec.language, f"{stack_id} language eksik"
            assert spec.test_framework, f"{stack_id} test_framework eksik"
            assert spec.package_manager, f"{stack_id} package_manager eksik"
            assert spec.linter_formatter, f"{stack_id} linter_formatter eksik"
            assert isinstance(spec.project_layout, dict), f"{stack_id} project_layout dict değil"
            assert isinstance(spec.run_commands, dict), f"{stack_id} run_commands dict değil"


class TestFileManifestParser:
    """FILE manifest parser testi"""
    
    def test_parse_single_file(self):
        """Tek dosya parse et"""
        manifest = """
FILE: src/main.py
def hello():
    print("Hello")
"""
        files = parse_file_manifest(manifest)
        assert len(files) == 1
        assert "src/main.py" in files
        assert "def hello():" in files["src/main.py"]
    
    def test_parse_multiple_files(self):
        """Çoklu dosya parse et"""
        manifest = """
FILE: package.json
{"name": "test"}

FILE: src/index.ts
console.log("hello");

FILE: README.md
# Project
"""
        files = parse_file_manifest(manifest)
        assert len(files) == 3
        assert "package.json" in files
        assert "src/index.ts" in files
        assert "README.md" in files
        assert '"name": "test"' in files["package.json"]
    
    def test_parse_empty_manifest(self):
        """Boş manifest"""
        manifest = ""
        files = parse_file_manifest(manifest)
        assert len(files) == 0
    
    def test_parse_no_file_markers(self):
        """FILE marker'ı olmayan içerik"""
        manifest = "Just some text without FILE markers"
        files = parse_file_manifest(manifest)
        assert len(files) == 0


class TestOutputValidation:
    """Output validation testi"""
    
    def test_validate_fastapi_structure(self):
        """FastAPI proje yapısını doğrula"""
        files = {
            "app/main.py": "from fastapi import FastAPI\napp = FastAPI()",
            "app/routers/users.py": "# User routes",
            "requirements.txt": "fastapi\nuvicorn",
            ".env.example": "DATABASE_URL=",
        }
        
        is_valid, errors = validate_output_constraints(files, stack_id="fastapi")
        assert is_valid or len(errors) == 0  # Uyarılar olabilir ama hata olmamalı
    
    def test_validate_express_structure(self):
        """Express-TS proje yapısını doğrula"""
        files = {
            "package.json": '{"name": "test", "dependencies": {"express": "^4.0.0"}}',
            "src/server.ts": "import express from 'express';",
            "tsconfig.json": '{"compilerOptions": {}}',
        }
        
        is_valid, errors = validate_output_constraints(files, stack_id="express-ts")
        assert is_valid or len(errors) == 0
    
    def test_validate_constraint_pnpm(self):
        """pnpm constraint'i test et"""
        files = {
            "package.json": '{"scripts": {"dev": "npm run start"}}',  # pnpm yok!
        }
        
        constraints = ["Use pnpm"]
        is_valid, errors = validate_output_constraints(files, constraints=constraints)
        assert not is_valid
        assert any("pnpm" in err.lower() for err in errors)
    
    def test_validate_constraint_env_vars(self):
        """.env.example constraint'i test et"""
        files = {
            "src/main.py": "# code",
        }
        
        constraints = ["Must include env vars"]
        is_valid, errors = validate_output_constraints(files, constraints=constraints)
        assert not is_valid
        assert any("env.example" in err.lower() for err in errors)
    
    def test_validate_empty_files(self):
        """Boş dosya hatası"""
        files = {
            "src/main.py": "",
            "README.md": "# Content",
        }
        
        is_valid, errors = validate_output_constraints(files)
        assert not is_valid
        assert any("Boş dosya" in err for err in errors)
    
    def test_validate_strict_mode(self):
        """Strict mode - FILE blokları zorunlu"""
        files = {}  # Boş
        
        is_valid, errors = validate_output_constraints(files, strict_mode=True)
        assert not is_valid
        assert any("FILE bloğu" in err for err in errors)


class TestSafeFileWriter:
    """Safe file writer testi"""
    
    def test_write_new_file(self):
        """Yeni dosya yaz"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            content = "Hello World"
            
            success = safe_write_file(str(file_path), content)
            assert success
            assert file_path.exists()
            assert file_path.read_text() == content
    
    def test_overwrite_with_backup(self):
        """Mevcut dosyayı yedekle ve üzerine yaz"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("Original")
            
            success = safe_write_file(str(file_path), "Updated", create_backup_flag=True)
            assert success
            assert file_path.read_text() == "Updated"
            
            # Backup dosyası oluşturulmalı
            backups = list(Path(tmpdir).glob("test.txt.*.bak"))
            assert len(backups) > 0
    
    def test_create_nested_directories(self):
        """İç içe klasörler oluştur"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "src" / "app" / "main.py"
            content = "# Python code"
            
            success = safe_write_file(str(file_path), content)
            assert success
            assert file_path.exists()
            assert file_path.parent.exists()


class TestStackStructureValidation:
    """Stack structure validation testi"""
    
    def test_validate_fastapi_project(self):
        """FastAPI proje yapısını kontrol et"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Gerekli klasörleri oluştur
            (Path(tmpdir) / "app").mkdir()
            (Path(tmpdir) / "app" / "routers").mkdir()
            (Path(tmpdir) / "tests").mkdir()
            (Path(tmpdir) / "requirements.txt").touch()
            (Path(tmpdir) / ".env.example").touch()
            
            is_valid, warnings = validate_stack_structure(tmpdir, "fastapi")
            # Bazı uyarılar olabilir ama temel yapı geçerli
            assert len(warnings) < 5  # Çok fazla uyarı olmamalı
    
    def test_validate_missing_structure(self):
        """Eksik yapı uyarıları"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Boş proje
            is_valid, warnings = validate_stack_structure(tmpdir, "fastapi")
            assert not is_valid
            assert len(warnings) > 0


class TestTeamConfigStackSupport:
    """TeamConfig stack ayarları testi"""
    
    def test_config_with_stack_fields(self):
        """Stack alanlarıyla config oluştur"""
        config = TeamConfig(
            target_stack="fastapi",
            project_type="api",
            output_mode="generate_new",
            strict_requirements=True,
            constraints=["Use minimal dependencies"],
        )
        
        assert config.target_stack == "fastapi"
        assert config.project_type == "api"
        assert config.output_mode == "generate_new"
        assert config.strict_requirements is True
        assert len(config.constraints) == 1
    
    def test_config_defaults(self):
        """Varsayılan değerler"""
        config = TeamConfig()
        
        assert config.target_stack is None
        assert config.project_type is None
        assert config.output_mode == "generate_new"
        assert config.strict_requirements is False
        assert config.constraints == []
    
    def test_config_from_dict(self):
        """Dict'ten config oluştur"""
        data = {
            "target_stack": "nextjs",
            "project_type": "webapp",
            "max_rounds": 3,
        }
        
        config = TeamConfig.from_dict(data)
        assert config.target_stack == "nextjs"
        assert config.project_type == "webapp"
        assert config.max_rounds == 3


class TestJSONInputParsing:
    """JSON input parsing testi"""
    
    def test_parse_valid_json_task(self):
        """Geçerli JSON task parse et"""
        task_json = {
            "task": "Create a REST API for user management",
            "target_stack": "fastapi",
            "project_type": "api",
            "constraints": ["Use Pydantic", "Add authentication"],
            "output_mode": "generate_new"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(task_json, f)
            temp_path = f.name
        
        try:
            with open(temp_path, 'r') as f:
                loaded = json.load(f)
            
            assert loaded["task"] == "Create a REST API for user management"
            assert loaded["target_stack"] == "fastapi"
            assert len(loaded["constraints"]) == 2
        finally:
            Path(temp_path).unlink()
    
    def test_minimal_json_task(self):
        """Minimal JSON task (sadece task alanı)"""
        task_json = {
            "task": "Create a simple function"
        }
        
        assert "task" in task_json
        assert task_json.get("target_stack") is None  # Opsiyonel


class TestBackwardCompatibility:
    """Backward compatibility testi"""
    
    def test_old_config_still_works(self):
        """Eski config formatı hala çalışmalı"""
        config = TeamConfig(
            max_rounds=5,
            human_reviewer=True,
            enable_caching=True,
        )
        
        assert config.max_rounds == 5
        assert config.human_reviewer is True
        assert config.enable_caching is True
        # Yeni alanlar varsayılan değerlerde olmalı
        assert config.target_stack is None
        assert config.output_mode == "generate_new"


class TestConstraintKeywordDetection:
    """Constraint keyword detection testi"""
    
    def test_detect_pnpm_constraint(self):
        """pnpm constraint detection"""
        files = {"package.json": '{"name": "test"}'}
        constraints = ["Use pnpm for package management"]
        
        is_valid, errors = validate_output_constraints(files, constraints=constraints)
        assert not is_valid
    
    def test_detect_env_constraint(self):
        """Environment variable constraint detection"""
        files = {"src/main.py": "# code"}
        constraints = ["Must include environment variables"]
        
        is_valid, errors = validate_output_constraints(files, constraints=constraints)
        assert not is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
