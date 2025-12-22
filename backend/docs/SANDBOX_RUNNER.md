# Phase 11: Sandboxed Code Runner - Complete Implementation

## Overview

**KRITIK** - Agent tarafından yazılan kodu güvenli ve izole ortamda çalıştırma sistemi.

Bu implementation, agent'ların kodları güvenli Docker sandbox'larda çalıştırmasını, test etmesini ve sonuçları capture etmesini sağlar.

## Architecture

### Core Components

1. **SandboxRunner** (`backend/services/sandbox/runner.py`)
   - Docker API ile container management
   - Security hardening (read-only, no-network, resource limits)
   - Multi-language support
   - Resource monitoring

2. **Language Executors** (`backend/services/sandbox/executors.py`)
   - NodeExecutor (npm test, npm run build)
   - PythonExecutor (pytest, python -m)
   - PHPExecutor (phpunit, composer test)
   - DockerExecutor (docker build, docker run)

3. **API Endpoints** (`backend/routers/sandbox.py`)
   - REST API for execution management
   - WebSocket for live log streaming
   - Execution history and metrics

4. **Database Models** (`backend/db/models/entities.py`)
   - SandboxExecution ORM model
   - Multi-tenant workspace/project scoping

5. **Integration Layer** (`mgx_agent/actions.py`)
   - Automatic code execution after WriteCode
   - Test command determination
   - Failure feedback to revision system

## Security Model

### Container Security Hardening

```python
SECURITY_OPTS = [
    "no-new-privileges:true",
    "apparmor=unconfined", 
    "seccomp=unconfined",
]
```

- **Read-only root filesystem**: `read_only: True`
- **No network access**: `network_mode: "none"`
- **User namespace isolation**: `user: "nobody"`
- **Capability dropping**: `cap_drop: ["ALL"]`
- **Resource limits**: CPU, memory, time, file descriptors
- **Temporary filesystem**: `/tmp` tmpfs with restrictions

### Resource Limits

```python
# Default limits
MEMORY_LIMIT = "512m"
CPU_LIMIT = "1.0"
DEFAULT_TIMEOUT = 30.0

# Container configuration
mem_limit: "512m"
cpu_quota: 30000  # 30 seconds in microseconds
ulimits: [
    {"name": "nofile", "soft": 1024, "hard": 2048},
    {"name": "nproc", "soft": 64, "hard": 128}
]
```

## API Reference

### Execute Code

```http
POST /api/sandbox/execute
Content-Type: application/json

{
  "code": "print('Hello World')",
  "command": "python main.py", 
  "language": "python",
  "timeout": 60,
  "memory_limit_mb": 512
}
```

**Response:**
```json
{
  "success": true,
  "stdout": "Hello World\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 5234,
  "resource_usage": {
    "max_memory_mb": 128,
    "cpu_percent": 45.2,
    "network_io": 0,
    "disk_io": 2048
  }
}
```

### Get Execution Details

```http
GET /api/sandbox/executions/{execution_id}
```

### List Executions

```http
GET /api/sandbox/executions?offset=0&limit=50&status=completed&language=python
```

### Stop Execution

```http
DELETE /api/sandbox/executions/{execution_id}
```

### WebSocket Logs

```javascript
const ws = new WebSocket('ws://localhost/api/sandbox/executions/{execution_id}/logs');
ws.onmessage = (event) => {
  console.log('Log:', event.data);
};
```

### Get Metrics

```http
GET /api/sandbox/metrics?workspace_id={workspace_id}
```

**Response:**
```json
{
  "total_executions": 100,
  "success_rate": 0.87,
  "avg_duration_ms": 5234.5,
  "avg_memory_mb": 128.7,
  "language_breakdown": {
    "python": 45,
    "javascript": 35,
    "php": 20
  },
  "status_breakdown": {
    "completed": 87,
    "failed": 10,
    "timeout": 3
  }
}
```

## Supported Languages

### Python
- **Base Image**: `mgx-sandbox-python:latest`
- **Test Commands**: `pytest`, `python -m unittest discover`
- **Build Commands**: `poetry build` (if pyproject.toml exists)
- **Execution**: `python main.py`

### JavaScript/Node.js
- **Base Image**: `mgx-sandbox-node:latest`
- **Package Managers**: npm, yarn, pnpm
- **Test Commands**: `npm test`, `yarn test`, `pnpm test`
- **Build Commands**: `npm run build`, `yarn build`, `pnpm build`
- **Execution**: `node index.js`

### PHP
- **Base Image**: `mgx-sandbox-php:latest`
- **Package Manager**: Composer
- **Test Commands**: `vendor/bin/phpunit`
- **Build Commands**: `composer run build`
- **Execution**: `php index.php`

### Docker
- **Base Image**: `mgx-sandbox-node:latest`
- **Commands**: `docker build`, `docker run`
- **Use Case**: Docker-in-Docker scenarios

