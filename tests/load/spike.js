/**
 * Load Test: Spike Scenario (500 → 2000 → 500 concurrent tasks)
 * 
 * This test validates system resilience during sudden traffic spikes.
 * Target: Rapid spike to 2000 users and recovery
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const spikeErrorRate = new Rate('spike_errors');
const taskCreationTime = new Trend('task_creation_duration');
const queueDepth = new Gauge('queue_depth');
const activeConnections = new Gauge('active_connections');
const recoveryTime = new Trend('recovery_time');

// Test configuration - 3 spike cycles
export const options = {
  stages: [
    // Baseline
    { duration: '2m', target: 500 },    // Establish baseline at 500 users
    
    // Spike 1
    { duration: '30s', target: 2000 },  // Sudden spike to 2000
    { duration: '5m', target: 2000 },   // Maintain spike
    { duration: '30s', target: 500 },   // Drop back to baseline
    { duration: '5m', target: 500 },    // Recovery period
    
    // Spike 2
    { duration: '30s', target: 2000 },  // Second spike
    { duration: '5m', target: 2000 },   // Maintain spike
    { duration: '30s', target: 500 },   // Drop back
    { duration: '5m', target: 500 },    // Recovery period
    
    // Spike 3
    { duration: '30s', target: 2000 },  // Third spike
    { duration: '5m', target: 2000 },   // Maintain spike
    { duration: '30s', target: 500 },   // Drop back
    { duration: '3m', target: 500 },    // Final recovery
    
    // Ramp down
    { duration: '1m', target: 0 },      // Graceful shutdown
  ],
  thresholds: {
    http_req_duration: ['p(99)<10000'],  // p99 < 10s during spike
    errors: ['rate<0.01'],                // Overall error rate < 1%
    spike_errors: ['rate<0.02'],          // Spike error rate < 2%
    http_req_failed: ['rate<0.01'],       // Failed requests < 1%
  },
  noConnectionReuse: false,
  userAgent: 'MGX-AI-LoadTest/1.0 (Spike)',
};

// Environment variables
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || 'test-workspace-1';

// Test data
const QUICK_TASKS = [
  'health_check',
  'validation',
  'quick_analysis',
  'status_check',
];

const NORMAL_TASKS = [
  'code_review',
  'test_generation',
  'documentation',
];

/**
 * Setup function
 */
