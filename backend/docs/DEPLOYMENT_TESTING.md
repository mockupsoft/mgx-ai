# Deployment Testing Guide

Comprehensive guide for testing deployment validation, security checks, performance benchmarks, and disaster recovery procedures.

## Table of Contents

1. [Overview](#overview)
2. [Pre-Deployment Validators](#pre-deployment-validators)
3. [Security Validations](#security-validations)
4. [Pre-Deployment Checklist](#pre-deployment-checklist)
5. [Deployment Simulation](#deployment-simulation)
6. [Health Check System](#health-check-system)
7. [Backup & Recovery](#backup--recovery)
8. [Rollback Procedures](#rollback-procedures)
9. [Performance Testing](#performance-testing)
10. [Integration Scenarios](#integration-scenarios)
11. [Running Tests](#running-tests)
12. [CI/CD Integration](#cicd-integration)

## Overview

This testing suite provides comprehensive coverage for:
- ✅ Docker image validation
- ✅ Kubernetes manifest validation
- ✅ Security scanning and hardcoded secret detection
- ✅ Pre-deployment checklists with human sign-off
- ✅ Deployment simulation (dry-run)
- ✅ Health check validation
- ✅ Database backup and restore procedures
- ✅ Rollback capability verification
- ✅ Performance benchmarking and load testing

## Pre-Deployment Validators

### Docker Image Validation

**Location**: `backend/tests/test_validators.py`

**Checks**:
- ✅ Image exists and is accessible
- ✅ Image size analysis (<500MB warning, <1GB hard limit)
- ✅ Base image security (no 'latest' tags)
- ✅ Hardcoded secrets detection
- ✅ Entry point configured
- ✅ Health check endpoint defined
- ✅ Non-root user configured
- ✅ Image layers documented

**Usage**:
```python
from backend.services.validators import DockerValidator

validator = DockerValidator(workspace_id="ws-123")
result = await validator.validate_image(
    validation_id="val-123",
    image_id="myapp:1.0.0",
    image_metadata={
        "size_bytes": 256000000,
        "base_image": "python:3.11-slim",
        "entry_point": ["python", "app.py"],
        "user": "app",
    }
)

if result.is_passing():
    print("✓ Docker image validation passed")
else:
    print(f"✗ Validation failed: {result.failed_checks} checks failed")
```

**Test Coverage**:
```bash
pytest backend/tests/test_validators.py::test_docker_validate_image_success
pytest backend/tests/test_validators.py::test_docker_validate_hardcoded_secrets
pytest backend/tests/test_validators.py::test_docker_validate_large_image_warning
```

### Kubernetes Manifests Validation

**Checks**:
- ✅ YAML syntax valid
- ✅ Resource requests/limits set
- ✅ Liveness probe configured
- ✅ Readiness probe configured
- ✅ Security context applied
- ✅ Image pull policy set
- ✅ Service/Ingress configuration

**Usage**:
```python
from backend.services.validators import KubernetesValidator

validator = KubernetesValidator(workspace_id="ws-123")
result = await validator.validate_manifests(
    validation_id="val-123",
    manifests=[
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: myapp
        spec:
          replicas: 3
          template:
            spec:
              containers:
              - name: app
                image: myapp:1.0.0
                resources:
                  requests:
                    cpu: 500m
                    memory: 256Mi
                livenessProbe:
                  httpGet:
                    path: /health
                    port: 8000
        """
    ]
)
```

**Test Coverage**:
```bash
pytest backend/tests/test_validators.py::test_k8s_validate_valid_manifests
pytest backend/tests/test_validators.py::test_k8s_validate_missing_resources
```

## Security Validations

### Static Analysis

**Location**: `backend/tests/test_validators.py`

**Checks**:
- ✅ Hardcoded secrets detection (API keys, tokens, passwords)
- ✅ Default credentials detection (admin/admin, test/test)
- ✅ Dependency vulnerability audit
- ✅ License compliance checking
- ✅ Security headers validation
- ✅ TLS/HTTPS enforcement
- ✅ CORS configuration validation
- ✅ OWASP Top 10 compliance

**Usage**:
```python
from backend.services.validators import SecurityValidator

validator = SecurityValidator(workspace_id="ws-123")
result = await validator.validate_security(
    validation_id="val-123",
    artifacts={
        "application_code": "# Clean code",
        "configuration": {},
        "security_headers": {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
        "cors_config": {
            "allowed_origins": ["https://app.example.com"]
        }
    }
)
```

**Secret Detection Patterns**:
- API keys: `api[_-]?key.*[=:]\s*['"]?[a-zA-Z0-9]{20,}['"]?`
- AWS keys: `AKIA[0-9A-Z]{16}`
- Tokens: `token.*[=:]\s*['"]?[a-zA-Z0-9]{20,}['"]?`
- Passwords: `password.*[=:]\s*['"]?.+['"]?`

**Test Coverage**:
```bash
pytest backend/tests/test_validators.py::test_security_validate_hardcoded_secrets
pytest backend/tests/test_validators.py::test_security_validate_cors_all_origins
```

### Runtime Security

**Checks**:
- ✅ Environment variable validation
- ✅ Service endpoint reachability
- ✅ Database connection validation
- ✅ Redis/cache configuration
- ✅ Storage configuration (MinIO, S3)
- ✅ Log level appropriateness
- ✅ Timeout value validation

## Pre-Deployment Checklist

**Location**: `backend/tests/test_deployment.py`

### Default 12-Item Checklist

1. ✅ Code review completed
2. ✅ All tests passing
3. ✅ Coverage ≥80%
4. ✅ Database migrations tested
5. ✅ No breaking API changes
6. ✅ Documentation updated
7. ✅ Security scan passed
8. ✅ Performance acceptable
9. ✅ Backup procedures verified
10. ✅ Rollback plan ready
11. ✅ Monitoring configured
12. ✅ On-call documentation updated

**Usage**:
```python
from backend.services.validators import PreDeploymentChecklist

checklist = PreDeploymentChecklist(workspace_id="ws-123")
checklist.build_default_checklist()

# Update checklist items
for item in checklist.items:
    # Perform checks...
    checklist.set_item_status(item.id, "pass")

# Add human sign-off for critical items
checklist.add_signoff(
    "critical_item",
    user="admin@example.com",
    timestamp=datetime.utcnow()
)

# Verify checklist
if checklist.all_passed() and checklist.can_deploy():
    print("✓ Deployment approved")
else:
    print("✗ Deployment blocked - checklist incomplete")
```

**Test Coverage**:
```bash
pytest backend/tests/test_deployment.py::test_checklist_default_items_creation
pytest backend/tests/test_deployment.py::test_checklist_human_signoff_required
pytest backend/tests/test_deployment.py::test_checklist_prevent_deployment_critical_unchecked
```

## Deployment Simulation

**Location**: `backend/tests/test_deployment.py`

### Dry-Run Testing

**Process**:
1. Create test namespace
2. Deploy manifests to test namespace
3. Verify pods reach ready state
4. Execute health checks
5. Collect metrics
6. Clean up test environment

**Usage**:
```python
from backend.services.validators import DeploymentSimulator

simulator = DeploymentSimulator(workspace_id="ws-123")
result = await simulator.simulate_deployment(
    validation_id="val-123",
    artifacts={
        "kubernetes_manifests": [
            {"kind": "Deployment", "metadata": {"name": "myapp"}}
        ],
    },
    target_environment="staging",
    dry_run=True
)

print(f"Simulation status: {result['status']}")
print(f"Test namespace: {result['test_namespace']}")
print(f"Duration: {result['duration_seconds']}s")
```

**Test Coverage**:
```bash
pytest backend/tests/test_deployment.py::test_simulator_test_namespace_creation
pytest backend/tests/test_deployment.py::test_simulator_pods_reach_ready_state
pytest backend/tests/test_deployment.py::test_simulator_dry_run_no_production_impact
```

## Health Check System

**Location**: `backend/tests/test_validators.py`

### Health Endpoints

- `/health` - Overall system health
- `/health/ready` - Readiness probe
- `/health/live` - Liveness probe

**Response Format**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-12-19T10:00:00Z",
  "dependencies": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5
    },
    "cache": {
      "status": "healthy",
      "response_time_ms": 2
    },
    "storage": {
      "status": "healthy",
      "response_time_ms": 10
    }
  }
}
```

**Test Coverage**:
```bash
pytest backend/tests/test_validators.py::test_health_validate_success
pytest backend/tests/test_validators.py::test_health_validate_missing_env_vars
```

## Backup & Recovery

**Location**: `backend/tests/test_backup_recovery.py`

### PostgreSQL Backup

**Process**:
1. Execute `pg_dump`
2. Compress backup (optional)
3. Encrypt backup (optional)
4. Verify backup location
5. Calculate checksum

**Usage**:
```python
from backend.services.backup import BackupService

backup_service = BackupService(workspace_id="ws-123")

# Create backup
result = await backup_service.backup_postgresql(
    backup_id="backup-123",
    database_url="postgresql://localhost:5432/mydb",
    output_path="/backups/backup_20241219.sql.gz",
    compress=True,
    encrypt=True,
)

print(f"Backup created: {result['file_path']}")
print(f"Size: {result['size_bytes']} bytes")
```

**Test Coverage**:
```bash
pytest backend/tests/test_backup_recovery.py::test_postgresql_dump_creates_file
pytest backend/tests/test_backup_recovery.py::test_postgresql_backup_compression
pytest backend/tests/test_backup_recovery.py::test_postgresql_backup_encryption
```

### PostgreSQL Restore

**Process**:
1. Verify backup exists
2. Stop application (if needed)
3. Restore database
4. Verify data integrity
5. Check foreign key constraints
6. Restart application

**Usage**:
```python
# Restore from backup
result = await backup_service.restore_postgresql(
    backup_id="restore-123",
    database_url="postgresql://localhost:5432/mydb",
    backup_path="/backups/backup_20241219.sql.gz",
)

print(f"Restored {result['records_restored']} records")
```

**Test Coverage**:
```bash
pytest backend/tests/test_backup_recovery.py::test_postgresql_restore_succeeds
pytest backend/tests/test_backup_recovery.py::test_postgresql_data_matches_pre_backup
pytest backend/tests/test_backup_recovery.py::test_postgresql_restore_time_acceptable
```

### MinIO Backup

**Process**:
1. List all objects
2. Download objects
3. Create tarball
4. Compress and encrypt
5. Verify checksums

**Test Coverage**:
```bash
pytest backend/tests/test_backup_recovery.py::test_minio_backup_lists_all_objects
pytest backend/tests/test_backup_recovery.py::test_minio_restore_succeeds
pytest backend/tests/test_backup_recovery.py::test_minio_object_checksums_match
```

## Rollback Procedures

**Location**: `backend/tests/test_deployment.py`

### Rollback Validation

**Checks**:
- ✅ Previous version available
- ✅ Database rollback procedure exists
- ✅ Rollback doesn't require code changes
- ✅ SLA window ≤1 hour
- ✅ Estimated rollback time calculated
- ✅ Post-rollback health check passes
- ✅ Data consistency verified

**Usage**:
```python
from backend.services.validators import RollbackValidator

validator = RollbackValidator(workspace_id="ws-123")
result = await validator.validate_rollback_plan(
    validation_id="val-123",
    from_version="1.0.0",
    to_version="0.9.0",
    artifacts={
        "docker_images": {
            "0.9.0": "myapp:0.9.0",
        },
        "database_rollback_plan": {
            "backup_available": True,
            "rollback_script": "rollback_v1.sql",
        },
        "estimated_rollback_time_minutes": 45,
        "sla_window_minutes": 60,
    }
)

if result.validation_passed:
    print(f"✓ Rollback validated (ETA: {result.estimated_rollback_time}min)")
```

**Test Coverage**:
```bash
pytest backend/tests/test_deployment.py::test_rollback_previous_version_available
pytest backend/tests/test_deployment.py::test_rollback_sla_window_respected
pytest backend/tests/test_deployment.py::test_rollback_data_consistency_verified
```

## Performance Testing

**Location**: `backend/tests/test_performance.py`

### Load Testing

**Thresholds**:
- P95 response time: <500ms
- P99 response time: <1000ms
- Memory stable during test
- CPU <80% utilization
- Error rate <0.1%

**Usage**:
```python
from backend.tests.test_performance import PerformanceMonitor, MockAPIClient

monitor = PerformanceMonitor()
client = MockAPIClient()

# Run 100 concurrent requests
async def make_request():
    start = time.time()
    await client.get("/api/workspaces")
    duration = (time.time() - start) * 1000
    monitor.record_response(duration)

tasks = [make_request() for _ in range(100)]
await asyncio.gather(*tasks)

# Check metrics
p95 = monitor.get_percentile(95)
p99 = monitor.get_percentile(99)
error_rate = monitor.get_error_rate()

print(f"P95: {p95}ms, P99: {p99}ms, Error rate: {error_rate}%")
```

**Test Coverage**:
```bash
pytest backend/tests/test_performance.py::test_api_100_concurrent_requests
pytest backend/tests/test_performance.py::test_p95_response_time_under_500ms
pytest backend/tests/test_performance.py::test_p99_response_time_under_1000ms
pytest backend/tests/test_performance.py::test_error_rate_under_0_1_percent
```

### Search Performance

**Thresholds**:
- Single search: <200ms
- Complex search: <500ms
- 1000-item KB search: <300ms

**Test Coverage**:
```bash
pytest backend/tests/test_performance.py::test_single_search_under_200ms
pytest backend/tests/test_performance.py::test_complex_search_under_500ms
pytest backend/tests/test_performance.py::test_1000_item_kb_search_under_300ms
```

### Memory Profiling

**Test Coverage**:
```bash
pytest backend/tests/test_performance.py::test_no_memory_leaks_sustained_load
pytest backend/tests/test_performance.py::test_memory_usage_per_request
```

## Integration Scenarios

**Location**: `backend/tests/test_deployment.py`

### Complete Deployment Flow

1. Run pre-deployment checklist ✅
2. Run security validators ✅
3. Run pre-deployment simulation ✅
4. Verify health checks pass ✅
5. Test backup procedure ✅
6. Test restore procedure ✅
7. Validate rollback capability ✅
8. Run load tests ✅
9. Approve deployment ✅
10. Deploy to production ✅
11. Monitor health metrics ✅
12. Verify no errors/alerts ✅

**Test Coverage**:
```bash
pytest backend/tests/test_deployment.py::test_full_deployment_checklist_flow
pytest backend/tests/test_deployment.py::test_deployment_with_security_checks
pytest backend/tests/test_deployment.py::test_production_deployment_succeeds
```

## Running Tests

### All Tests

```bash
# Run all deployment tests
pytest backend/tests/test_validators.py -v
pytest backend/tests/test_deployment.py -v
pytest backend/tests/test_backup_recovery.py -v
pytest backend/tests/test_performance.py -v
```

### Specific Test Categories

```bash
# Validators only
pytest backend/tests/test_validators.py -v

# Deployment flow
pytest backend/tests/test_deployment.py -v

# Backup/recovery
pytest backend/tests/test_backup_recovery.py -v

# Performance
pytest backend/tests/test_performance.py -v
```

### With Coverage

```bash
pytest backend/tests/test_deployment.py \
  backend/tests/test_backup_recovery.py \
  backend/tests/test_performance.py \
  --cov=backend/services/validators \
  --cov-report=html \
  --cov-report=term-missing
```

### Load Tests

```bash
# Locust
cd load_tests
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless

# K6
cd load_tests
k6 run k6_script.js
```

See [load_tests/README.md](../load_tests/README.md) for detailed load testing instructions.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deployment Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  deployment-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run Deployment Validators
        run: pytest backend/tests/test_validators.py -v
      
      - name: Run Deployment Flow Tests
        run: pytest backend/tests/test_deployment.py -v
      
      - name: Run Backup/Recovery Tests
        run: pytest backend/tests/test_backup_recovery.py -v
      
      - name: Run Performance Tests
        run: pytest backend/tests/test_performance.py -v
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: deployment-tests

  load-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install K6
        run: |
          sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6
      
      - name: Run Load Tests
        run: k6 run load_tests/k6_script.js
```

## Best Practices

### Before Deployment

1. ✅ Run complete test suite
2. ✅ Verify all checklist items
3. ✅ Run deployment simulation
4. ✅ Create fresh backup
5. ✅ Verify rollback plan
6. ✅ Check monitoring dashboards

### During Deployment

1. Monitor health endpoints
2. Watch error rates
3. Track response times
4. Monitor resource usage
5. Keep communication channels open
6. Have rollback plan ready

### After Deployment

1. Verify all health checks pass
2. Run smoke tests
3. Check logs for errors
4. Monitor metrics for anomalies
5. Validate data integrity
6. Document any issues

## Troubleshooting

### Failed Deployment Simulation

**Problem**: Simulation fails to deploy

**Solutions**:
- Check Kubernetes cluster connectivity
- Verify namespace permissions
- Review manifest syntax
- Check resource quotas

### Backup Failures

**Problem**: Backup creation fails

**Solutions**:
- Verify disk space
- Check database connectivity
- Verify backup directory permissions
- Review backup logs

### Performance Degradation

**Problem**: Response times exceed thresholds

**Solutions**:
- Check database query performance
- Verify caching is working
- Review application logs
- Check resource allocation
- Profile slow endpoints

### Rollback Issues

**Problem**: Rollback validation fails

**Solutions**:
- Verify previous version availability
- Check database backup exists
- Review rollback script
- Test in staging first

## Metrics & Reporting

### Key Metrics

- **Deployment Success Rate**: Target >99%
- **Rollback Frequency**: Target <1% of deployments
- **Mean Time to Deploy (MTTD)**: Target <30 minutes
- **Mean Time to Rollback (MTTR)**: Target <15 minutes
- **Security Vulnerabilities**: Target 0 critical/high

### Reports

1. **Deployment Report**: Summary of all validation checks
2. **Performance Report**: Load test results and trends
3. **Security Report**: Vulnerability scan results
4. **Backup Report**: Backup status and recovery time

## Support

For questions or issues with deployment testing:

- 📧 Email: devops@example.com
- 💬 Slack: #deployment-support
- 📚 Wiki: https://wiki.example.com/deployment-testing

## References

- [DEPLOYMENT_VALIDATOR.md](./DEPLOYMENT_VALIDATOR.md) - Validator service documentation
- [Load Testing README](../load_tests/README.md) - Load testing guide
- [TESTING.md](./TESTING.md) - General testing guide
- [QUALITY_GATES.md](./QUALITY_GATES.md) - Quality gates documentation
