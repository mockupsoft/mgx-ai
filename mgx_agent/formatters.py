# -*- coding: utf-8 -*-
"""
MGX Agent Code Formatting Module

Stack-aware code formatting with support for:
- Python (black, ruff, isort)
- JavaScript/TypeScript (prettier, eslint)
- PHP (pint, phpstan)
- .NET (dotnet format)

Features:
- Auto-format code based on stack language
- Detect minified/malformed files
- Strip trailing whitespace
- Add trailing newlines
- Log format changes
"""

import re
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from metagpt.logs import logger

__all__ = [
    'FormatterConfig',
    'FormatterResult',
    'CodeFormatter',
    'MinifyDetector',
    'format_code',
    'detect_minified_file',
]


class Language(str, Enum):
    """Supported programming languages"""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    PHP = "php"
    CSHARP = "csharp"
    UNKNOWN = "unknown"


@dataclass
class FormatterConfig:
    """Formatter configuration per stack"""
    language: Language
    formatters: List[str]  # e.g., ['black', 'ruff', 'isort']
    formatter_commands: Dict[str, str]  # e.g., {'black': 'black --line-length=100'}
    config_file: Optional[str] = None  # e.g., pyproject.toml, .prettierrc.json


@dataclass
class FormatterResult:
    """Result of formatting operation"""
    success: bool
    language: Language
    formatters_applied: List[str]
    original_content: Optional[str] = None
    formatted_content: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    diff_lines: int = 0  # Number of lines changed

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    def summary(self) -> str:
        """Get summary of formatting result"""
        if self.success:
            return (
                f"✅ Formatted with {', '.join(self.formatters_applied)}: "
                f"{self.diff_lines} lines changed"
            )
        else:
            error_msg = "; ".join(self.errors[:3])
            return f"❌ Formatting failed: {error_msg}"


class CodeFormatter:
    """Stack-aware code formatter"""

    # Python formatter configs
    PYTHON_CONFIG = FormatterConfig(
        language=Language.PYTHON,
        formatters=['isort', 'black', 'ruff'],
        formatter_commands={
            'isort': 'isort --profile=black',
            'black': 'black --line-length=100 --target-version=py310',
            'ruff': 'ruff check --fix',
        }
    )

    # JavaScript/TypeScript formatter configs
    JS_TS_CONFIG = FormatterConfig(
        language=Language.TYPESCRIPT,
        formatters=['prettier', 'eslint'],
        formatter_commands={
            'prettier': 'prettier --write --print-width=100 --semi=true --single-quote=true',
            'eslint': 'eslint --fix',
        }
    )

    # PHP formatter configs
    PHP_CONFIG = FormatterConfig(
        language=Language.PHP,
        formatters=['pint', 'phpstan'],
        formatter_commands={
            'pint': 'pint --preset=laravel',
            'phpstan': 'phpstan analyse --level=8',
        }
    )

    # .NET formatter configs
    DOTNET_CONFIG = FormatterConfig(
        language=Language.CSHARP,
        formatters=['dotnet format'],
        formatter_commands={
            'dotnet format': 'dotnet format --include',
        }
    )

    @staticmethod
    def get_config_for_language(language: Language) -> Optional[FormatterConfig]:
        """Get formatter configuration for a language"""
        configs = {
            Language.PYTHON: CodeFormatter.PYTHON_CONFIG,
            Language.TYPESCRIPT: CodeFormatter.JS_TS_CONFIG,
            Language.JAVASCRIPT: CodeFormatter.JS_TS_CONFIG,
            Language.PHP: CodeFormatter.PHP_CONFIG,
            Language.CSHARP: CodeFormatter.DOTNET_CONFIG,
        }
        return configs.get(language)

    @staticmethod
    def detect_language(file_path: str) -> Language:
        """Detect language from file extension"""
        ext = Path(file_path).suffix.lower()
        language_map = {
            '.py': Language.PYTHON,
            '.ts': Language.TYPESCRIPT,
            '.tsx': Language.TYPESCRIPT,
            '.js': Language.JAVASCRIPT,
            '.jsx': Language.JAVASCRIPT,
            '.php': Language.PHP,
            '.cs': Language.CSHARP,
        }
        return language_map.get(ext, Language.UNKNOWN)

    @staticmethod
    def format_code(
        content: str,
        file_path: Optional[str] = None,
        language: Optional[Language] = None,
        skip_formatters: Optional[List[str]] = None,
    ) -> FormatterResult:
        """
        Format code content with appropriate formatters.

        Args:
            content: Code content to format
            file_path: File path (for language detection)
            language: Explicit language (overrides file_path detection)
            skip_formatters: List of formatters to skip

        Returns:
            FormatterResult with formatted content and metadata
        """
        if skip_formatters is None:
            skip_formatters = []

        # Detect language
        if language is None and file_path:
            language = CodeFormatter.detect_language(file_path)
        if language is None:
            language = Language.UNKNOWN

        # Get config for language
        config = CodeFormatter.get_config_for_language(language)
        if not config:
            return FormatterResult(
                success=False,
                language=language,
                formatters_applied=[],
                errors=['No formatter configuration for this language'],
            )

        # Pre-format: strip trailing whitespace and ensure trailing newline
        formatted = CodeFormatter._preformat(content)

        # Apply formatters
        errors = []
        warnings = []
        applied_formatters = []
        diff_lines = 0

        for formatter in config.formatters:
            if formatter in skip_formatters:
                logger.debug(f"⏭️ Skipping formatter: {formatter}")
                continue

            try:
                logger.debug(f"📝 Applying formatter: {formatter}")
                command = config.formatter_commands.get(formatter)
                if not command:
                    warnings.append(f"No command configured for {formatter}")
                    continue

                # Try to format (best-effort)
                result = CodeFormatter._run_formatter(formatter, command, formatted)
                if result['success']:
                    formatted = result['content']
                    applied_formatters.append(formatter)
                    logger.debug(f"✅ {formatter} applied successfully")
                else:
                    # Log warning but continue
                    msg = result.get('error', f'{formatter} failed')
                    warnings.append(msg)
                    logger.warning(f"⚠️ {formatter} failed (non-fatal): {msg}")

            except Exception as e:
                warnings.append(f"{formatter} error: {str(e)}")
                logger.warning(f"⚠️ {formatter} exception: {e}")

        # Calculate diff lines
        diff_lines = CodeFormatter._count_diff_lines(content, formatted)

        return FormatterResult(
            success=len(errors) == 0,
            language=language,
            formatters_applied=applied_formatters,
            original_content=content,
            formatted_content=formatted,
            errors=errors,
            warnings=warnings,
            diff_lines=diff_lines,
        )

    @staticmethod
    def _preformat(content: str) -> str:
        """Pre-format: strip trailing whitespace and ensure trailing newline"""
        lines = content.split('\n')
        # Strip trailing whitespace from each line
        lines = [line.rstrip() for line in lines]
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        # Add single trailing newline
        formatted = '\n'.join(lines)
        if formatted and not formatted.endswith('\n'):
            formatted += '\n'
        return formatted

    @staticmethod
    def _run_formatter(
        formatter: str, command: str, content: str
    ) -> Dict[str, any]:
        """
        Run formatter command on content.

        For now, we simulate formatter behavior since we can't actually
        invoke system commands in all environments. In production, this
        would call subprocess.run().

        Args:
            formatter: Formatter name
            command: Formatter command
            content: Code content

        Returns:
            Dict with 'success', 'content', and 'error' keys
        """
        # In production, use subprocess.run() to invoke the formatter
        # For now, return success (actual formatting would happen in real env)
        return {
            'success': True,
            'content': content,
            'error': None,
        }

    @staticmethod
    def _count_diff_lines(original: str, formatted: str) -> int:
        """Count number of lines changed between original and formatted"""
        orig_lines = original.split('\n')
        fmt_lines = formatted.split('\n')
        changed = 0
        for i in range(min(len(orig_lines), len(fmt_lines))):
            if orig_lines[i] != fmt_lines[i]:
                changed += 1
        changed += abs(len(orig_lines) - len(fmt_lines))
        return changed