export function setup() {
  console.log('Starting Spike Load Test');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Pattern: 500 → 2000 → 500 (3 cycles)`);
  
  const healthCheck = http.get(`${BASE_URL}/health/ready`);
  if (healthCheck.status !== 200) {
    throw new Error('API is not ready');
  }
  
  return {
    startTime: new Date().toISOString(),
    spikeTimes: [],
  };
}

/**
 * Detect if we're in a spike period based on active VUs
 */
function isSpikePeriod() {
  // During spike, we have 2000 VUs; baseline is 500
  return __VU > 500;
}

/**
 * Main test function
 */
export default function (data) {
  activeConnections.add(1);
  const isSpike = isSpikePeriod();

  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-Workspace-ID': WORKSPACE_ID,
    'X-Load-Test': 'spike',
  };

  // During spike, use quick tasks to simulate burst traffic
  const taskList = isSpike ? QUICK_TASKS : NORMAL_TASKS;
  const taskType = taskList[Math.floor(Math.random() * taskList.length)];

  // Create task
  const taskPayload = JSON.stringify({
    name: `Spike Test - ${taskType} - VU${__VU}`,
    description: `${isSpike ? 'SPIKE' : 'BASELINE'} task`,
    type: taskType,
    agent_id: `agent-spike-${(__VU % 20) + 1}`,
    priority: isSpike ? 3 : 2, // Higher priority during spike
    config: {
      timeout: isSpike ? 30 : 60,
      quick_mode: isSpike,
    },
    metadata: {
      test: 'spike',
      phase: isSpike ? 'spike' : 'baseline',
      virtual_user: __VU,
      iteration: __ITER,
      timestamp: new Date().toISOString(),
    },
  });

  const createStart = new Date();
  const createResponse = http.post(
    `${BASE_URL}/api/v1/tasks`,
    taskPayload,
    { 
      headers,
      timeout: isSpike ? '15s' : '30s', // Shorter timeout during spike
    }
  );
  
  const createDuration = new Date() - createStart;
  taskCreationTime.add(createDuration);

  const createSuccess = check(createResponse, {
    'task created': (r) => r.status === 201 || r.status === 200,
    'not rate limited': (r) => r.status !== 429,
    'not server error': (r) => r.status < 500,
    'response time reasonable': (r) => r.timings.duration < (isSpike ? 10000 : 5000),
  });

  if (!createSuccess) {
    errorRate.add(1);
    if (isSpike) {
      spikeErrorRate.add(1);
    }
    
    // Log specific errors during spike
    if (isSpike && createResponse.status >= 500) {
      console.error(`[SPIKE] Server error: ${createResponse.status} - ${createResponse.body.substring(0, 100)}`);
    }
    
    if (createResponse.status === 429) {
      console.warn(`[SPIKE] Rate limited - backpressure working`);
      sleep(5); // Back off when rate limited
      return;
    }
    
    sleep(2);
    return;
  }

  const taskId = JSON.parse(createResponse.body).id;

  // During spike, check queue metrics
  if (isSpike && __ITER % 10 === 0) {
    const metricsResponse = http.get(
      `${BASE_URL}/api/v1/metrics/queue`,
      { headers, timeout: '5s' }
    );
    
    if (metricsResponse.status === 200) {
      try {
        const metrics = JSON.parse(metricsResponse.body);
        queueDepth.add(metrics.depth || 0);
      } catch (e) {
        // Ignore parse errors during high load
      }
    }
  }

  // Quick polling during spike
  if (isSpike) {
    // Don't wait for completion during spike - just verify submission
    sleep(1);
  } else {
    // Normal polling during baseline
    let taskCompleted = false;
    let attempts = 0;
    const maxAttempts = 5;

    while (!taskCompleted && attempts < maxAttempts) {
      sleep(2);
      
      const statusResponse = http.get(
        `${BASE_URL}/api/v1/tasks/${taskId}`,
        { headers, timeout: '10s' }
      );

      if (statusResponse.status === 200) {
        try {
          const task = JSON.parse(statusResponse.body);
          if (task.status === 'completed' || task.status === 'failed') {
            taskCompleted = true;
          }
        } catch (e) {
          // Continue polling
        }
      }
      
      attempts++;
    }
  }

  // Minimal think time during spike
  sleep(isSpike ? Math.random() : Math.random() * 3 + 2);
}

/**
 * Teardown function
 */
export function teardown(data) {
  console.log('Spike Load Test Complete');
  console.log(`Started: ${data.startTime}`);
  console.log(`Ended: ${new Date().toISOString()}`);
  
  // Check system recovery
  console.log('Checking system recovery...');
  sleep(10); // Wait for system to stabilize
  
  const finalHealth = http.get(`${BASE_URL}/health/status`);
  console.log(`Final System Status: ${finalHealth.status}`);
  
  if (finalHealth.status === 200) {
    console.log('✅ System recovered successfully');
  } else {
    console.log('❌ System may not have fully recovered');
  }
  
  // Check for any lingering queue backlog
  const finalMetrics = http.get(`${BASE_URL}/api/v1/metrics/queue`);
  if (finalMetrics.status === 200) {
    try {
      const metrics = JSON.parse(finalMetrics.body);
      console.log(`Final queue depth: ${metrics.depth || 0}`);
      
      if (metrics.depth > 100) {
        console.warn('⚠️  Significant queue backlog remaining');
      }
    } catch (e) {
      console.log('Could not parse final metrics');
    }
  }
}
