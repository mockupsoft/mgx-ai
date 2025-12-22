# -*- coding: utf-8 -*-
"""Comprehensive project integration smoke tests (Phase 1-8).

These tests are intentionally lightweight and deterministic:
- Validate that public modules import without circular dependency issues
- Validate example wrapper compatibility
- Validate CLI helper flags that are used by project documentation
- Exercise a minimal end-to-end pipeline (stack spec -> guardrails -> formatting)
- Exercise safe patch application in a temporary workspace

They do not call any external APIs (LLM/GitHub) and should be safe in CI.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
class TestPhase1CoreImports:
    def test_import_all_public_modules(self):
        import mgx_agent

        # Ensure package exports are resolvable
        for name in mgx_agent.__all__:
            assert hasattr(mgx_agent, name), f"mgx_agent.__all__ contains missing symbol: {name}"

        # Spot-check key modules for import/circular dependency regressions
        import mgx_agent.config  # noqa: F401
        import mgx_agent.metrics  # noqa: F401
        import mgx_agent.actions  # noqa: F401
        import mgx_agent.roles  # noqa: F401
        import mgx_agent.adapter  # noqa: F401
        import mgx_agent.team  # noqa: F401
        import mgx_agent.cli  # noqa: F401
        import mgx_agent.guardrails  # noqa: F401
        import mgx_agent.diff_writer  # noqa: F401
        import mgx_agent.formatters  # noqa: F401

    def test_examples_mgx_style_team_wrapper_imports(self):
        # examples/ is not a package; execute in isolated namespace.
        example_path = Path(__file__).resolve().parents[2] / "examples" / "mgx_style_team.py"
        ns = runpy.run_path(str(example_path))

        assert "MGXStyleTeam" in ns
        assert "TeamConfig" in ns
        assert "TaskComplexity" in ns


@pytest.mark.integration
class TestPhase7CliHelpers:
    def test_cli_list_stacks_flag_does_not_boot_team(self, monkeypatch, capsys):
        from mgx_agent import cli as cli_module

        monkeypatch.setattr(sys, "argv", ["mgx_agent.cli", "--list-stacks"])
        cli_module.cli_main()

        captured = capsys.readouterr()
        assert "Desteklenen Stack" in captured.out


@pytest.mark.integration
class TestEndToEndFlowsWithoutExternalDependencies:
    def test_flow_fastapi_generation_guardrails_and_formatting(self):
        from mgx_agent.actions import WriteCode
        from mgx_agent.guardrails import validate_output_constraints
        from mgx_agent.stack_specs import get_stack_spec

        spec = get_stack_spec("fastapi")
        assert spec is not None

        manifest = (
            "FILE: app/main.py\n"
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/')\n"
            "def hello():\n"
            "    return {'message': 'hello'}\n"
            "\n"
            "FILE: requirements.txt\n"
            "fastapi\nuvicorn\n"
        )

        result = validate_output_constraints(
            generated_output=manifest,
            stack_spec=spec,
            constraints=["No extra libraries"],
            strict_mode=True,
        )
        assert result.is_valid, f"Guardrails errors: {result.errors}"

        formatted = WriteCode._format_output(manifest, stack_id="fastapi", language="python")
        assert "FILE: app/main.py" in formatted
        assert formatted.endswith("\n")

    def test_flow_nextjs_generation_guardrails(self):
        from mgx_agent.guardrails import validate_output_constraints
        from mgx_agent.stack_specs import get_stack_spec

        spec = get_stack_spec("nextjs")
        assert spec is not None

        manifest = (
            "FILE: next.config.js\n"
            "/** @type {import('next').NextConfig} */\n"
            "const nextConfig = {}\n"
            "module.exports = nextConfig\n"
            "\n"
            "FILE: app/page.tsx\n"
            "export default function Page() {\n"
            "  return <main>User dashboard</main>\n"
            "}\n"
        )

        result = validate_output_constraints(
            generated_output=manifest,
            stack_spec=spec,
            constraints=[],
            strict_mode=True,
        )
        assert result.is_valid, f"Guardrails errors: {result.errors}"

    def test_flow_patch_mode_safe_apply_creates_backup(self, tmp_path: Path):
        from mgx_agent.diff_writer import apply_diff

        target_file = tmp_path / "src" / "server.ts"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("import express from 'express';\nconst app = express();\n")

        diff = (
            "--- a/src/server.ts\n"
            "+++ b/src/server.ts\n"
            "@@ -1,2 +1,3 @@\n"
            " import express from 'express';\n"
            "+app.use((req, _res, next) => { console.log(req.method, req.url); next(); });\n"
            " const app = express();\n"
        )

        result = apply_diff(str(target_file), diff, backup=True)
        assert result.success, result.message
        assert result.backup_file is not None
        assert Path(result.backup_file).exists()
        assert "app.use" in target_file.read_text()
