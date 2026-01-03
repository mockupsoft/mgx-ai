/**
 * Load Test: Ramp-Up Scenario (0 → 1000 concurrent tasks)
 * 
 * This test validates system stability during gradual load increase.
 * Target: Linear increase from 0 to 1000 concurrent users over 10 minutes
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const taskCreationTime = new Trend('task_creation_duration');
const taskExecutionTime = new Trend('task_execution_duration');
const successfulTasks = new Counter('successful_tasks');
const failedTasks = new Counter('failed_tasks');

// Test configuration
export const options = {
  stages: [
    { duration: '10m', target: 1000 },  // Ramp up to 1000 users over 10 minutes
    { duration: '2m', target: 1000 },   // Stay at 1000 users for 2 minutes
    { duration: '2m', target: 0 },      // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000', 'p(99)<5000'],  // 95% < 3s, 99% < 5s
    errors: ['rate<0.001'],                            // Error rate < 0.1%
    http_req_failed: ['rate<0.001'],                   // Failed requests < 0.1%
  },
  // Test-wide configuration
  noConnectionReuse: false,
  userAgent: 'MGX-AI-LoadTest/1.0 (Ramp-Up)',
};

// Environment variables
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || 'test-workspace-1';

// Test data
const TASK_TEMPLATES = [
  { type: 'simple', description: 'Simple task', expectedDuration: 1 },
  { type: 'medium', description: 'Medium complexity task', expectedDuration: 3 },
  { type: 'complex', description: 'Complex task', expectedDuration: 10 },
];

/**
 * Setup function - runs once before test
 */
export function setup() {
  console.log('Starting Ramp-Up Load Test');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Workspace: ${WORKSPACE_ID}`);
  
  // Verify API is accessible
  const healthCheck = http.get(`${BASE_URL}/health/ready`);
  if (healthCheck.status !== 200) {
    throw new Error('API is not ready');
  }
  
  return {
    startTime: new Date().toISOString(),
  };
}

/**
 * Main test function - runs for each virtual user
 */
export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-Workspace-ID': WORKSPACE_ID,
  };

  // Select random task template (weighted distribution)
  const rand = Math.random();
  let template;
  if (rand < 0.4) {
    template = TASK_TEMPLATES[0]; // 40% simple
  } else if (rand < 0.75) {
    template = TASK_TEMPLATES[1]; // 35% medium
  } else {
    template = TASK_TEMPLATES[2]; // 25% complex
  }

  // Create a task
  const taskPayload = JSON.stringify({
    name: `Load Test Task ${__VU}-${__ITER}`,
    description: `${template.description} (VU: ${__VU}, Iteration: ${__ITER})`,
    type: template.type,
    agent_id: `test-agent-${(__VU % 10) + 1}`, // Distribute across 10 agents
    priority: Math.floor(Math.random() * 3) + 1, // Priority 1-3
    metadata: {
      test: 'ramp-up',
      virtual_user: __VU,
      iteration: __ITER,
      timestamp: new Date().toISOString(),
    },
  });

  const createStart = new Date();
  const createResponse = http.post(
    `${BASE_URL}/api/v1/tasks`,
    taskPayload,
    { headers }
  );
  
  const createDuration = new Date() - createStart;
  taskCreationTime.add(createDuration);

  const createSuccess = check(createResponse, {
    'task created': (r) => r.status === 201 || r.status === 200,
    'response has task_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!createSuccess) {
    errorRate.add(1);
    failedTasks.add(1);
    console.error(`Failed to create task: ${createResponse.status} - ${createResponse.body}`);
    sleep(1);
    return;
  }

  const taskId = JSON.parse(createResponse.body).id;

  // Wait a bit before checking task status
  sleep(Math.random() * 2 + 1); // Random 1-3 seconds

  // Poll task status
  let taskCompleted = false;
  let attempts = 0;
  const maxAttempts = 10;
  const pollStart = new Date();

  while (!taskCompleted && attempts < maxAttempts) {
    const statusResponse = http.get(
      `${BASE_URL}/api/v1/tasks/${taskId}`,
      { headers }
    );

    const statusCheck = check(statusResponse, {
      'status check successful': (r) => r.status === 200,
    });

    if (statusCheck) {
      try {
        const task = JSON.parse(statusResponse.body);
        if (task.status === 'completed' || task.status === 'failed') {
          taskCompleted = true;
          const executionDuration = new Date() - pollStart;
          taskExecutionTime.add(executionDuration);
          
          if (task.status === 'completed') {
            successfulTasks.add(1);
          } else {
            failedTasks.add(1);
          }
        }
      } catch (e) {
        console.error(`Failed to parse task status: ${e}`);
      }
    } else {
      errorRate.add(1);
    }

    attempts++;
    sleep(2); // Wait 2 seconds between polls
  }

  if (!taskCompleted) {
    console.warn(`Task ${taskId} did not complete within ${maxAttempts * 2} seconds`);
  }

  // Think time between iterations
  sleep(Math.random() * 3 + 1); // Random 1-4 seconds
}

/**
 * Teardown function - runs once after test
 */
export function teardown(data) {
  console.log('Ramp-Up Load Test Complete');
  console.log(`Started: ${data.startTime}`);
  console.log(`Ended: ${new Date().toISOString()}`);
}
