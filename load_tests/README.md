# Load Testing

This directory contains load testing scenarios for the platform using both Locust and K6.

## Tools

### Locust (Python-based)

**Installation:**
```bash
pip install locust
```

**Run basic load test:**
```bash
cd load_tests
locust -f locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser to configure and start the test.

**Run from command line:**
```bash
# 100 users, spawn rate of 10 users/second, run for 5 minutes
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless
```

**Run specific tags:**
```bash
# Only health checks
locust -f locustfile.py --host=http://localhost:8000 --tags health

# Exclude write operations
locust -f locustfile.py --host=http://localhost:8000 --exclude-tags write
```

### K6 (JavaScript-based)

**Installation:**
```bash
# macOS
brew install k6

# Linux
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Windows
choco install k6
```

**Run load test:**
```bash
cd load_tests
k6 run k6_script.js
```

**Run with custom target:**
```bash
k6 run --vus 100 --duration 5m k6_script.js
```

**Run with environment variables:**
```bash
k6 run -e BASE_URL=http://production.example.com k6_script.js
```

## Test Scenarios

### 1. Smoke Test
Minimal load to verify system is working.

**Locust:**
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 5 --spawn-rate 1 --run-time 2m --headless
```

**K6:**
```bash
k6 run --vus 5 --duration 2m k6_script.js
```

### 2. Load Test
Normal expected load.

**Locust:**
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 10m --headless
```

**K6:**
```bash
k6 run k6_script.js  # Uses configured stages
```

### 3. Stress Test
Push system to limits.

**Locust:**
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 500 --spawn-rate 50 --run-time 10m --headless
```

**K6:**
```bash
k6 run --stage 2m:200,5m:200,2m:0 k6_script.js
```

### 4. Spike Test
Sudden traffic increase.

**Locust:**
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 200 --spawn-rate 100 --run-time 5m --headless
```

**K6:**
```bash
k6 run --stage 30s:20,1m:200,30s:20 k6_script.js
```

### 5. Endurance Test
Sustained load over extended period.

**Locust:**
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 2h --headless
```

## Performance Thresholds

Our target performance metrics:

- **P95 Response Time**: < 500ms
- **P99 Response Time**: < 1000ms
- **Error Rate**: < 0.1%
- **Throughput**: > 100 requests/second
- **CPU Usage**: < 80%
- **Memory Growth**: < 100MB over 10 minutes

## Monitoring During Tests

While running load tests, monitor:

1. **Application Metrics**:
   - Response times (P50, P95, P99)
   - Request rate
   - Error rate
   - Active connections

2. **System Metrics**:
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O

3. **Database Metrics**:
   - Query time
   - Connection pool usage
   - Lock contention
   - Cache hit rate

## Analyzing Results

### Locust Results

Locust provides:
- Real-time web UI at http://localhost:8089
- CSV exports (statistics, failures, exceptions)
- HTML report generation

Generate HTML report:
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless \
  --html=report.html
```

### K6 Results

K6 outputs:
- Summary statistics to console
- JSON export with `--out json=results.json`
- Integration with monitoring tools

Export to JSON:
```bash
k6 run --out json=results.json k6_script.js
```

Export to InfluxDB:
```bash
k6 run --out influxdb=http://localhost:8086/k6 k6_script.js
```

## Continuous Load Testing

Integrate load tests into CI/CD:

```yaml
# .github/workflows/load-test.yml
name: Load Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install K6
        run: |
          sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6
      
      - name: Run Load Test
        run: k6 run load_tests/k6_script.js
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: results.json
```

## Best Practices

1. **Start Small**: Begin with smoke tests before running full load tests
2. **Monitor Everything**: Keep an eye on all metrics during tests
3. **Ramp Up Gradually**: Use staged ramp-up to avoid overwhelming the system
4. **Test Realistic Scenarios**: Match production user behavior patterns
5. **Clean Up**: Remove test data after load tests
6. **Document Baselines**: Track performance over time
7. **Test in Isolation**: Run load tests in dedicated environment when possible

## Troubleshooting

**High error rates:**
- Check application logs
- Verify database connections
- Check rate limiting settings
- Ensure adequate resources

**Slow response times:**
- Profile application code
- Check database query performance
- Verify caching is working
- Check network latency

**Connection failures:**
- Increase connection pool size
- Check firewall settings
- Verify load balancer configuration
- Check file descriptor limits

## User Classes

### PlatformUser (Normal Load)
- Health checks
- List/create workspaces
- List/create workflows
- Trigger executions
- Search knowledge base

### AdminUser (Administrative)
- System metrics
- Audit logs
- User management
- Cost tracking

### HeavyUser (Resource Intensive)
- Large project generation
- Large dataset searches
- Codebase analysis

## Contact

For questions about load testing, contact the DevOps team.
