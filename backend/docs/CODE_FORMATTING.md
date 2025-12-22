# Code Formatting & Pre-commit Hooks Guide

## Overview

This guide covers code formatting, style standardization, and pre-commit hook configuration for MGX Agent projects across all supported stacks.

**Key Goals:**
- Ensure consistent code style across projects
- Prevent unformatted code from being committed
- Reduce manual code review friction
- Support multiple programming languages and frameworks

---

## Formatter Configuration per Stack

### Python (FastAPI, Backend)

**Formatters:**
- **black** - Code formatter (line-length=100, target-version=py310)
- **ruff** - Fast linter (includes E, F, W rules)
- **isort** - Import sorter (profile=black)

**Configuration:**
```python
from mgx_agent.config import FORMATTER_CONFIGS

config = FORMATTER_CONFIGS['fastapi']
# {
#   'language': 'python',
#   'formatters': ['isort', 'black', 'ruff'],
#   'formatter_commands': {
#       'isort': 'isort --profile=black',
#       'black': 'black --line-length=100 --target-version=py310',
#       'ruff': 'ruff check --fix',
#   }
# }
```

**Line Length:** 100 characters
**Target Version:** Python 3.10+
**Import Style:** Black-compatible

**Local Setup:**
```bash
pip install black ruff isort
```

**Run Formatters:**
```bash
isort .                  # Sort imports
black .                  # Format code
ruff check --fix .       # Lint and fix
```

---

### JavaScript/TypeScript (Express, NestJS, Next.js, React+Vite, Vue+Vite)

**Formatters:**
- **prettier** - Code formatter (printWidth=100, semi=true, singleQuote=true)
- **eslint** - Linter (extends recommended + framework-specific)

**Configuration:**
```python
config = FORMATTER_CONFIGS['express-ts']
# {
#   'language': 'typescript',
#   'formatters': ['prettier', 'eslint'],
#   'formatter_commands': {
#       'prettier': 'prettier --write --print-width=100 --semi=true --single-quote=true',
#       'eslint': 'eslint --fix',
#   }
# }
```