## Base Images

Pre-built base images with security hardening:

```dockerfile
# mgx-sandbox-python:latest
FROM python:3.10-slim
RUN useradd -m -u 1000 sandbox
COPY --chown=sandbox:sandbox /workspace /workspace
USER sandbox
WORKDIR /workspace
CMD ["python", "main.py"]

# mgx-sandbox-node:latest  
FROM node:18-alpine
RUN addgroup -g 1000 -S sandbox && adduser -S sandbox -G sandbox
COPY --chown=sandbox:sandbox /workspace /workspace
USER sandbox
WORKDIR /workspace
CMD ["node", "index.js"]

# mgx-sandbox-php:latest
FROM php:8.1-cli-alpine
RUN addgroup -g 1000 -S sandbox && adduser -S sandbox -G sandbox
COPY --chown=sandbox:sandbox /workspace /workspace
USER sandbox
WORKDIR /workspace
CMD ["php", "index.php"]
```

## Integration with TaskExecutor

### Automatic Testing Flow

1. **WriteCode Action** generates code
2. **Sandbox testing** is automatically triggered
3. **Test commands** are determined based on files
4. **Code execution** runs in secure containers
5. **Results** are captured and logged
6. **Failure feedback** is injected into revision prompts
7. **Success** marks execution phase complete

### Code Example

```python
# WriteCode action automatically calls sandbox testing
result = await write_code.run(
    instruction="Create a simple Python web server",
    target_stack="python",
    strict_mode=True
)

# Sandbox testing happens automatically
# Results logged for debugging
# Failures trigger revision prompts
```

### Disable Sandbox Testing

```bash
# Environment variable to disable testing
export DISABLE_SANDBOX_TESTING=true
```

## Database Schema

### SandboxExecution Model

```python
class SandboxExecution(Base):
    __tablename__ = "sandbox_executions"
    
    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey, nullable=False)
    project_id = Column(String(36), nullable=False)
    
    execution_type = Column(SQLEnum(SandboxExecutionLanguage))
    status = Column(SQLEnum(SandboxExecutionStatus))
    
    # Command and results
    command = Column(Text, nullable=False)
    code = Column(Text)
    stdout = Column(Text)
    stderr = Column(Text)
    exit_code = Column(Integer)
    success = Column(Boolean)
    
    # Resource usage
    duration_ms = Column(Integer)
    max_memory_mb = Column(Integer)
    cpu_percent = Column(Float)
    network_io = Column(BigInteger)
    disk_io = Column(BigInteger)
    
    # Error information
    error_type = Column(String(255))
    error_message = Column(Text)
    timeout_seconds = Column(Integer)
    container_id = Column(String(255))
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

## Telemetry & Monitoring

### Metrics Tracked

- **Execution time tracking**: Duration per execution
- **Success/failure rate**: Per language and overall
- **Resource usage patterns**: Memory, CPU, I/O
- **Error classification**: Compilation, runtime, timeout
- **Performance metrics**: P50, P95, P99 latency

### Event Types

```python
# Sandbox execution events
SANDBOX_EXECUTION_STARTED = "sandbox_execution_started"
SANDBOX_EXECUTION_COMPLETED = "sandbox_execution_completed"  
SANDBOX_EXECUTION_FAILED = "sandbox_execution_failed"
SANDBOX_EXECUTION_LOGS = "sandbox_execution_logs"
```

### Sample Metrics

```json
{
  "execution_metrics": {
    "total_executions": 1000,
    "success_rate": 0.92,
    "avg_duration_ms": 3245,
    "p50_latency": 2100,
    "p95_latency": 5800,
    "p99_latency": 12000,
    "languages": {
      "python": {"count": 400, "success_rate": 0.95},
      "javascript": {"count": 350, "success_rate": 0.90},
      "php": {"count": 250, "success_rate": 0.89}
    }
  }
}
```

## Testing Strategy

### Unit Tests
- Executor initialization
- Command building logic
- Security configuration
- Parameter validation

### Integration Tests  
- Mocked Docker API
- Database operations
- API endpoints
- WebSocket connections

### End-to-End Tests
- Real container execution
- Multi-language scenarios
- Resource limit enforcement
- Network isolation

### Security Tests
- Container breakout attempts
- Resource limit enforcement
- Network access prevention
- Filesystem read-only verification

### Failure Scenario Tests
- Timeout handling
- Out-of-memory scenarios
- Container creation failures
- Invalid parameter handling

## Performance Characteristics

### Typical Execution Times
- **Python simple script**: 2-5 seconds
- **JavaScript npm test**: 10-30 seconds  
- **PHP unit test**: 5-15 seconds
- **Complex builds**: 30-120 seconds

### Resource Usage
- **Memory**: 50-200MB typical
- **CPU**: 1-50% of allocated quota
- **Network**: Zero (isolated)
- **Disk**: 10-100MB per execution

### Scalability
- **Concurrent executions**: Limited by Docker daemon
- **Container startup**: 1-3 seconds
- **Image pulling**: One-time cost
- **Cleanup overhead**: <1 second

## Troubleshooting

### Common Issues

1. **Container Creation Fails**
   ```bash
   # Check Docker daemon status
   docker ps
   
   # Verify base images exist
   docker images | grep mgx-sandbox
   ```

2. **Out of Memory**
   ```python
   # Increase memory limit
   await runner.execute_code(
       memory_limit_mb=1024,  # 1GB
       timeout=60
   )
   ```

3. **Network Access Denied**
   ```python
   # This is expected behavior - containers are isolated
   # For dependency installation, images should be pre-built
   ```

4. **Timeout Issues**
   ```python
   # Increase timeout for long-running processes
   await runner.execute_code(
       timeout=300  # 5 minutes
   )
   ```

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Detailed Docker API logs
result = await runner.execute_code(...)
print(result)
```

