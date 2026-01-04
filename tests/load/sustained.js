/**
 * Load Test: Sustained Load Scenario (1000 concurrent tasks for 1 hour)
 * 
 * This test validates system stability under constant high load.
 * Target: Maintain 1000 concurrent users for 60 minutes
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const taskCreationTime = new Trend('task_creation_duration');
const taskExecutionTime = new Trend('task_execution_duration');
const taskCompletionRate = new Rate('task_completion_rate');
const successfulTasks = new Counter('successful_tasks');
const failedTasks = new Counter('failed_tasks');
const activeUsers = new Gauge('active_virtual_users');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 1000 },   // Ramp up to 1000 users over 2 minutes
    { duration: '60m', target: 1000 },  // Sustain 1000 users for 60 minutes
    { duration: '2m', target: 0 },      // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(50)<1000', 'p(95)<3000', 'p(99)<5000'],  // p50<1s, p95<3s, p99<5s
    errors: ['rate<0.001'],                                          // Error rate < 0.1%
    http_req_failed: ['rate<0.001'],                                 // Failed requests < 0.1%
    task_completion_rate: ['rate>0.99'],                             // Task completion > 99%
  },
  noConnectionReuse: false,
  userAgent: 'MGX-AI-LoadTest/1.0 (Sustained)',
};

// Environment variables
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || 'test-workspace-1';

// Test data - Realistic workload mix
const TASK_TYPES = [
  { type: 'code_review', weight: 0.25, duration: 5 },
  { type: 'bug_fix', weight: 0.20, duration: 8 },
  { type: 'feature_implementation', weight: 0.15, duration: 15 },
  { type: 'test_generation', weight: 0.15, duration: 4 },
  { type: 'documentation', weight: 0.10, duration: 3 },
  { type: 'refactoring', weight: 0.10, duration: 10 },
  { type: 'analysis', weight: 0.05, duration: 20 },
];

const LLM_PROVIDERS = ['openai', 'anthropic', 'google', 'local'];

/**
 * Setup function - runs once before test
 */
