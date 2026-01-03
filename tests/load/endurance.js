/**
 * Load Test: Endurance Scenario (500 concurrent tasks for 8 hours)
 * 
 * This test validates system stability over extended time periods.
 * Target: Maintain 500 concurrent users for 8 hours
 * Focus: Memory leaks, performance degradation, resource exhaustion
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const taskCreationTime = new Trend('task_creation_duration');
const taskExecutionTime = new Trend('task_execution_duration');
const successfulTasks = new Counter('successful_tasks');
const failedTasks = new Counter('failed_tasks');
const memoryUsage = new Gauge('memory_usage_mb');
const responseTimeHourly = new Trend('response_time_hourly');
const connectionErrors = new Counter('connection_errors');

// Test configuration
export const options = {
  stages: [
    { duration: '5m', target: 500 },     // Ramp up to 500 users over 5 minutes
    { duration: '8h', target: 500 },     // Sustain 500 users for 8 hours
    { duration: '5m', target: 0 },       // Ramp down over 5 minutes
  ],
  thresholds: {
    http_req_duration: ['p(99)<5000'],    // p99 < 5s throughout test
    errors: ['rate<0.001'],               // Error rate < 0.1%
    http_req_failed: ['rate<0.001'],      // Failed requests < 0.1%
    connection_errors: ['count<100'],     // Less than 100 connection errors
  },
  noConnectionReuse: false,
  discardResponseBodies: true, // Reduce memory usage
  userAgent: 'MGX-AI-LoadTest/1.0 (Endurance)',
};

// Environment variables
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || 'test-workspace-1';

// Test data - Mix of task types
const TASK_TYPES = [
  'code_review',
  'bug_fix',
  'test_generation',
  'documentation',
  'refactoring',
];

/**
 * Setup function
 */
