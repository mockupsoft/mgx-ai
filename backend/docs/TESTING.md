# 🧪 Testing Guide - TEM Agent

Comprehensive guide to the TEM Agent test infrastructure, fixtures, and best practices.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Setup](#setup)
3. [Running Tests](#running-tests)
4. [Test Structure](#test-structure)
5. [Fixtures](#fixtures)
6. [Test Helpers & Stubs](#test-helpers--stubs)
7. [Writing Tests](#writing-tests)
8. [Coverage](#coverage)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The TEM Agent project uses **pytest** as its testing framework with comprehensive support for:

- **Unit tests**: Fast, isolated tests for individual functions
- **Integration tests**: Tests verifying component interactions
- **End-to-end tests**: Complete workflow tests
- **Async testing**: Built-in asyncio support via pytest-asyncio
- **Coverage tracking**: Automated coverage reports (HTML, XML, terminal)
- **MetaGPT stubs**: Lightweight mocks for MetaGPT components (no network calls)

### Current Status

```
Phase 3: Testing Infrastructure ✅
├─ pytest.ini configuration      ✅ Complete
├─ requirements-dev.txt          ✅ Complete  
├─ Test directory structure      ✅ Complete
├─ MetaGPT stubs & factories     ✅ Complete
├─ Test fixtures                 ✅ Complete
└─ Smoke tests                   ✅ Passing
```

**Coverage Target**: 80%+ (current: ~71%; see PROJECT_STATUS.md)

---

## Setup

### Installation

```bash
# 1. Install test dependencies
pip install -r requirements-dev.txt

# 2. Verify pytest is installed
pytest --version

# 3. Check pytest can collect tests
pytest --collect-only
```

### Verify Setup

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_helpers.py

# Run specific test class
pytest tests/unit/test_helpers.py::TestMockLogger

# Run specific test function
pytest tests/unit/test_helpers.py::TestMockLogger::test_logger_creation
```

---

## Running Tests

### Common Commands

```bash
# Run all tests with coverage report
pytest

# Run specific test level
pytest tests/unit              # Unit tests only
pytest tests/integration       # Integration tests only
pytest tests/e2e              # End-to-end tests only

# Run with output options
pytest -v                      # Verbose output
pytest -s                      # Show print statements
pytest -x                      # Stop on first failure
pytest -k "keyword"            # Run tests matching keyword

# Run with markers
pytest -m asyncio              # Async tests only
pytest -m "not slow"           # Skip slow tests

# Performance/load tests (excluded by default via pytest.ini addopts)
pytest -o addopts='' -m performance tests/performance -v

# Parallel execution (faster)
pytest -n auto                 # Use all CPU cores

# Run with specific log level
pytest --log-cli-level=DEBUG   # Show debug logs
```

Performance suite notes:

- Generates artifacts in `perf_reports/` (`latest.json`, `before_after.md`)
- Compares against the committed baseline `perf_reports/baseline.json`

See [docs/PERFORMANCE.md](PERFORMANCE.md) for configuration flags, profiling usage, and the CI workflow.

### Coverage Reports

```bash
# Terminal report (default)
pytest
# Shows missing lines and coverage percentage

# Generate HTML report
pytest --cov=mgx_agent --cov-report=html
# Open: htmlcov/index.html

# Generate XML report (for CI/CD)
pytest --cov=mgx_agent --cov-report=xml
# Use in: GitHub Actions, GitLab CI, etc.

# Combined reports
pytest --cov=mgx_agent --cov-report=term-missing --cov-report=html --cov-report=xml

# Coverage by specific module
pytest --cov=mgx_agent.roles tests/unit
```

---

## Test Structure

### Directory Layout

```
tests/
├── __init__.py                  # Package init
├── conftest.py                  # Global fixtures & configuration
├── pytest.ini                   # Pytest config (in project root)
│
├── unit/                        # Fast, isolated tests
│   ├── __init__.py
│   ├── test_helpers.py         # Tests for test infrastructure
│   ├── test_config.py          # Tests for config module
│   ├── test_metrics.py         # Tests for metrics module
│   ├── test_actions.py         # Tests for actions module
│   ├── test_adapter.py         # Tests for adapter module
│   ├── test_roles.py           # Tests for roles module
│   └── test_team.py            # Tests for team module
│
├── integration/                 # Component interaction tests
│   ├── __init__.py
│   ├── test_team_roles.py      # Team + Roles integration
│   ├── test_adapter_roles.py   # Adapter + Roles integration
│   └── test_workflow.py        # Complete workflow tests
│
├── e2e/                        # Complete workflow tests
│   ├── __init__.py
│   ├── test_full_pipeline.py  # Complete pipeline
│   └── test_user_scenarios.py # Real-world use cases
│
├── helpers/                    # Test utilities & stubs
│   ├── __init__.py
│   ├── metagpt_stubs.py       # MetaGPT component stubs
│   └── factories.py           # Factory functions
│
└── logs/                       # Test logs directory
    └── pytest.log             # Pytest log file
```

### Test File Structure

```python
# tests/unit/test_module.py

import pytest
from mgx_agent.module import MyClass

class TestMyClass:
    """Tests for MyClass."""
    
    def test_basic_functionality(self):
        """Test basic feature."""
        obj = MyClass()
        assert obj is not None
    
    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async feature."""
        obj = MyClass()
        result = await obj.async_method()
        assert result is not None
    
    def test_with_fixtures(self, fake_team, fake_role):
        """Test using fixtures."""
        team = fake_team
        team.hire(fake_role)
        assert len(team.roles) == 1
```

---

## Fixtures

### Global Fixtures (from conftest.py)

#### Event Loop Fixture

```python
def test_async_operation(event_loop):
    """Async tests automatically get a fresh event loop."""
    # Fixture is automatically used for @pytest.mark.asyncio tests
    pass
```

#### Team Fixtures

```python
def test_with_team(fake_team):
    """Get a team with 4 default roles."""
    assert len(fake_team.roles) == 4

def test_custom_team(fake_team_with_custom_roles):
    """Factory fixture for custom teams."""
    team = fake_team_with_custom_roles(
        role_names=["Engineer", "Tester", "Reviewer"]
    )
    assert len(team.roles) == 3
```

#### Role Fixtures

```python
def test_with_role(fake_role):
    """Get a role with 2 default actions."""
    assert len(fake_role.actions) == 2
```

#### Memory Fixtures

```python
def test_with_memory(fake_memory):
    """Get an empty memory store."""
    fake_memory.add("key", "value")
    assert fake_memory.get("key") == "value"

def test_with_memory_data(fake_memory_with_data):
    """Get memory with initial data."""
    assert fake_memory_with_data.get("task") == "Test Task"
    assert len(fake_memory_with_data.get_messages()) > 0
```

#### Message Fixtures

```python
def test_with_message(fake_message):
    """Factory fixture for creating messages."""
    msg = fake_message(role="user", content="Hello")
    assert msg.content == "Hello"
```

#### LLM Response Fixtures

```python
def test_with_llm_response(fake_llm_response):
    """Factory fixture for LLM responses."""
    response = fake_llm_response(content="Generated code")
    assert "Generated code" in response.content

def test_with_mock_llm(async_mock_llm):
    """Factory fixture for async mock LLMs."""
    mock = async_mock_llm(responses=["Response 1", "Response 2"])
    result = await mock("prompt")
    assert "Response 1" in result
```

#### Directory Fixtures

```python
def test_with_output_dir(tmp_output_dir):
    """Get a temporary output directory."""
    output_file = tmp_output_dir / "output.txt"
    output_file.write_text("test")
    assert output_file.exists()

def test_with_logs_dir(tmp_logs_dir):
    """Get a temporary logs directory."""
    log_file = tmp_logs_dir / "test.log"
    log_file.write_text("log content")
    assert log_file.exists()
```

#### Logging Fixtures

```python
def test_with_caplog(caplog_setup):
    """Capture and verify logs."""
    logger = logging.getLogger(__name__)
    logger.info("Test message")
    
    assert "Test message" in caplog_setup.text
```

---

## Test Helpers & Stubs

### MetaGPT Stubs

Since tests should run without the real MetaGPT package or network calls, we provide lightweight stubs:

#### Available Stubs

```python
from tests.helpers import (
    MockAction,      # Stub for metagpt.Action
    MockRole,        # Stub for metagpt.Role
    MockTeam,        # Stub for metagpt.Team
    MockMessage,     # Stub for metagpt.types.Message
    mock_logger,     # Stub for metagpt.logs.logger
)
```

#### Automatic Registration

The stubs are automatically registered in `sys.modules` in `tests/conftest.py`:

```python
sys.modules['metagpt'] = MetaGPTStub()
sys.modules['metagpt.logs'] = MetaGPTLogsStub()
sys.modules['metagpt.types'] = MetaGPTTypesStub()
```

This allows tests to import and use MetaGPT components without errors.

### Factory Functions

#### Team Factory

```python
from tests.helpers import create_fake_team

# Basic usage
team = create_fake_team()  # 4 default roles

# Custom
team = create_fake_team(
    name="CustomTeam",
    role_names=["Mike", "Alex", "Bob", "Charlie"]
)
```

#### Role Factory

```python
from tests.helpers import create_fake_role

role = create_fake_role(
    name="Engineer",
    goal="Write code",
    num_actions=3
)
```

#### Action Factory

```python
from tests.helpers import create_fake_action

action = create_fake_action(
    name="WriteCode",
    run_result="Generated code"
)

result = await action.run()
```

#### Memory Factory

```python
from tests.helpers import create_fake_memory_store

memory = create_fake_memory_store(
    initial_data={"key": "value"},
    initial_messages=[msg1, msg2]
)
```

#### LLM Response Factory

```python
from tests.helpers import (
    create_fake_llm_response,
    create_async_mock_llm
)

# Fake response
response = create_fake_llm_response(
    content="Generated code",
    completion_tokens=50
)

# Async mock LLM
mock_llm = create_async_mock_llm(
    responses=["Response 1", "Response 2"]
)
result = await mock_llm("prompt")
```

---

## Writing Tests

### Unit Test Example

```python
# tests/unit/test_myfeature.py

import pytest
from mgx_agent.module import MyClass

class TestMyClass:
    """Test suite for MyClass."""
    
    def test_initialization(self):
        """Test object initialization."""
        obj = MyClass(param="value")
        assert obj.param == "value"
    
    def test_method_returns_expected_value(self):
        """Test method returns correct value."""
        obj = MyClass()
        result = obj.method()
        assert result is not None
        assert isinstance(result, str)
    
    def test_exception_on_invalid_input(self):
        """Test exception handling."""
        obj = MyClass()
        with pytest.raises(ValueError):
            obj.method(invalid_param="test")
```

### Async Test Example

```python
# tests/unit/test_async_feature.py

import pytest
from mgx_agent.module import AsyncClass

class TestAsyncClass:
    """Test suite for async features."""
    
    @pytest.mark.asyncio
    async def test_async_method(self):
        """Test async method."""
        obj = AsyncClass()
        result = await obj.async_method()
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_async_with_mock_team(self, fake_team):
        """Test async with fixtures."""
        obj = AsyncClass(team=fake_team)
        result = await obj.process()
        assert result is not None
```

### Integration Test Example

```python
# tests/integration/test_team_workflow.py

import pytest
from mgx_agent.team import MGXStyleTeam
from mgx_agent.roles import Mike, Alex

@pytest.mark.integration
class TestTeamWorkflow:
    """Test team workflow integration."""
    
    @pytest.mark.asyncio
    async def test_team_execution(self, fake_team):
        """Test complete team execution."""
        # Run team
        result = await fake_team.run(max_iterations=3)
        
        # Verify results
        assert fake_team.is_running is False
        assert fake_team.run_count == 1
```

### Test with Markers

```python
@pytest.mark.asyncio
def test_async_operation():
    """Mark test as async."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Mark test as slow (use: pytest -m "not slow")."""
    pass

@pytest.mark.integration
def test_integration():
    """Mark test as integration."""
    pass
```

---

## Coverage

### Understanding Coverage Reports

The terminal coverage report shows:

```
mgx_agent/config.py    87    4    95%   23-25, 45
mgx_agent/roles.py    189   12    94%   45-50, 100-102
...
```

Columns:
- **Module**: File path
- **Statements**: Total lines of code
- **Missing**: Lines not executed in tests
- **Coverage**: Percentage of code covered
- **Missing lines**: Line numbers not covered

### Achieving 80% Coverage Target

1. **Identify gaps**:
   ```bash
   pytest --cov=mgx_agent --cov-report=term-missing
   ```

2. **Write tests for missing lines**:
   ```python
   def test_untested_branch():
       # Test code path not yet covered
       pass
   ```

3. **Track progress**:
   ```bash
   # Repeat coverage check
   pytest --cov=mgx_agent --cov-report=term-missing
   ```

### HTML Coverage Reports

```bash
# Generate HTML report
pytest --cov=mgx_agent --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\index.html  # Windows
```

The HTML report provides:
- Color-coded coverage visualization
- Line-by-line coverage details
- Branch coverage analysis
- Clickable file navigation

### Coverage Requirements

This project maintains strict quality standards:

```bash
# Verify 80% coverage requirement
pytest --cov=mgx_agent --cov-report=term-missing

# Check test count requirement (≥130 tests)
pytest --collect-only -q | tail -1
```

**Quality Gates**:
- ✅ **Test Count**: ≥130 tests (current: 310 tests)
- ✅ **Coverage**: ≥80% overall coverage
- ✅ **HTML Reports**: Generated under `htmlcov/`
- ✅ **XML Reports**: Generated as `coverage.xml`

### Comprehensive Coverage Commands

```bash
# Run tests with all coverage reports
pytest --cov=mgx_agent \
       --cov-report=html:htmlcov \
       --cov-report=xml:coverage.xml \
       --cov-report=term-missing

# Expected output files:
# - coverage.xml (XML format for CI/CD tools)
# - htmlcov/ (HTML reports directory)
# - .coverage (binary coverage data)

# View coverage in terminal
coverage report --show-missing

# Generate XML report explicitly
coverage xml -o coverage.xml

# Check coverage percentage
pytest --cov=mgx_agent --cov-report=term-missing | tail -1
```

### CI/CD Integration

#### GitHub Actions Workflow

The project includes a comprehensive GitHub Actions workflow (`.github/workflows/tests.yml`) that automatically:

1. **Installs dependencies** including `pytest-cov` for coverage
2. **Runs unit, integration, and E2E tests** with coverage tracking
3. **Generates HTML and XML coverage reports**
4. **Uploads coverage artifacts** for each Python version
5. **Validates quality gates** (≥130 tests, ≥80% coverage)

```yaml
# Trigger conditions
on:
  push:
    branches: [ main, test-cli-workflows-coverage-ci-docs ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:
```

#### Automated Quality Checks

The workflow performs automated quality validation:

```bash
# Test count validation (≥130 tests)
TEST_COUNT=$(pytest --collect-only -q | grep -o '[0-9]*')
if [ "$TEST_COUNT" -lt 130 ]; then exit 1; fi

# Coverage validation (≥80%)
COVERAGE=$(coverage report | tail -1 | grep -o '[0-9]*%' | sed 's/%//')
if [ "$COVERAGE" -lt 80 ]; then exit 1; fi
```

#### Coverage Report Integration

- **HTML Reports**: Uploaded as artifacts (`coverage-reports-*.tar.gz`)
- **XML Reports**: Generated as `coverage.xml` for CI/CD tools
- **Codecov Integration**: Optional upload if token is configured
- **PR Comments**: Automatic coverage reporting on pull requests

#### Performance (Phase 4) Job

The CI workflow also includes a dedicated `performance` job that runs the performance-marked suite (excluded from default runs).

- **Command:** `pytest -o addopts='' -m performance tests/performance -v`
- **Artifacts:** uploads `perf_reports/` (including `latest.json` and `before_after.md`)
- **Job summary:** publishes the before/after table so regressions are visible without downloading artifacts
- **Triggering:** can be configured to run on a schedule, workflow dispatch, or via a PR label (see `.github/workflows/tests.yml`)

#### Manual Coverage Commands

For local development and CI verification:

```bash
# Full coverage report
pytest --cov=mgx_agent --cov-report=html:htmlcov --cov-report=xml:coverage.xml

# Check test and coverage requirements
pytest --collect-only -q
coverage report --show-missing
coverage xml -o coverage.xml

# View HTML reports
open htmlcov/index.html  # or your browser
```

The workflow ensures all quality gates are met before merging to maintain code quality standards.

---

## Troubleshooting

### Common Issues

#### 1. Event Loop Errors

**Problem**: `RuntimeError: no running event loop`

**Solution**: Use `@pytest.mark.asyncio` decorator:
```python
@pytest.mark.asyncio
async def test_async_function():
    pass
```

#### 2. Import Errors for MetaGPT

**Problem**: `ModuleNotFoundError: No module named 'metagpt'`

**Solution**: Stubs are registered in `conftest.py`. Ensure:
- `conftest.py` exists in `tests/` directory
- Tests are run via pytest (not directly)

#### 3. Fixture Not Found

**Problem**: `fixture 'fake_team' not found`

**Solution**: Ensure `conftest.py` is in the same directory:
```
tests/
├── conftest.py          # Must be here
├── unit/
│   └── test_*.py        # Uses fixtures
```

#### 4. Tests Not Discovered

**Problem**: `no tests collected`

**Solution**:
```bash
# Check pytest can find tests
pytest --collect-only

# Verify file/function names:
# - Files: test_*.py or *_test.py
# - Classes: Test*
# - Functions: test_*
```

#### 5. Async Test Timeout

**Problem**: `test timed out after 300 seconds`

**Solution**:
```python
@pytest.mark.timeout(10)  # 10 second timeout
async def test_slow_async():
    pass
```

Or adjust in `pytest.ini`:
```ini
timeout = 600  # Change to 600 seconds
```

---

## Best Practices

### ✅ Do

- ✅ Use fixtures to reduce boilerplate
- ✅ Write descriptive test names
- ✅ Test one thing per test function
- ✅ Use parametrize for similar tests
- ✅ Mock external dependencies
- ✅ Keep tests fast (< 1 second each)
- ✅ Test edge cases and errors

### ❌ Don't

- ❌ Depend on test execution order
- ❌ Make network calls in tests
- ❌ Use real file I/O (use tmp_path)
- ❌ Print to stdout (use logging)
- ❌ Have side effects between tests
- ❌ Use sleep() in tests
- ❌ Ignore test failures

---

## Next Steps

### Phase 3 Roadmap

1. **✅ Pytest Infrastructure** (Week 1)
   - Setup pytest, fixtures, stubs
   - Create test directory structure
   - Write smoke tests

2. **Unit Tests** (Week 2-3)
   - Test each module in isolation
   - Achieve 80% coverage
   - 80+ unit tests

3. **Integration Tests** (Week 4)
   - Test component interactions
   - Workflow integration tests
   - 30+ integration tests

4. **E2E Tests** (Week 5)
   - Complete pipeline tests
   - User scenario tests
   - 10+ e2e tests

### Coverage Target

```
Current:  2%  (Baseline)
Phase 3:  80% (Target)  ← You are here

Unit:     80%
Integration: 70%
E2E:      60%
```

---

## Documentation

- [Pytest Official Docs](https://docs.pytest.org/)
- [Pytest Asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Docs](https://coverage.readthedocs.io/)
- [Mock/Stub Patterns](https://en.wikipedia.org/wiki/Mock_object)

---

**Last Updated**: December 2024  
**Status**: 🟢 Testing Infrastructure Complete