export function setup() {
  console.log('Starting Sustained Load Test');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Duration: 60 minutes at 1000 concurrent users`);
  
  // Verify API is accessible
  const healthCheck = http.get(`${BASE_URL}/health/ready`);
  if (healthCheck.status !== 200) {
    throw new Error('API is not ready');
  }
  
  // Get system info
  const statusCheck = http.get(`${BASE_URL}/health/status`);
  console.log(`System Status: ${statusCheck.body}`);
  
  return {
    startTime: new Date().toISOString(),
    testDuration: '60m',
  };
}

/**
 * Select task type based on weighted distribution
 */
function selectTaskType() {
  const rand = Math.random();
  let cumulative = 0;
  
  for (const taskType of TASK_TYPES) {
    cumulative += taskType.weight;
    if (rand < cumulative) {
      return taskType;
    }
  }
  
  return TASK_TYPES[0]; // Fallback
}

/**
 * Main test function - runs for each virtual user
 */
export default function (data) {
  activeUsers.add(1);

  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-Workspace-ID': WORKSPACE_ID,
  };

  // Select task type based on realistic distribution
  const taskType = selectTaskType();
  const provider = LLM_PROVIDERS[Math.floor(Math.random() * LLM_PROVIDERS.length)];

  // Create a task
  const taskPayload = JSON.stringify({
    name: `${taskType.type} - VU${__VU}-IT${__ITER}`,
    description: `Automated task for ${taskType.type}`,
    type: taskType.type,
    agent_id: `agent-${provider}-${(__VU % 50) + 1}`, // 50 agents per provider
    priority: Math.floor(Math.random() * 5) + 1, // Priority 1-5
    config: {
      llm_provider: provider,
      max_iterations: 3,
      timeout: taskType.duration * 60, // Convert to seconds
    },
    metadata: {
      test: 'sustained',
      virtual_user: __VU,
      iteration: __ITER,
      timestamp: new Date().toISOString(),
      expected_duration: taskType.duration,
    },
  });

  const createStart = new Date();
  const createResponse = http.post(
    `${BASE_URL}/api/v1/tasks`,
    taskPayload,
    { 
      headers,
      timeout: '30s',
    }
  );
  
  const createDuration = new Date() - createStart;
  taskCreationTime.add(createDuration);

  const createSuccess = check(createResponse, {
    'task created': (r) => r.status === 201 || r.status === 200,
    'response time acceptable': (r) => r.timings.duration < 5000, // < 5s
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
    taskCompletionRate.add(0);
    
    if (createResponse.status !== 200 && createResponse.status !== 201) {
      console.error(`[${new Date().toISOString()}] Failed to create task: ${createResponse.status}`);
    }
    
    sleep(5);
    return;
  }

  const taskId = JSON.parse(createResponse.body).id;

  // Simulate realistic user behavior - wait before checking
  sleep(Math.random() * 5 + 2); // Random 2-7 seconds

  // Poll task status with exponential backoff
  let taskCompleted = false;
  let attempts = 0;
  const maxAttempts = Math.ceil(taskType.duration / 2) + 5; // Based on expected duration
  const pollStart = new Date();
  let backoff = 2;

  while (!taskCompleted && attempts < maxAttempts) {
    const statusResponse = http.get(
      `${BASE_URL}/api/v1/tasks/${taskId}`,
      { 
        headers,
        timeout: '10s',
      }
    );

    const statusCheck = check(statusResponse, {
      'status check successful': (r) => r.status === 200,
      'response time acceptable': (r) => r.timings.duration < 2000, // < 2s
    });

    if (statusCheck) {
      try {
        const task = JSON.parse(statusResponse.body);
        
        if (task.status === 'completed') {
          taskCompleted = true;
          const executionDuration = new Date() - pollStart;
          taskExecutionTime.add(executionDuration);
          successfulTasks.add(1);
          taskCompletionRate.add(1);
          
          // Verify task quality
          check(task, {
            'task has output': (t) => t.output !== undefined && t.output !== null,
            'task completed within expected time': (t) => 
              executionDuration < (taskType.duration * 60 * 1000 * 1.5), // 150% of expected
          });
          
        } else if (task.status === 'failed' || task.status === 'cancelled') {
          taskCompleted = true;
          failedTasks.add(1);
          taskCompletionRate.add(0);
          console.error(`Task ${taskId} failed with status: ${task.status}`);
          
        } else if (task.status === 'running' || task.status === 'pending') {
          // Task still in progress, continue polling
        } else {
          console.warn(`Unknown task status: ${task.status}`);
        }
      } catch (e) {
        console.error(`Failed to parse task status: ${e}`);
        errorRate.add(1);
      }
    } else {
      errorRate.add(1);
      
      if (statusResponse.status >= 500) {
        console.error(`Server error checking task ${taskId}: ${statusResponse.status}`);
      }
    }

    if (!taskCompleted) {
      attempts++;
      sleep(backoff);
      backoff = Math.min(backoff * 1.5, 10); // Exponential backoff, max 10s
    }
  }

  if (!taskCompleted) {
    console.warn(`Task ${taskId} did not complete within ${maxAttempts * 2} seconds`);
    taskCompletionRate.add(0);
    failedTasks.add(1);
  }

  // Realistic think time between tasks
  const thinkTime = Math.random() * 10 + 5; // Random 5-15 seconds
  sleep(thinkTime);
}

/**
 * Teardown function - runs once after test
 */
export function teardown(data) {
  console.log('Sustained Load Test Complete');
  console.log(`Started: ${data.startTime}`);
  console.log(`Ended: ${new Date().toISOString()}`);
  console.log(`Duration: ${data.testDuration}`);
  
  // Final health check
  const finalHealth = http.get(`${BASE_URL}/health/status`);
  console.log(`Final System Status: ${finalHealth.body}`);
}