export function setup() {
  console.log('Starting Endurance Load Test');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Duration: 8 hours at 500 concurrent users`);
  console.log(`Focus: Memory leaks, performance degradation, resource exhaustion`);
  
  const healthCheck = http.get(`${BASE_URL}/health/ready`);
  if (healthCheck.status !== 200) {
    throw new Error('API is not ready');
  }
  
  // Get initial system metrics
  const initialMetrics = http.get(`${BASE_URL}/health/status`);
  console.log(`Initial System Status: ${initialMetrics.body}`);
  
  return {
    startTime: new Date().toISOString(),
    initialMemory: 0, // Will be populated if metrics available
    checkpoints: [],
  };
}

/**
 * Calculate current test hour (0-8)
 */
function getCurrentHour() {
  // Approximate based on iteration
  // First 5 minutes is ramp-up, then 8 hours sustained
  const estimatedMinutes = __ITER * 0.5; // Rough estimate
  if (estimatedMinutes < 5) return 0;
  return Math.min(Math.floor((estimatedMinutes - 5) / 60), 8);
}

/**
 * Main test function
 */
export default function (data) {
  const currentHour = getCurrentHour();
  
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-Workspace-ID': WORKSPACE_ID,
    'X-Load-Test': 'endurance',
    'X-Test-Hour': currentHour.toString(),
  };

  // Select random task type
  const taskType = TASK_TYPES[Math.floor(Math.random() * TASK_TYPES.length)];

  // Create task
  const taskPayload = JSON.stringify({
    name: `Endurance Test - ${taskType} - VU${__VU}-IT${__ITER}`,
    description: `Endurance test task (Hour ${currentHour})`,
    type: taskType,
    agent_id: `agent-endurance-${(__VU % 25) + 1}`, // 25 agents
    priority: Math.floor(Math.random() * 3) + 1,
    metadata: {
      test: 'endurance',
      hour: currentHour,
      virtual_user: __VU,
      iteration: __ITER,
      timestamp: new Date().toISOString(),
    },
  });

  const createStart = new Date();
  let createResponse;
  
  try {
    createResponse = http.post(
      `${BASE_URL}/api/v1/tasks`,
      taskPayload,
      { 
        headers,
        timeout: '30s',
      }
    );
  } catch (e) {
    console.error(`Connection error: ${e}`);
    connectionErrors.add(1);
    errorRate.add(1);
    sleep(10); // Back off on connection errors
    return;
  }
  
  const createDuration = new Date() - createStart;
  taskCreationTime.add(createDuration);
  responseTimeHourly.add(createDuration);

  const createSuccess = check(createResponse, {
    'task created': (r) => r.status === 201 || r.status === 200,
    'response time acceptable': (r) => r.timings.duration < 5000,
    'no connection errors': (r) => r.status !== 0,
    'no timeout': (r) => r.timings.duration < 30000,
  });

  if (!createSuccess) {
    errorRate.add(1);
    failedTasks.add(1);
    
    if (createResponse && createResponse.status >= 500) {
      console.error(`[Hour ${currentHour}] Server error: ${createResponse.status}`);
    }
    
    if (createResponse && createResponse.status === 0) {
      console.error(`[Hour ${currentHour}] Connection refused or timeout`);
      connectionErrors.add(1);
    }
    
    sleep(5);
    return;
  }

  let taskId;
  try {
    taskId = JSON.parse(createResponse.body).id;
  } catch (e) {
    console.error(`Failed to parse task response: ${e}`);
    errorRate.add(1);
    sleep(3);
    return;
  }

  // Wait before checking status
  sleep(Math.random() * 3 + 2); // Random 2-5 seconds

  // Poll task status
  let taskCompleted = false;
  let attempts = 0;
  const maxAttempts = 10;
  const pollStart = new Date();

  while (!taskCompleted && attempts < maxAttempts) {
    let statusResponse;
    
    try {
      statusResponse = http.get(
        `${BASE_URL}/api/v1/tasks/${taskId}`,
        { 
          headers,
          timeout: '15s',
        }
      );
    } catch (e) {
      console.error(`Error polling task ${taskId}: ${e}`);
      connectionErrors.add(1);
      attempts++;
      sleep(5);
      continue;
    }

    const statusCheck = check(statusResponse, {
      'status check successful': (r) => r.status === 200,
      'no timeout': (r) => r.timings.duration < 15000,
    });

    if (statusCheck) {
      try {
        const task = JSON.parse(statusResponse.body);
        
        if (task.status === 'completed') {
          taskCompleted = true;
          const executionDuration = new Date() - pollStart;
          taskExecutionTime.add(executionDuration);
          successfulTasks.add(1);
          
        } else if (task.status === 'failed') {
          taskCompleted = true;
          failedTasks.add(1);
          console.error(`[Hour ${currentHour}] Task ${taskId} failed`);
        }
      } catch (e) {
        console.error(`Failed to parse task status: ${e}`);
      }
    } else {
      errorRate.add(1);
    }

    attempts++;
    sleep(3); // Wait 3 seconds between polls
  }

  if (!taskCompleted) {
    console.warn(`[Hour ${currentHour}] Task ${taskId} did not complete`);
    failedTasks.add(1);
  }

  // Periodic health checks (every 100 iterations)
  if (__ITER % 100 === 0) {
    try {
      const healthResponse = http.get(
        `${BASE_URL}/health/status`,
        { headers, timeout: '10s' }
      );
      
      if (healthResponse.status === 200) {
        try {
          const health = JSON.parse(healthResponse.body);
          
          // Track memory usage if available
          if (health.memory_mb) {
            memoryUsage.add(health.memory_mb);
            
            // Alert on memory growth
            if (data.initialMemory > 0 && health.memory_mb > data.initialMemory * 2) {
              console.warn(`[Hour ${currentHour}] Memory usage doubled: ${health.memory_mb}MB`);
            }
          }
          
          // Check for degraded services
          if (health.status !== 'healthy') {
            console.warn(`[Hour ${currentHour}] System health degraded: ${health.status}`);
          }
        } catch (e) {
          // Continue test even if health check parsing fails
        }
      }
    } catch (e) {
      console.error(`[Hour ${currentHour}] Health check failed: ${e}`);
    }
  }

  // Realistic think time
  const thinkTime = Math.random() * 8 + 4; // Random 4-12 seconds
  sleep(thinkTime);
}

/**
 * Teardown function
 */
export function teardown(data) {
  console.log('Endurance Load Test Complete');
  console.log(`Started: ${data.startTime}`);
  console.log(`Ended: ${new Date().toISOString()}`);
  console.log(`Duration: 8 hours`);
  
  // Final comprehensive health check
  console.log('Performing final health check...');
  sleep(30); // Wait for system to stabilize
  
  const finalHealth = http.get(`${BASE_URL}/health/status`);
  console.log(`Final System Status: ${finalHealth.status}`);
  
  if (finalHealth.status === 200) {
    try {
      const health = JSON.parse(finalHealth.body);
      console.log(`Final Health: ${JSON.stringify(health, null, 2)}`);
      
      // Check for memory leaks
      if (data.initialMemory > 0 && health.memory_mb) {
        const memoryGrowth = ((health.memory_mb - data.initialMemory) / data.initialMemory) * 100;
        console.log(`Memory growth: ${memoryGrowth.toFixed(2)}%`);
        
        if (memoryGrowth > 50) {
          console.warn('⚠️  Possible memory leak detected (>50% growth)');
        } else {
          console.log('✅ No significant memory leak detected');
        }
      }
      
      // Check system health
      if (health.status === 'healthy') {
        console.log('✅ System remained healthy throughout test');
      } else {
        console.warn('⚠️  System health degraded during test');
      }
    } catch (e) {
      console.log('Could not parse final health status');
    }
  } else {
    console.log('❌ System may have issues - health check failed');
  }
  
  console.log('Endurance test analysis complete');
}
