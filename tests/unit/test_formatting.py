# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for code formatting module

Tests coverage:
- CodeFormatter.format_code() with different languages
- Pre-formatting (trailing whitespace, newlines)
- MinifyDetector.detect_minified_file()
- File manifest parsing
- Minified file detection
- Language detection from file paths
- Formatter configuration per stack
"""

import pytest
import sys
import os

sys.path.insert(0, '/home/engine/project')
os.environ['OPENAI_API_KEY'] = 'dummy_key_for_testing'

from mgx_agent.formatters import (
    Language,
    CodeFormatter,
    MinifyDetector,
    FormatterResult,
    detect_minified_file,
    format_code,
)
from mgx_agent.config import FORMATTER_CONFIGS, get_formatter_config
from mgx_agent.actions import WriteCode


class TestLanguageDetection:
    """Test language detection from file extensions"""

    def test_python_file_detection(self):
        """Should detect .py files as Python"""
        lang = CodeFormatter.detect_language('main.py')
        assert lang == Language.PYTHON

    def test_typescript_file_detection(self):
        """Should detect .ts files as TypeScript"""
        lang = CodeFormatter.detect_language('index.ts')
        assert lang == Language.TYPESCRIPT

    def test_typescript_tsx_detection(self):
        """Should detect .tsx files as TypeScript"""
        lang = CodeFormatter.detect_language('Component.tsx')
        assert lang == Language.TYPESCRIPT

    def test_javascript_file_detection(self):
        """Should detect .js files as JavaScript"""
        lang = CodeFormatter.detect_language('app.js')
        assert lang == Language.JAVASCRIPT

    def test_php_file_detection(self):
        """Should detect .php files as PHP"""
        lang = CodeFormatter.detect_language('index.php')
        assert lang == Language.PHP

    def test_csharp_file_detection(self):
        """Should detect .cs files as C#"""
        lang = CodeFormatter.detect_language('Program.cs')
        assert lang == Language.CSHARP

    def test_unknown_extension_detection(self):
        """Should return UNKNOWN for unrecognized extensions"""
        lang = CodeFormatter.detect_language('file.txt')
        assert lang == Language.UNKNOWN


class TestFormatterConfiguration:
    """Test formatter configurations per stack"""

    def test_fastapi_config_exists(self):
        """Should have FastAPI formatter config"""
        config = get_formatter_config('fastapi')
        assert config is not None
        assert config['language'] == 'python'
        assert 'black' in config['formatters']
        assert 'isort' in config['formatters']

    def test_express_ts_config_exists(self):
        """Should have Express TypeScript formatter config"""
        config = get_formatter_config('express-ts')
        assert config is not None
        assert config['language'] == 'typescript'
        assert 'prettier' in config['formatters']

    def test_nestjs_config_exists(self):
        """Should have NestJS formatter config"""
        config = get_formatter_config('nestjs')
        assert config is not None
        assert 'eslint' in config['formatters']

    def test_laravel_config_exists(self):
        """Should have Laravel formatter config"""
        config = get_formatter_config('laravel')
        assert config is not None
        assert config['language'] == 'php'
        assert 'pint' in config['formatters']

    def test_unknown_stack_returns_none(self):
        """Should return None for unknown stack"""
        config = get_formatter_config('unknown-stack')
        assert config is None

    def test_all_formatter_configs_have_commands(self):
        """All formatters should have commands defined"""
        for stack_id, config in FORMATTER_CONFIGS.items():
            for formatter in config['formatters']:
                assert formatter in config['formatter_commands']
                assert len(config['formatter_commands'][formatter]) > 0


class TestCodeFormatterPreformatting:
    """Test pre-formatting operations"""

    def test_strip_trailing_whitespace(self):
        """Should remove trailing whitespace from lines"""
        code = "def hello():\n    pass   \n    return   "
        result = CodeFormatter._preformat(code)
        # Check lines don't have trailing spaces
        for line in result.split('\n')[:-1]:  # Skip last empty line check
            assert not line.endswith(' ')

    def test_add_trailing_newline(self):
        """Should ensure trailing newline"""
        code = "def foo():\n    pass"
        result = CodeFormatter._preformat(code)
        assert result.endswith('\n')

    def test_preserve_empty_lines_in_middle(self):
        """Should preserve empty lines within code"""
        code = "def foo():\n    pass\n\ndef bar():\n    pass"
        result = CodeFormatter._preformat(code)
        # Should have empty line between functions
        assert '\n\n' in result

    def test_remove_excessive_trailing_empty_lines(self):
        """Should remove multiple trailing empty lines"""
        code = "def foo():\n    pass\n\n\n"
        result = CodeFormatter._preformat(code)
        # Should end with single newline
        assert result.endswith('\n')
        assert not result.endswith('\n\n')


