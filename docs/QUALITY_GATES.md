# Quality Gate System Documentation

## Overview

The Quality Gate System provides automated code quality checks and enforcement to ensure generated code meets production standards before deployment. It integrates with the existing sandboxed code runner from Phase 11 and provides comprehensive quality metrics.

## Architecture

### Components

1. **Quality Gate Manager** (`backend/services/quality_gates/gate_manager.py`)
   - Orchestrates gate evaluations
   - Handles parallel/sequential execution
   - Manages configuration and results

2. **Gate Implementations** (`backend/services/quality_gates/gates/`)
   - Individual gate types for different quality aspects
   - Pluggable architecture for easy extension

3. **Database Models** (`backend/db/models/entities.py`)
   - QualityGate configuration
   - GateExecution results tracking
   - Historical data storage

4. **API Layer** (`backend/routers/quality_gates.py`)
   - REST endpoints for gate evaluation
   - History and statistics retrieval
   - Health checks

## Gate Types

### 1. Lint Gate
**Purpose**: Code linting using industry-standard tools

**Tools Supported**:
- **JavaScript/TypeScript**: ESLint
- **Python**: Ruff (replaces flake8/pylint)
- **PHP**: Pint

**Configuration**:
```yaml
lint:
  enabled: true
  blocking: true
  fail_on_error: true
  fail_on_warning: false
  max_warnings: 10
  tools:
    javascript:
      command: "npx eslint --format json"
      max_errors: 0
      max_warnings: 10
    python:
      command: "ruff check --format json"
      max_errors: 0
      max_warnings: 5
    php:
      command: "pint --format=json"
      max_errors: 0
      max_warnings: 5
```

**Results**:
- Total errors and warnings count
- Per-language breakdown
- Specific rule violations
- File-level statistics

### 2. Coverage Gate
**Purpose**: Test coverage enforcement

**Tools Supported**:
- **Python**: pytest-cov
- **JavaScript**: Jest coverage
- **PHP**: PHPUnit coverage

**Configuration**:
```yaml
coverage:
  enabled: true
  blocking: true
  min_percentage: 80
  exclude_patterns:
    - "**/generated/**"
    - "**/tests/**"
  tools:
    python:
      command: "pytest --cov --cov-report=json --cov-report=term"
    javascript:
      command: "npm test -- --coverage --coverageReporters=json --coverageReporters=text"
```

**Results**:
- Overall coverage percentage
- Lines covered vs total
- Per-file coverage breakdown
- Coverage gap analysis

### 3. Security Gate
**Purpose**: Security audit and vulnerability scanning

**Tools Supported**:
- **Dependency Scanning**: npm audit, pip audit, composer audit
- **Code Scanning**: Semgrep, SonarQube patterns
- **Secrets Detection**: Hardcoded credentials scanning
- **License Compliance**: Package license validation

**Configuration**:
```yaml
security:
  enabled: true
  blocking: true
  allow_dev_dependencies: false
  critical_only: false
  tools:
    dependency_audit:
      npm_audit: true
      pip_audit: true
      composer_audit: true
      critical_vulnerabilities: 0
      high_vulnerabilities: 0
      medium_vulnerabilities: 5
    code_scan:
      semgrep:
        enabled: true
        rules: ["owasp-top-ten", "security-audit"]
      hardcoded_secrets: true
    license_check:
      allowed_licenses: ["MIT", "Apache-2.0", "BSD-2-Clause"]
      blocked_licenses: ["GPL-3.0", "AGPL-3.0"]
```

**Results**:
- Vulnerability count by severity (critical/high/medium/low)
- Package-specific security issues
- License compliance violations
- Security recommendations

### 4. Performance Gate
**Purpose**: Performance smoke testing and benchmarking

**Tests**:
- **Response Time**: HTTP endpoint latency testing
- **Throughput**: Requests per second measurement
- **Memory Usage**: Peak memory consumption
- **CPU Usage**: CPU utilization patterns
- **Stress Testing**: Concurrency and load testing

**Configuration**:
```yaml
performance:
  enabled: true
  blocking: true
  max_response_time_ms: 500
  min_throughput_rps: 100
  max_memory_mb: 512
  max_cpu_percent: 80
  tests:
    response_time:
      threshold_ms: 500
      concurrent_requests: 10
      duration_seconds: 30
    throughput:
      min_rps: 100
      duration_seconds: 60
```

**Results**:
- Average and P95 response times
- Measured RPS vs threshold
- Memory and CPU utilization
- Performance recommendations

### 5. Contract Gate
**Purpose**: API endpoint contract testing

**Features**:
- OpenAPI specification validation
- Schema compliance checking
- Response time validation
- Status code verification

**Configuration**:
```yaml
contract:
  enabled: true
  blocking: true
  endpoints:
    - path: "/health"
      method: "GET"
      expected_status: 200
      timeout_ms: 5000
    - path: "/api/v1/status"
      method: "GET"
      expected_status: 200
      response_schema:
        type: "object"
        required: ["status"]
```

**Results**:
- Endpoint availability and response
- Schema validation results
- Performance metrics per endpoint
- Contract compliance score

### 6. Complexity Gate
**Purpose**: Code complexity analysis and limits

**Tools Supported**:
- **Python**: Radon (cyclomatic and cognitive complexity)
- **JavaScript**: ESLint complexity rule
- **PHP**: PHPMD complexity rules

**Configuration**:
```yaml
complexity:
  enabled: true
  blocking: true
  max_cyclomatic: 10
  max_cognitive: 15
  max_lines_per_function: 50
  max_nesting_level: 4
  tools:
    radon:
      enabled: true
      command: "radon cc --show-complexity --average"
```

**Results**:
- Function-level complexity scores
- Files exceeding complexity thresholds
- Complexity distribution analysis
- Refactoring recommendations