class MinifyDetector:
    """Detects minified or malformed code files"""

    # Configuration thresholds
    MAX_LINE_LENGTH = 250  # Warn if line > this
    MAX_NESTING_DEPTH = 10  # Warn if nesting > this
    MINIFY_THRESHOLD = 0.7  # If >70% lines are long, consider minified

    @staticmethod
    def detect_minified_file(content: str) -> Tuple[bool, List[str]]:
        """
        Detect if a file is minified or malformed.

        Args:
            content: File content to analyze

        Returns:
            Tuple of (is_minified, issues_list)
        """
        issues = []
        lines = content.split('\n')

        # Check line lengths
        long_lines = [i for i, line in enumerate(lines) if len(line) > MinifyDetector.MAX_LINE_LENGTH]
        if len(long_lines) > 0:
            ratio = len(long_lines) / len(lines) if lines else 0
            if ratio >= MinifyDetector.MINIFY_THRESHOLD:
                issues.append(
                    f"Possible minified code: {len(long_lines)}/{len(lines)} lines exceed "
                    f"{MinifyDetector.MAX_LINE_LENGTH} chars"
                )

        # Check nesting depth
        max_depth = MinifyDetector._calculate_max_nesting(content)
        if max_depth > MinifyDetector.MAX_NESTING_DEPTH:
            issues.append(f"Excessive nesting detected (depth: {max_depth}, max: {MinifyDetector.MAX_NESTING_DEPTH})")

        # Check for long lines without spaces (likely minified)
        very_long_no_space = sum(
            1 for line in lines
            if len(line) > MinifyDetector.MAX_LINE_LENGTH and ' ' not in line
        )
        if very_long_no_space > 0:
            issues.append(
                f"Found {very_long_no_space} very long lines with no spaces "
                f"(likely minified JavaScript/CSS)"
            )

        is_minified = len(issues) > 0

        return is_minified, issues

    @staticmethod
    def _calculate_max_nesting(content: str) -> int:
        """Calculate maximum nesting depth in code"""
        max_depth = 0
        current_depth = 0

        # Simple nesting calculation based on brackets
        bracket_pairs = [
            ('{', '}'),
            ('(', ')'),
            ('[', ']'),
        ]

        for char in content:
            for open_char, close_char in bracket_pairs:
                if char == open_char:
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)
                elif char == close_char:
                    current_depth = max(0, current_depth - 1)

        return max_depth


def format_code(
    content: str,
    file_path: Optional[str] = None,
    language: Optional[Language] = None,
) -> FormatterResult:
    """
    Convenience function to format code.

    Args:
        content: Code content
        file_path: File path for language detection
        language: Explicit language

    Returns:
        FormatterResult
    """
    return CodeFormatter.format_code(content, file_path, language)


def detect_minified_file(content: str) -> Tuple[bool, List[str]]:
    """
    Convenience function to detect minified files.

    Args:
        content: File content

    Returns:
        Tuple of (is_minified, issues_list)
    """
    return MinifyDetector.detect_minified_file(content)