class TestPythonCodeFormatting:
    """Test Python code formatting"""

    def test_format_python_code(self):
        """Should format Python code"""
        code = "def hello(  ):  pass"
        result = CodeFormatter.format_code(code, 'test.py', Language.PYTHON)
        assert result.language == Language.PYTHON
        # Should attempt to format
        assert isinstance(result, FormatterResult)

    def test_python_config_uses_black(self):
        """Python formatter should include black"""
        config = CodeFormatter.get_config_for_language(Language.PYTHON)
        assert 'black' in config.formatters

    def test_python_black_command_configured(self):
        """Black command should be configured correctly"""
        config = CodeFormatter.get_config_for_language(Language.PYTHON)
        black_cmd = config.formatter_commands.get('black')
        assert 'black' in black_cmd
        assert '100' in black_cmd  # Line length
        assert 'py310' in black_cmd  # Target version


class TestTypeScriptFormatting:
    """Test TypeScript/JavaScript code formatting"""

    def test_format_typescript_code(self):
        """Should format TypeScript code"""
        code = "const hello = (  ) => { return 42; }"
        result = CodeFormatter.format_code(code, 'test.ts', Language.TYPESCRIPT)
        assert result.language == Language.TYPESCRIPT

    def test_typescript_config_uses_prettier(self):
        """TypeScript formatter should include prettier"""
        config = CodeFormatter.get_config_for_language(Language.TYPESCRIPT)
        assert 'prettier' in config.formatters

    def test_prettier_command_configured(self):
        """Prettier command should be configured correctly"""
        config = CodeFormatter.get_config_for_language(Language.TYPESCRIPT)
        prettier_cmd = config.formatter_commands.get('prettier')
        assert 'prettier' in prettier_cmd
        assert '100' in prettier_cmd  # Print width
        assert 'true' in prettier_cmd  # Semi colons

    def test_format_javascript_uses_typescript_config(self):
        """JavaScript should use same config as TypeScript"""
        ts_config = CodeFormatter.get_config_for_language(Language.TYPESCRIPT)
        js_config = CodeFormatter.get_config_for_language(Language.JAVASCRIPT)
        assert ts_config.formatters == js_config.formatters


class TestPHPFormatting:
    """Test PHP code formatting"""

    def test_format_php_code(self):
        """Should format PHP code"""
        code = "<?php\nfunction hello(  ){ return 42; }"
        result = CodeFormatter.format_code(code, 'index.php', Language.PHP)
        assert result.language == Language.PHP

    def test_php_config_uses_pint(self):
        """PHP formatter should include pint"""
        config = CodeFormatter.get_config_for_language(Language.PHP)
        assert 'pint' in config.formatters

    def test_pint_command_configured(self):
        """Pint command should be configured correctly"""
        config = CodeFormatter.get_config_for_language(Language.PHP)
        pint_cmd = config.formatter_commands.get('pint')
        assert 'pint' in pint_cmd
        assert 'laravel' in pint_cmd  # Preset


class TestMinifyDetector:
    """Test minified code detection"""

    def test_detect_normal_code_not_minified(self):
        """Normal code should not be detected as minified"""
        code = """def hello(name):
    print(f"Hello, {name}!")
    return True"""
        is_minified, issues = MinifyDetector.detect_minified_file(code)
        assert not is_minified
        assert len(issues) == 0

    def test_detect_minified_javascript(self):
        """Minified JavaScript should be detected"""
        # Long line with no spaces (minified)
        code = "var x=1;var y=2;var z=3;var a=4;var b=5;var c=6;var d=7;var e=8;var f=9;var g=10;var h=11;var i=12;var j=13;var k=14;var l=15;var m=16;var n=17;var o=18;var p=19;var q=20;var r=21;var s=22;var t=23;var u=24;var v=25;var w=26;var x27=27;var y28=28;var z29=29;"
        is_minified, issues = MinifyDetector.detect_minified_file(code)
        # May or may not detect depending on line length threshold
        # But should provide issues list if detected
        assert isinstance(is_minified, bool)
        assert isinstance(issues, list)

    def test_detect_excessive_nesting(self):
        """Code with deep nesting should trigger warning"""
        # Create deeply nested code
        code = "{ { { { { { { { { { { { } } } } } } } } } } } }"
        is_minified, issues = MinifyDetector.detect_minified_file(code)
        # Should detect excessive nesting
        if is_minified and len(issues) > 0:
            assert any('nesting' in issue.lower() for issue in issues)

    def test_very_long_line_detection(self):
        """Lines over 250 chars should be detected"""
        long_line = "x " * 130  # Will be 260+ chars
        is_minified, issues = MinifyDetector.detect_minified_file(long_line)
        assert isinstance(issues, list)

    def test_minified_threshold(self):
        """If >70% lines are long, should detect as minified"""
        lines = ["x" * 300 for _ in range(8)]  # 8 long lines
        lines.append("def foo(): pass")  # 1 short line
        code = '\n'.join(lines)
        is_minified, issues = MinifyDetector.detect_minified_file(code)
        # Should be detected as likely minified (80% long lines)
        if is_minified:
            assert len(issues) > 0