### 7. Type Check Gate
**Purpose**: Static type checking

**Tools Supported**:
- **TypeScript**: TypeScript compiler
- **Python**: MyPy

**Configuration**:
```yaml
type_check:
  enabled: true
  blocking: true
  strict_mode: false
  tools:
    typescript:
      enabled: true
      command: "npx tsc --noEmit --pretty"
    mypy:
      enabled: true
      command: "mypy --show-error-codes --show-column-numbers"
```

**Results**:
- Type error count and breakdown
- Warning level analysis
- File coverage for type checking
- Type safety recommendations

## Usage

### API Usage

```python
from backend.services.quality_gates import get_gate_manager

# Get gate manager instance
gate_manager = await get_gate_manager()

# Evaluate quality gates
result = await gate_manager.evaluate_gates(
    workspace_id="workspace_123",
    project_id="project_456", 
    gate_types=["lint", "coverage", "security"],
    working_directory="/path/to/code",
    application_url="http://localhost:8080"
)

if result["passed"]:
    print("✅ All quality gates passed!")
else:
    print(f"❌ Failed gates: {result['blocking_failures']}")
    for recommendation in result["recommendations"]:
        print(f"💡 {recommendation}")
```

### Integration with Code Generation

The system automatically runs quality gates after code generation and sandbox testing:

```python
# In WriteCode action
if await self._run_sandbox_execution(code, command, language):
    # Quality gates run automatically after successful sandbox execution
    quality_passed = await self._run_quality_gates_after_sandbox(
        files=generated_files,
        workspace_id=workspace_id,
        project_id=project_id
    )
    
    if not quality_passed:
        # Trigger revision loop with quality feedback
        return "Code quality issues detected. Please revise..."
```

### Configuration Management

1. **Default Configuration**: `configs/quality_gates.yml`
2. **Environment Overrides**: `development`, `staging`, `production`
3. **Per-Project Settings**: Stored in database
4. **Runtime Adjustments**: Via API endpoints

### Database Schema

#### QualityGate Table
- Configuration and metadata for each gate type
- Statistics tracking (pass/fail rates)
- Threshold settings

#### GateExecution Table
- Individual gate execution records
- Detailed results and metrics
- Historical data for trending

## Performance Characteristics

- **Parallel Execution**: Up to 4 gates simultaneously
- **Typical Evaluation Time**: 30-60 seconds for full gate set
- **Memory Usage**: 100-300MB per gate evaluation
- **Storage**: ~1KB per gate execution record

## Monitoring and Analytics

### Available Metrics
- Gate pass/fail rates by type
- Average evaluation times
- Issue trends over time
- Language-specific quality metrics
- Project-level quality scores

### Dashboard Integration
- Real-time gate status
- Historical trend charts
- Issue breakdown by severity
- Performance metrics tracking

## Error Handling

### Graceful Degradation
- **Missing Tools**: Gate skips with warning instead of failure
- **Configuration Errors**: Validation prevents execution
- **Timeout Handling**: Fail-safe timeouts prevent hanging
- **Resource Limits**: Automatic cleanup and memory management

### Retry Logic
- **Automatic Retries**: Up to 2 attempts for transient failures
- **Exponential Backoff**: Progressive delay between retries
- **Circuit Breaker**: Prevents cascading failures

## Best Practices

### For Developers
1. **Pre-commit Hooks**: Run subset of gates before committing
2. **IDE Integration**: Show real-time quality feedback
3. **Incremental Improvements**: Address issues incrementally
4. **Documentation**: Document exceptions and thresholds

### For Teams
1. **Quality Baseline**: Establish project-specific thresholds
2. **Gradual Rollout**: Start with warning mode, progress to blocking
3. **Regular Reviews**: Analyze quality trends and adjust thresholds
4. **Training**: Educate team on quality gate feedback

## Troubleshooting

### Common Issues

1. **Tool Installation**
   ```bash
   # Ensure tools are available in PATH
   npm install -g eslint
   pip install ruff mypy radon
   composer global require phpmd/phpmd
   ```

2. **Configuration Validation**
   ```python
   # Check configuration errors
   from backend.services.quality_gates import get_gate_manager
   gate_manager = await get_gate_manager()
   errors = gate_manager.validate_configuration()
   ```

3. **Performance Issues**
   - Check parallel execution settings
   - Monitor resource usage
   - Review timeout configurations

### Debug Mode
```python
import logging
logging.getLogger('backend.services.quality_gates').setLevel(logging.DEBUG)
```

## Extension Guide

### Adding New Gate Types

1. **Inherit BaseQualityGate**
2. **Implement evaluate() method**
3. **Register with @register_gate decorator**
4. **Add configuration validation**
5. **Update documentation**

### Example Custom Gate

```python
from .base_gate import BaseQualityGate, GateResult, GateConfiguration, register_gate
from ...db.models.enums import QualityGateType, QualityGateStatus

@register_gate(QualityGateType.CUSTOM)
class CustomGate(BaseQualityGate):
    async def evaluate(self, **kwargs) -> GateResult:
        # Implementation here
        pass
```

## Integration Points

- **WriteCode Action**: Automatic quality gate execution
- **Sandbox Runner**: Leverages existing execution infrastructure
- **Event System**: Real-time quality status updates
- **Database**: Persistent quality metrics and history
- **API Gateway**: REST endpoints for external integration

## Future Enhancements

- **AI-Powered Quality Analysis**: Machine learning-based code quality assessment
- **Custom Rules Engine**: User-defined quality rules and thresholds
- **Integration with External Tools**: SonarQube, CodeClimate, etc.
- **Real-time Quality Monitoring**: Live code quality dashboards
- **Advanced Analytics**: Predictive quality modeling