**Print Width:** 100 characters
**Semicolons:** True (required)
**Quotes:** Single quotes (')

**Local Setup:**
```bash
npm install --save-dev prettier eslint @typescript-eslint/eslint-plugin
```

**Run Formatters:**
```bash
npx prettier --write .
npx eslint --fix .
```

**With Next.js:**
```bash
npm install --save-dev eslint-config-next
# Add to .eslintrc.json:
# "extends": ["next", "plugin:@typescript-eslint/recommended"]
```

---

### PHP (Laravel)

**Formatters:**
- **pint** - PHP code formatter (preset=laravel)
- **phpstan** - Static analysis (level=8, optional)

**Configuration:**
```python
config = FORMATTER_CONFIGS['laravel']
# {
#   'language': 'php',
#   'formatters': ['pint', 'phpstan'],
#   'formatter_commands': {
#       'pint': 'pint --preset=laravel',
#       'phpstan': 'phpstan analyse --level=8',
#   }
# }
```

**Preset:** Laravel (PSR-12 compatible)
**Type Level:** 8 (strict)

**Local Setup:**
```bash
composer require --dev laravel/pint
composer require --dev phpstan/phpstan
```

**Run Formatters:**
```bash
./vendor/bin/pint
./vendor/bin/phpstan analyse app routes tests
```

---

### .NET / C# (Optional)

**Formatters:**
- **dotnet format** - C# code formatter

**Configuration:**
```python
config = FORMATTER_CONFIGS['dotnet-api']
# {
#   'language': 'csharp',
#   'formatters': ['dotnet format'],
#   'formatter_commands': {
#       'dotnet format': 'dotnet format --include',
#   }
# }
```

**Local Setup:**
```bash
dotnet tool install -g dotnet-format
```

**Run Formatter:**
```bash
dotnet format
```

---

## Pre-commit Hook Configuration

Pre-commit hooks automatically run formatters before each commit, preventing unformatted code from entering the repository.

### Installation

**1. Install pre-commit:**
```bash
pip install pre-commit
# or
brew install pre-commit
```

**2. Choose configuration template:**

Choose based on your project type:

**Python Projects:**
```bash
cp docs/.pre-commit-config-python.yaml .pre-commit-config.yaml
```

**Node.js/TypeScript Projects:**
```bash
cp docs/.pre-commit-config-node.yaml .pre-commit-config.yaml
```

**PHP Projects:**
```bash
cp docs/.pre-commit-config-php.yaml .pre-commit-config.yaml
```

**3. Install hooks:**
```bash
pre-commit install
pre-commit install --hook-type commit-msg  # Optional: for commit message linting
```

**4. Run on all files (first time):**
```bash
pre-commit run --all-files
```

### Running Pre-commit

**Automatic (on commit):**
```bash
git add .
git commit -m "Add feature"  # Hooks run automatically
```

**Manual (on specific files):**
```bash
pre-commit run --files src/*.py
pre-commit run --files app.ts
```

**Run all hooks on all files:**
```bash
pre-commit run --all-files
```

### Skipping Hooks (Not Recommended)

If you need to bypass hooks temporarily:
```bash
git commit --no-verify
```

**Note:** Using `--no-verify` bypasses all safety checks. Use with caution!

### Customizing Configuration

Edit `.pre-commit-config.yaml` to:

**Exclude files:**
```yaml
exclude: |
  (?x)^(
    migrations/|
    build/|
    vendor/
  )
```

**Modify arguments:**
```yaml
- id: black
  args: ['--line-length=88']  # Change line length
```

**Disable specific hooks:**
Comment out or remove the hook entry.

---

## WriteCode Auto-formatting

When `WriteCode` action generates files in FILE manifest mode, it automatically formats each file based on the target stack.

### How It Works

1. Parse FILE manifest output from LLM
2. Detect language from file extension
3. Apply stack-appropriate formatters
4. Log format changes (non-fatal on errors)
5. Return formatted manifest

### Example Flow

```python
from mgx_agent.actions import WriteCode

action = WriteCode()
result = await action.run(
    instruction="Create API endpoint",
    target_stack="fastapi"
)
# Automatically formats Python files with black, isort, ruff
```

### Format Detection

Files are formatted based on:

1. **Target Stack** → language (e.g., fastapi → python)
2. **File Extension** → language (e.g., .ts → typescript)
3. **Formatter Config** → tools to apply

### Minified File Detection

`WriteCode` warns about potentially minified files:

- Lines > 250 characters → suspicious
- > 10 levels of nesting → suspicious
- > 70% lines are long → likely minified

Example log:
```
⚠️ File app.js may be minified: Possible minified code: 8/10 lines exceed 250 chars
```

### Best-Effort Formatting

Formatting is **non-fatal**:
- If formatter fails: log warning, continue
- Original content returned on error
- Task never fails due to formatting

---

## Test File Formatting

After `WriteTest` generates test files, they are automatically formatted for readability:

```python
from mgx_agent.actions import WriteTest

action = WriteTest()
result = await action.run(code=source_code)
# Test output is automatically formatted and cleaned
```

### Cleanup Applied

- Trailing whitespace removed
- Proper line endings ensured
- Consistent indentation
- Imports sorted (Python)
- Code aligned (JavaScript/PHP)

---

## Minified/Malformed File Detection

Utility to detect and warn about problematic code patterns:

```python
from mgx_agent.formatters import detect_minified_file

code = open('app.js').read()
is_minified, issues = detect_minified_file(code)

if is_minified:
    print("⚠️ Issues:", issues)
    # [
    #   "Possible minified code: 15/20 lines exceed 250 chars",
    #   "Excessive nesting detected (depth: 12, max: 10)"
    # ]
```

### Thresholds

| Issue | Threshold |
|-------|-----------|
| Long line | > 250 characters |
| Nesting depth | > 10 levels |
| Minified indicator | > 70% long lines |

---

## Troubleshooting

### Formatter Not Found

**Error:** `Command not found: black`

**Solution:**
```bash
# Python
pip install black isort ruff

# Node.js
npm install --save-dev prettier eslint

# PHP
composer require --dev laravel/pint
```

### Pre-commit Hook Not Running

**Error:** Hooks not executing on commit

**Solution:**
```bash
# Reinstall hooks
pre-commit install

# Verify installation
cat .git/hooks/pre-commit
```

### Pre-commit Takes Too Long

**Solution - Run on staged files only:**
```bash
# Edit .pre-commit-config.yaml
stages: [commit]
```

**Or skip expensive hooks:**
```bash
# Comment out mypy, phpstan
```

### Line Length Conflicts

Different formatters have different defaults:

| Formatter | Default | Recommended |
|-----------|---------|-------------|
| Black | 88 | 100 (configured) |
| Prettier | 80 | 100 (configured) |
| Pint | 120 | 100 (via config file) |

**Solution:** Use configuration files in project root:

**pyproject.toml (Python):**
```toml
[tool.black]
line-length = 100

[tool.isort]
profile = "black"
line_length = 100
```

**.prettierrc.json (JavaScript):**
```json
{
  "printWidth": 100,
  "semi": true,
  "singleQuote": true
}
```

**pint.json (PHP):**
```json
{
  "preset": "laravel"
}
```

### Commit Message Too Long

Pre-commit may check commit message length:

**Solution:** Edit message or increase limit in config:
```yaml
- id: commit-msg
  args: ['--max-length=100']
```

---

## Integration with TaskExecutor

When `TaskExecutor` runs a task:

1. **After WriteCode:**
   - Receives FILE manifest
   - Auto-formats output
   - Emits `code_formatted` event (optional)

2. **Before Creating PR:**
   - Runs formatters on changes
   - Ensures clean git diff
   - Commits with formatted code

3. **WebSocket Events:**
   ```javascript
   // Monitor formatting
   ws.onmessage = (event) => {
     if (event.data.type === 'code_formatted') {
       console.log(`Formatted ${event.data.files_count} files`);
     }
   };
   ```

---

## Local Development Setup

### Python Project

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install formatters
pip install black ruff isort mypy

# Install pre-commit
pip install pre-commit

# Setup hooks
cp docs/.pre-commit-config-python.yaml .pre-commit-config.yaml
pre-commit install
pre-commit run --all-files
```

### Node.js Project

```bash
# Install formatters
npm install --save-dev prettier eslint @typescript-eslint/eslint-plugin

# Install pre-commit
npm install -g pre-commit

# Setup hooks
cp docs/.pre-commit-config-node.yaml .pre-commit-config.yaml
pre-commit install
pre-commit run --all-files
```

### PHP Project

```bash
# Install formatters
composer require --dev laravel/pint phpstan/phpstan

# Install pre-commit
# Use system pre-commit or composer script

# Setup hooks
cp docs/.pre-commit-config-php.yaml .pre-commit-config.yaml
pre-commit install
```

---

## Common Formatting Issues

### Issue: Black and Prettier Differ

**Problem:** Black (Python) and Prettier (JS) have different line-length preferences.

**Solution:** Configure both to use 100 chars (as in MGX defaults).

### Issue: Import Order Conflicts

**Problem:** isort and ruff have different import ordering.

**Solution:** Use `isort --profile=black` (configured by default).

### Issue: Trailing Commas

**Problem:** Prettier adds trailing commas, some linters don't like them.

**Solution:** Configure both to allow trailing commas:
```json
{
  "trailingComma": "es5"
}
```

### Issue: Semicolons in JavaScript

**Problem:** Some projects omit semicolons.

**Solution:** Prettier and ESLint configured to require them (MGX default).

---

## API Reference

### CodeFormatter.format_code()

```python
from mgx_agent.formatters import CodeFormatter, Language

result = CodeFormatter.format_code(
    content="def foo(): pass",
    file_path="test.py",  # Optional, for language detection
    language=Language.PYTHON  # Optional, explicit language
)

# Returns FormatterResult with:
# - success: bool
# - formatters_applied: List[str]
# - formatted_content: str
# - errors: List[str]
# - warnings: List[str]
```

### MinifyDetector.detect_minified_file()

```python
from mgx_agent.formatters import MinifyDetector

is_minified, issues = MinifyDetector.detect_minified_file(code)

# Returns:
# - is_minified: bool
# - issues: List[str] (descriptions of problems)
```

### get_formatter_config()

```python
from mgx_agent.config import get_formatter_config

config = get_formatter_config('fastapi')
# config = {
#   'language': 'python',
#   'formatters': [...],
#   'formatter_commands': {...}
# }
```

---

## FAQ

**Q: Do I have to use pre-commit hooks?**
A: No, they're optional. But highly recommended for team projects.

**Q: What if a formatter breaks my code?**
A: Formatters are designed to preserve semantics. If code breaks, report the issue.

**Q: Can I skip specific files?**
A: Yes, use `exclude` in `.pre-commit-config.yaml`.

**Q: How often should I run formatters?**
A: On every commit (via pre-commit) or manually before pushing.

**Q: What about code review formatting feedback?**
A: Most formatting should be automated. Code review should focus on logic, not style.

---

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Prettier Documentation](https://prettier.io/docs/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [Laravel Pint](https://laravel.com/docs/pint)
- [Pre-commit Documentation](https://pre-commit.com/)
- [ESLint Rules](https://eslint.org/docs/rules/)

---

**Phase 8.3 - Code Formatting & Pre-commit Complete** ✅
