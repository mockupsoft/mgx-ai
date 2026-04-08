# -*- coding: utf-8 -*-
"""
Unit tests: Paralel Mikroservis Orkestrasyonu (models, decomposer, integrator)

metagpt kurulu olmayan ortamlarda çalışır; her modül dosya yolundan
doğrudan yüklenir (mgx_agent/__init__.py zinciri tetiklenmez).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from functools import wraps
from typing import Any
from unittest.mock import AsyncMock, patch
import pytest


def run_async(coro_fn):
    """Sync wrapper — async testleri pytest-asyncio gerektirmeden çalıştırır."""
    @wraps(coro_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro_fn(*args, **kwargs))
    return wrapper

# ---------------------------------------------------------------------------
# 1) metagpt stub kurulumu — pytest modülü import ETMEDEN önce olmalı
# ---------------------------------------------------------------------------
_METAGPT_MODS = [
    "metagpt", "metagpt.actions", "metagpt.logs",
    "metagpt.roles", "metagpt.schema", "metagpt.team",
    "metagpt.context", "metagpt.config",
]
for _mod_name in _METAGPT_MODS:
    sys.modules.setdefault(_mod_name, types.ModuleType(_mod_name))


class _StubAction:
    name: str = "StubAction"
    def __init__(self, **kw): pass
    async def _aask(self, prompt: str) -> str: return ""


class _StubRole:
    pass


class _StubMessage:
    def __init__(self, content: str = "", role: str = "", cause_by: Any = None):
        self.content = content
        self.role = role


sys.modules["metagpt.actions"].Action = _StubAction          # type: ignore[attr-defined]
sys.modules["metagpt.roles"].Role = _StubRole                # type: ignore[attr-defined]
sys.modules["metagpt.schema"].Message = _StubMessage         # type: ignore[attr-defined]
sys.modules["metagpt.logs"].logger = (                       # type: ignore[attr-defined]
    __import__("logging").getLogger("metagpt")
)

# ---------------------------------------------------------------------------
# 2) Modülleri dosya yolundan doğrudan yükle (pkg __init__ bypass)
# ---------------------------------------------------------------------------
import os as _os
_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))


def _load(rel_path: str, module_name: str):
    abs_path = _os.path.join(_ROOT, rel_path.replace("/", _os.sep))
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod_models = _load("mgx_agent/microservice/models.py", "mgx_agent.microservice.models")
_mod_decomp = _load("mgx_agent/microservice/decomposer.py", "mgx_agent.microservice.decomposer")
_mod_integ = _load("mgx_agent/microservice/integrator.py", "mgx_agent.microservice.integrator")

ServiceSpec = _mod_models.ServiceSpec
ServiceResult = _mod_models.ServiceResult
ParallelRunResult = _mod_models.ParallelRunResult

DecomposeTask = _mod_decomp.DecomposeTask
_parse_llm_response = _mod_decomp._parse_llm_response
_single_service_fallback = _mod_decomp._single_service_fallback

IntegrateServices = _mod_integ.IntegrateServices
_parse_files = _mod_integ._parse_files
_fallback_files = _mod_integ._fallback_files


# ===========================================================================
# ServiceSpec
# ===========================================================================
class TestServiceSpec:
    def test_to_dict_round_trip(self):
        sp = ServiceSpec(
            name="user-service",
            description="Handles user auth",
            stack="fastapi",
            port=8001,
            dependencies=["db-service"],
        )
        sp2 = ServiceSpec.from_dict(sp.to_dict())
        assert sp2.name == sp.name
        assert sp2.port == sp.port
        assert sp2.dependencies == sp.dependencies

    def test_from_dict_string_port(self):
        sp = ServiceSpec.from_dict(
            {"name": "svc", "description": "desc", "stack": "fastapi", "port": "8005"}
        )
        assert sp.port == 8005

    def test_from_dict_missing_dependencies(self):
        sp = ServiceSpec.from_dict({"name": "x", "description": "y", "stack": "express-ts"})
        assert sp.dependencies == []

    def test_from_dict_default_port(self):
        sp = ServiceSpec.from_dict({"name": "x", "description": "y", "stack": "express-ts"})
        assert isinstance(sp.port, int)


# ===========================================================================
# ServiceResult
# ===========================================================================
class TestServiceResult:
    def _spec(self):
        return ServiceSpec("svc", "desc", "fastapi", 8001)

    def test_success_to_dict(self):
        sr = ServiceResult(spec=self._spec(), success=True, output="code", duration=3.14)
        d = sr.to_dict()
        assert d["success"] is True
        assert d["output"] == "code"
        assert abs(d["duration"] - 3.14) < 0.01

    def test_failure_to_dict(self):
        sr = ServiceResult(spec=self._spec(), success=False, error="timeout")
        d = sr.to_dict()
        assert d["success"] is False
        assert d["error"] == "timeout"

    def test_long_output_truncated(self):
        sr = ServiceResult(spec=self._spec(), success=True, output="x" * 5000)
        assert len(sr.to_dict()["output"]) <= 2000


# ===========================================================================
# ParallelRunResult
# ===========================================================================
class TestParallelRunResult:
    def _two_results(self):
        sp1 = ServiceSpec("a", "A", "fastapi", 8001)
        sp2 = ServiceSpec("b", "B", "express-ts", 8002)
        return [
            ServiceResult(spec=sp1, success=True),
            ServiceResult(spec=sp2, success=False, error="boom"),
        ]

    def test_stats(self):
        prr = ParallelRunResult(task="build", services=self._two_results(), success=True, duration=10.0)
        d = prr.to_dict()
        assert d["stats"] == {"total": 2, "succeeded": 1, "failed": 1}

    def test_integration_files_in_dict(self):
        prr = ParallelRunResult(
            task="build",
            services=[],
            integration_files={"docker-compose.yml": "version: 3.8", "README.md": "# App"},
            success=True,
            duration=5.0,
        )
        d = prr.to_dict()
        assert "docker-compose.yml" in d["integration_files"]

    def test_long_file_truncated(self):
        prr = ParallelRunResult(
            task="t", services=[],
            integration_files={"big.txt": "x" * 20000},
            success=True, duration=1.0,
        )
        assert len(prr.to_dict()["integration_files"]["big.txt"]) <= 8000


# ===========================================================================
# DecomposeTask — _parse_llm_response
# ===========================================================================
class TestParseLlmResponse:
    def test_valid_json(self):
        payload = json.dumps([
            {"name": "user-service", "description": "User auth", "stack": "fastapi", "port": 8001, "dependencies": []},
            {"name": "order-service", "description": "Orders", "stack": "express-ts", "port": 8002, "dependencies": ["user-service"]},
        ])
        specs = _parse_llm_response(payload, "build")
        assert len(specs) == 2
        assert specs[0].name == "user-service"
        assert specs[1].dependencies == ["user-service"]

    def test_json_in_markdown_fence(self):
        payload = "```json\n" + json.dumps([
            {"name": "svc", "description": "d", "stack": "fastapi", "port": 8001, "dependencies": []}
        ]) + "\n```"
        specs = _parse_llm_response(payload, "task")
        assert len(specs) == 1

    def test_duplicate_ports_auto_reassigned(self):
        payload = json.dumps([
            {"name": "a", "description": "A", "stack": "fastapi", "port": 8001, "dependencies": []},
            {"name": "b", "description": "B", "stack": "fastapi", "port": 8001, "dependencies": []},
        ])
        specs = _parse_llm_response(payload, "build")
        ports = [s.port for s in specs]
        assert len(set(ports)) == len(ports), f"Duplicate ports: {ports}"

    def test_invalid_json_returns_empty(self):
        assert _parse_llm_response("not json", "task") == []

    def test_empty_list_returns_empty(self):
        assert _parse_llm_response("[]", "task") == []

    def test_fallback_creates_single_main_service(self):
        fb = _single_service_fallback("do something complex")
        assert len(fb) == 1
        assert fb[0].name == "main-service"
        assert fb[0].description == "do something complex"


# ===========================================================================
# DecomposeTask.run (async)
# ===========================================================================
class TestDecomposeTaskRun:
    @run_async
    async def test_run_valid_response(self):
        llm_resp = json.dumps([
            {"name": "auth", "description": "Auth API", "stack": "fastapi", "port": 8001, "dependencies": []},
            {"name": "web", "description": "Frontend", "stack": "nextjs", "port": 3000, "dependencies": ["auth"]},
        ])
        action = DecomposeTask()
        with patch.object(action, "_aask", new=AsyncMock(return_value=llm_resp)):
            specs = await action.run("Build a web app")
        assert len(specs) == 2
        assert specs[0].name == "auth"
        assert specs[1].dependencies == ["auth"]

    @run_async
    async def test_run_llm_error_returns_fallback(self):
        action = DecomposeTask()
        with patch.object(action, "_aask", new=AsyncMock(side_effect=RuntimeError("LLM down"))):
            specs = await action.run("Build something")
        assert len(specs) == 1
        assert specs[0].name == "main-service"

    @run_async
    async def test_run_bad_json_returns_fallback(self):
        action = DecomposeTask()
        with patch.object(action, "_aask", new=AsyncMock(return_value="prose without json")):
            specs = await action.run("Build something")
        assert len(specs) == 1

    @run_async
    async def test_run_respects_max_services_prompt(self):
        """max_services parametresi prompt'a dahil olmalı."""
        captured = []
        async def capture_prompt(p):
            captured.append(p)
            return "[]"
        action = DecomposeTask()
        with patch.object(action, "_aask", new=AsyncMock(side_effect=capture_prompt)):
            await action.run("build", max_services=4)
        assert "4" in captured[0]


