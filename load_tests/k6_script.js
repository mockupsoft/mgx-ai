// K6 load testing script for the platform
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiResponseTime = new Trend('api_response_time');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users over 2 minutes
    { duration: '5m', target: 100 },  // Ramp up to 100 users over 5 minutes
    { duration: '10m', target: 100 }, // Stay at 100 users for 10 minutes
    { duration: '3m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% of requests under 500ms, 99% under 1s
    http_req_failed: ['rate<0.01'],                  // Error rate under 1%
    errors: ['rate<0.001'],                          // Custom error rate under 0.1%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Setup: runs once before all iterations
export function setup() {
  // Can perform authentication or data setup here
  return { baseUrl: BASE_URL };
}

// Main test function: runs for each virtual user
export default function (data) {
  const baseUrl = data.baseUrl;
  
  // Test 1: Health check
  testHealthCheck(baseUrl);
  sleep(1);
  
  // Test 2: List workspaces
  const workspaceId = testListWorkspaces(baseUrl);
  sleep(1);
  
  // Test 3: Create workspace
  testCreateWorkspace(baseUrl);
  sleep(1);
  
  if (workspaceId) {
    // Test 4: List workflows
    testListWorkflows(baseUrl, workspaceId);
    sleep(1);
    
    // Test 5: Search knowledge base
    testSearchKnowledge(baseUrl, workspaceId);
    sleep(2);
  }
}

function testHealthCheck(baseUrl) {
  const startTime = new Date();
  const response = http.get(`${baseUrl}/health`);
  const duration = new Date() - startTime;
  
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 100ms': (r) => duration < 100,
  });
  
  errorRate.add(!success);
}

function testListWorkspaces(baseUrl) {
  const startTime = new Date();
  const response = http.get(`${baseUrl}/api/workspaces`);
  const duration = new Date() - startTime;
  
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'list workspaces status is 200': (r) => r.status === 200,
    'list workspaces response time < 500ms': (r) => duration < 500,
    'list workspaces returns array': (r) => Array.isArray(JSON.parse(r.body || '[]')),
  });
  
  errorRate.add(!success);
  
  // Extract workspace ID if available
  if (response.status === 200) {
    const workspaces = JSON.parse(response.body || '[]');
    if (workspaces.length > 0) {
      return workspaces[0].id;
    }
  }
  
  return null;
}

function testCreateWorkspace(baseUrl) {
  const payload = JSON.stringify({
    name: `load-test-${Date.now()}`,
    description: 'Created by K6 load test',
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const startTime = new Date();
  const response = http.post(`${baseUrl}/api/workspaces`, payload, params);
  const duration = new Date() - startTime;
  
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'create workspace status is 201': (r) => r.status === 201 || r.status === 200,
    'create workspace response time < 1000ms': (r) => duration < 1000,
    'create workspace returns id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });
  
  errorRate.add(!success);
}

function testListWorkflows(baseUrl, workspaceId) {
  const startTime = new Date();
  const response = http.get(`${baseUrl}/api/workspaces/${workspaceId}/workflows`);
  const duration = new Date() - startTime;
  
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'list workflows status is 200': (r) => r.status === 200,
    'list workflows response time < 500ms': (r) => duration < 500,
  });
  
  errorRate.add(!success);
}

function testSearchKnowledge(baseUrl, workspaceId) {
  const queries = ['python', 'javascript', 'docker', 'api', 'database'];
  const query = queries[Math.floor(Math.random() * queries.length)];
  
  const startTime = new Date();
  const response = http.get(
    `${baseUrl}/api/workspaces/${workspaceId}/knowledge/search?query=${query}&limit=10`
  );
  const duration = new Date() - startTime;
  
  apiResponseTime.add(duration);
  
  const success = check(response, {
    'search status is 200': (r) => r.status === 200,
    'search response time < 300ms': (r) => duration < 300,
  });
  
  errorRate.add(!success);
}

// Teardown: runs once after all iterations
export function teardown(data) {
  // Can perform cleanup here
  console.log('Load test completed');
}

// Scenario-specific tests

export function smokeTest() {
  // Quick smoke test with 1-2 users
  const response = http.get(`${BASE_URL}/health`);
  check(response, {
    'smoke test - health is OK': (r) => r.status === 200,
  });
}

export function stressTest() {
  // Stress test configuration
  const stages = [
    { duration: '2m', target: 200 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ];
  
  // Run all tests with higher load
  testHealthCheck(BASE_URL);
  testListWorkspaces(BASE_URL);
  testCreateWorkspace(BASE_URL);
}

export function spikeTest() {
  // Spike test - sudden traffic increase
  const stages = [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 200 },  // Sudden spike
    { duration: '30s', target: 20 },
  ];
  
  testHealthCheck(BASE_URL);
  testListWorkspaces(BASE_URL);
}