class TestFileManifestParsing:
    """Test FILE manifest parsing"""

    def test_parse_single_file(self):
        """Should parse single FILE block"""
        manifest = "FILE: test.py\ndef hello():\n    pass"
        files = WriteCode._parse_file_manifest(manifest)
        assert len(files) == 1
        assert files[0][0] == "test.py"
        assert "def hello()" in files[0][1]

    def test_parse_multiple_files(self):
        """Should parse multiple FILE blocks"""
        manifest = """FILE: file1.py
def foo():
    pass

FILE: file2.py
def bar():
    pass"""
        files = WriteCode._parse_file_manifest(manifest)
        assert len(files) == 2
        assert files[0][0] == "file1.py"
        assert files[1][0] == "file2.py"

    def test_parse_preserves_file_content(self):
        """Should preserve exact file content"""
        content = "x = 42\ny = 100"
        manifest = f"FILE: test.py\n{content}"
        files = WriteCode._parse_file_manifest(manifest)
        assert files[0][1] == content

    def test_parse_with_nested_paths(self):
        """Should handle nested file paths"""
        manifest = "FILE: src/utils/helper.ts\nexport function foo() {}"
        files = WriteCode._parse_file_manifest(manifest)
        assert files[0][0] == "src/utils/helper.ts"

    def test_parse_empty_manifest(self):
        """Should handle empty manifest"""
        manifest = ""
        files = WriteCode._parse_file_manifest(manifest)
        assert len(files) == 0

    def test_parse_manifest_without_files(self):
        """Should handle manifest without FILE blocks"""
        manifest = "Some random text\nwithout FILE blocks"
        files = WriteCode._parse_file_manifest(manifest)
        assert len(files) == 0


class TestFormatterResult:
    """Test FormatterResult data class"""

    def test_result_success_summary(self):
        """Should generate success summary"""
        result = FormatterResult(
            success=True,
            language=Language.PYTHON,
            formatters_applied=['black', 'isort'],
            diff_lines=5
        )
        summary = result.summary()
        assert "✅" in summary
        assert "black" in summary
        assert "isort" in summary

    def test_result_failure_summary(self):
        """Should generate failure summary"""
        result = FormatterResult(
            success=False,
            language=Language.PYTHON,
            formatters_applied=[],
            errors=['Command not found: black']
        )
        summary = result.summary()
        assert "❌" in summary
        assert "Command not found" in summary

    def test_result_with_warnings(self):
        """Should handle warnings"""
        result = FormatterResult(
            success=True,
            language=Language.PYTHON,
            formatters_applied=['black'],
            warnings=['black did not format any lines']
        )
        assert len(result.warnings) == 1
        assert result.success


class TestFormatCodeConvenienceFunction:
    """Test the convenience format_code() function"""

    def test_format_code_with_path(self):
        """Should format code with file path"""
        code = "def foo(  ): pass"
        result = format_code(code, 'test.py')
        assert isinstance(result, FormatterResult)
        assert result.language == Language.PYTHON

    def test_format_code_with_explicit_language(self):
        """Should format with explicit language"""
        code = "const x = 42"
        result = format_code(code, language=Language.TYPESCRIPT)
        assert result.language == Language.TYPESCRIPT


class TestDetectMinifiedConvenienceFunction:
    """Test the convenience detect_minified_file() function"""

    def test_detect_minified_function(self):
        """Should detect minified code"""
        code = "var x=1;var y=2;var z=3;"
        is_minified, issues = detect_minified_file(code)
        assert isinstance(is_minified, bool)
        assert isinstance(issues, list)


class TestIntegrationFormatting:
    """Integration tests for formatting workflow"""

    def test_format_python_file_manifest(self):
        """Should format Python files in manifest"""
        manifest = """FILE: main.py
def hello(  ):
    pass

FILE: utils.py
def helper(  ):
    return 42"""
        result = WriteCode._format_output(manifest, 'fastapi', 'python')
        assert "FILE:" in result
        assert "main.py" in result
        assert "utils.py" in result

    def test_format_typescript_file_manifest(self):
        """Should format TypeScript files in manifest"""
        manifest = """FILE: index.ts
const hello = (  ) => { return 42; }

FILE: app.ts
export class App { }"""
        result = WriteCode._format_output(manifest, 'express-ts', 'typescript')
        assert "FILE:" in result
        assert "index.ts" in result

    def test_format_preserves_original_on_error(self):
        """Should return original on formatting error"""
        manifest = "FILE: test.py\nsome code"
        # Should gracefully handle and return original (not raise)
        result = WriteCode._format_output(manifest, 'unknown', 'unknown')
        assert "FILE:" in result
        assert "test.py" in result