# ===========================================================================
# IntegrateServices — _parse_files / _fallback_files
# ===========================================================================
class TestParseFiles:
    def _raw(self, files: dict) -> str:
        return "\n".join(
            f"<<<FILE:{name}>>>\n{content}\n<<<END>>>"
            for name, content in files.items()
        )

    def test_all_four_files_parsed(self):
        raw = self._raw({
            "docker-compose.yml": "version: 3.8",
            "nginx/nginx.conf": "http {}",
            "service-contracts.md": "# Contracts",
            "README.md": "# App",
        })
        files = _parse_files(raw)
        assert set(files.keys()) == {
            "docker-compose.yml", "nginx/nginx.conf",
            "service-contracts.md", "README.md",
        }

    def test_content_stripped(self):
        raw = self._raw({"test.yml": "  version: 3  "})
        assert "version" in _parse_files(raw)["test.yml"]

    def test_empty_returns_empty(self):
        assert _parse_files("") == {}

    def test_no_markers_returns_empty(self):
        assert _parse_files("plain prose") == {}


class TestFallbackFiles:
    def _results(self):
        sp1 = ServiceSpec("api", "API", "fastapi", 8001)
        sp2 = ServiceSpec("ui", "UI", "nextjs", 3000, ["api"])
        return [
            ServiceResult(spec=sp1, success=True, output="ok"),
            ServiceResult(spec=sp2, success=True, output="ok"),
        ]

    def test_all_four_files_present(self):
        fb = _fallback_files(self._results())
        assert all(
            k in fb
            for k in ["docker-compose.yml", "nginx/nginx.conf", "service-contracts.md", "README.md"]
        )

    def test_services_in_compose(self):
        fb = _fallback_files(self._results())
        assert "api" in fb["docker-compose.yml"]
        assert "ui" in fb["docker-compose.yml"]

    def test_ports_in_compose(self):
        fb = _fallback_files(self._results())
        assert "8001" in fb["docker-compose.yml"]