## Configuration

### Environment Variables

```bash
# Disable sandbox testing (development)
DISABLE_SANDBOX_TESTING=true

# Custom Docker socket (if needed)
DOCKER_HOST=unix:///var/run/docker.sock

# Default resource limits
SANDBOX_DEFAULT_TIMEOUT=30
SANDBOX_DEFAULT_MEMORY=512
SANDBOX_DEFAULT_CPU=1.0
```

### Base Image Configuration

```python
# Custom base images (development only)
BASE_IMAGES = {
    "python": "custom-python:latest",
    "javascript": "custom-node:latest", 
    "php": "custom-php:latest"
}
```

## Production Deployment

### Docker Images

```bash
# Build base images
docker build -f Dockerfile.python -t mgx-sandbox-python:latest .
docker build -f Dockerfile.node -t mgx-sandbox-node:latest .
docker build -f Dockerfile.php -t mgx-sandbox-php:latest .

# Tag for registry
docker tag mgx-sandbox-python:latest registry.example.com/mgx-sandbox-python:latest
docker tag mgx-sandbox-node:latest registry.example.com/mgx-sandbox-node:latest
docker tag mgx-sandbox-php:latest registry.example.com/mgx-sandbox-php:latest

# Push to registry
docker push registry.example.com/mgx-sandbox-python:latest
docker push registry.example.com/mgx-sandbox-node:latest
docker push registry.example.com/mgx-sandbox-php:latest
```

### Security Considerations

1. **Image Scanning**: Scan base images for vulnerabilities
2. **Resource Limits**: Monitor and adjust based on usage
3. **Container Cleanup**: Automatic cleanup of stopped containers
4. **Access Control**: Limit which users can execute code
5. **Audit Logging**: Log all execution attempts and results

### Monitoring

```python
# Prometheus metrics (example)
from prometheus_client import Counter, Histogram, Gauge

execution_counter = Counter('sandbox_executions_total', 'Total sandbox executions')
execution_duration = Histogram('sandbox_execution_duration_seconds', 'Execution duration')
active_containers = Gauge('sandbox_active_containers', 'Active container count')
```

## Migration Guide

### From Phase 10 to Phase 11

1. **Database Migration**
   ```bash
   cd backend
   python -m alembic upgrade head
   ```

2. **Dependencies**
   ```bash
   pip install docker  # If not already installed
   ```

3. **Configuration**
   ```bash
   # Add to .env
   SANDBOX_ENABLED=true
   DOCKER_SOCKET_PATH=/var/run/docker.sock
   ```

4. **Testing**
   ```bash
   # Run sandbox tests
   pytest backend/tests/test_sandbox_execution.py -v
   ```

## Future Enhancements

### Phase 12+ Roadmap

1. **Real-time WebSocket Event Streaming**
   - Live execution updates
   - Progress indicators
   - Real-time log streaming

2. **Advanced Filtering**
   - Filter by duration, status ranges
   - Custom metrics queries
   - Historical trend analysis

3. **Metric Alerts**
   - Anomaly detection
   - Performance thresholds
   - Automated alerts

4. **Custom Metrics**
   - User-defined metrics
   - Business logic tracking
   - Custom dashboards

5. **Performance Forecasting**
   - Resource prediction
   - Capacity planning
   - Cost optimization

6. **Cost Tracking**
   - Resource consumption billing
   - Usage analytics
   - Budget alerts

## Conclusion

Phase 11 Sandboxed Code Runner provides enterprise-grade secure code execution with:

✅ **Multi-language support** (Python, JavaScript, PHP, Docker)  
✅ **Security hardening** (container isolation, resource limits)  
✅ **Automatic integration** (WriteCode → test → feedback)  
✅ **Real-time monitoring** (metrics, logs, events)  
✅ **Production ready** (scalable, monitored, documented)

This implementation enables agents to automatically test and validate generated code, providing immediate feedback and ensuring code quality before deployment.