# ===========================================================================
# IntegrateServices.run (async)
# ===========================================================================
class TestIntegrateServicesRun:
    def _results(self):
        sp = ServiceSpec("svc", "desc", "fastapi", 8001)
        return [ServiceResult(spec=sp, success=True, output="code")]

    @run_async
    async def test_run_parses_llm_output(self):
        llm_resp = "<<<FILE:docker-compose.yml>>>\nversion: 3.8\n<<<END>>>\n<<<FILE:README.md>>>\n# App\n<<<END>>>"
        action = IntegrateServices()
        with patch.object(action, "_aask", new=AsyncMock(return_value=llm_resp)):
            files = await action.run(self._results())
        assert "docker-compose.yml" in files
        assert "README.md" in files

    @run_async
    async def test_run_fallback_on_llm_error(self):
        action = IntegrateServices()
        with patch.object(action, "_aask", new=AsyncMock(side_effect=Exception("down"))):
            files = await action.run(self._results())
        assert "docker-compose.yml" in files

    @run_async
    async def test_run_fallback_on_bad_markers(self):
        action = IntegrateServices()
        with patch.object(action, "_aask", new=AsyncMock(return_value="no markers")):
            files = await action.run(self._results())
        assert "docker-compose.yml" in files

    @run_async
    async def test_run_empty_services_returns_empty(self):
        action = IntegrateServices()
        files = await action.run([])
        assert files == {}

    @run_async
    async def test_run_includes_failed_service_in_prompt(self):
        sp = ServiceSpec("svc", "desc", "fastapi", 8001)
        failed = ServiceResult(spec=sp, success=False, error="timeout")
        captured = []
        async def capture(p): captured.append(p); return ""
        action = IntegrateServices()
        with patch.object(action, "_aask", new=AsyncMock(side_effect=capture)):
            await action.run([failed])
        assert "FAILED" in captured[0] or "timeout" in captured[0]
