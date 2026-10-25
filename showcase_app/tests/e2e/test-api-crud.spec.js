// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('API CRUD Operations', () => {
  const API_BASE = 'http://localhost:7331';

  test('should create a new pipeline via POST', async ({ request }) => {
    const newPipeline = {
      name: 'Test Pipeline - E2E',
      description: 'Pipeline created via e2e test',
      config: {
        steps: [
          {
            id: 'step_0',
            step_class: 'TransformStep',
            name: 'step1',
            module: 'pipelines.examples',
            config: { operation: 'uppercase' }
          }
        ],
        connections: [],
        flow: { paths: [] }
      },
      tags: []
    };

    const response = await request.post(`${API_BASE}/api/pipelines/`, {
      data: newPipeline
    });

    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.name).toBe('Test Pipeline - E2E');
    expect(body.id).toBeTruthy();
  });

  test('should get pipeline by ID via GET', async ({ request }) => {
    // First create a pipeline
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Get',
        config: { 
          steps: [{ id: 'step_0', step_class: 'TransformStep', name: 'step1', module: 'pipelines.examples', config: {} }], 
          connections: [],
          flow: { paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Now get it
    const getResponse = await request.get(`${API_BASE}/api/pipelines/${pipelineId}`);
    expect(getResponse.ok()).toBeTruthy();

    const body = await getResponse.json();
    expect(body.id).toBe(pipelineId);
    expect(body.name).toBe('Test Pipeline - Get');
  });

  test('should update pipeline via PUT', async ({ request }) => {
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Update',
        config: { 
          steps: [{ id: 'step_0', step_class: 'TransformStep', name: 'step1', module: 'pipelines.examples', config: {} }],
          connections: [],
          flow: { paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Update it
    const updateResponse = await request.put(`${API_BASE}/api/pipelines/${pipelineId}`, {
      data: {
        name: 'Test Pipeline - Updated',
        description: 'This was updated'
      }
    });

    expect(updateResponse.ok()).toBeTruthy();

    const body = await updateResponse.json();
    expect(body.name).toBe('Test Pipeline - Updated');
  });

  test('should delete pipeline via DELETE', async ({ request }) => {
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Delete',
        config: { 
          steps: [{ id: 'step_0', step_class: 'TransformStep', name: 'step1', module: 'pipelines.examples', config: {} }],
          connections: [],
          flow: { paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Delete it
    const deleteResponse = await request.delete(`${API_BASE}/api/pipelines/${pipelineId}`);
    expect(deleteResponse.ok()).toBeTruthy();

    // Verify it's gone
    const getResponse = await request.get(`${API_BASE}/api/pipelines/${pipelineId}`);
    expect(getResponse.ok()).toBeFalsy();
    expect(getResponse.status()).toBe(404);
  });

  test('should return 404 for non-existent pipeline', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines/non-existent-id`);
    expect(response.ok()).toBeFalsy();
    expect(response.status()).toBe(404);
  });

  test('should list all pipelines via GET', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThanOrEqual(0);
  });

  test('should get pipeline graph via GET', async ({ request }) => {
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Graph',
        config: {
          steps: [
            { id: 'step_0', step_class: 'TransformStep', name: 'step1', module: 'pipelines.examples', config: {} },
            { id: 'step_1', step_class: 'TransformStep', name: 'step2', module: 'pipelines.examples', config: {} }
          ],
          connections: [{ from: 'step_0', to: 'step_1' }],
          flow: { paths: [{ from: 'step_0', to: 'step_1' }] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Get graph
    const graphResponse = await request.get(`${API_BASE}/api/pipelines/${pipelineId}/graph`);
    expect(graphResponse.ok()).toBeTruthy();

    const body = await graphResponse.json();
    expect(body).toHaveProperty('nodes');
    expect(body).toHaveProperty('edges');
  });

  test('should create and execute pipeline', async ({ request }) => {
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Execute',
        config: {
          name: 'Test Pipeline - Execute',
          steps: [
            {
              id: 'step_0',
              step_class: 'TransformStep',
              name: 'transform',
              module: 'pipelines.examples',
              config: { operation: 'uppercase' }
            }
          ],
          connections: [],
          flow: { start_at: 'step_0', paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Execute it
    const executeResponse = await request.post(`${API_BASE}/api/execute/${pipelineId}`, {
      data: {
        input_data: { text: 'hello world' }
      }
    });

    expect(executeResponse.ok()).toBeTruthy();

    const body = await executeResponse.json();
    expect(body.job_id).toBeTruthy();
  });

  test('should get execution status', async ({ request }) => {
    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Status',
        config: {
          name: 'Test Pipeline - Status',
          steps: [{ id: 'step_0', step_class: 'TransformStep', name: 'step1', module: 'pipelines.examples', config: {} }],
          connections: [],
          flow: { start_at: 'step_0', paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    const executeResponse = await request.post(`${API_BASE}/api/execute/${pipelineId}`, {
      data: { input_data: { text: 'test' } }
    });

    expect(executeResponse.ok()).toBeTruthy();
    const execution = await executeResponse.json();
    const jobId = execution.job_id;

    // Get execution status
    const statusResponse = await request.get(`${API_BASE}/api/execute/${jobId}`);
    expect(statusResponse.ok()).toBeTruthy();

    const body = await statusResponse.json();
    expect(body.job_id).toBe(jobId);
  });

  test('should cancel execution', async ({ request }) => {
    // Use a multi-step pipeline with real steps so execution takes long enough to cancel
    const steps = Array.from({ length: 10 }, (_, i) => ({
      id: `step_${i}`,
      step_class: 'GreetingStep',
      name: `greeting_${i}`,
      module: 'pipelines.examples',
      config: {}
    }));
    const connections = steps.slice(0, -1).map((_, i) => ({
      from: `step_${i}`,
      to: `step_${i + 1}`
    }));

    const createResponse = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        name: 'Test Pipeline - Cancel (Slow)',
        config: {
          name: 'Test Pipeline - Cancel (Slow)',
          steps,
          connections,
          flow: { start_at: 'step_0', paths: [] }
        },
        tags: []
      }
    });

    expect(createResponse.ok()).toBeTruthy();
    const createdPipeline = await createResponse.json();
    const pipelineId = createdPipeline.id;

    // Execute it - this should take ~5s (10 steps x 0.5s each)
    const executeResponse = await request.post(`${API_BASE}/api/execute/${pipelineId}`, {
      data: { input_data: { name: 'test' } }
    });

    expect(executeResponse.ok()).toBeTruthy();
    const execution = await executeResponse.json();
    const jobId = execution.job_id;

    // Cancel it while still running
    const cancelResponse = await request.delete(`${API_BASE}/api/execute/${jobId}`);
    expect(cancelResponse.ok()).toBeTruthy();
  });

  test('should list executions', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/execute/`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('should handle validation errors', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/pipelines/`, {
      data: {
        // Missing required fields
      }
    });

    // Should return 400 or 422
    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should handle malformed JSON', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/pipelines/`, {
      headers: { 'Content-Type': 'application/json' },
      data: '{invalid json'
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should get metrics report', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/metrics/report`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body).toHaveProperty('svr');
  });

  test('should get SLO compliance', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/metrics/slo`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body).toHaveProperty('svr_compliant');
    expect(body).toHaveProperty('svr_target');
    expect(body).toHaveProperty('overall_compliant');
  });

  test('should get metric events', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/metrics/events`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('should clean up test pipelines', async ({ request }) => {
    const listResponse = await request.get(`${API_BASE}/api/pipelines/`);
    const data = await listResponse.json();
    const pipelines = Array.isArray(data) ? data : (data.pipelines || []);
    for (const pipeline of pipelines) {
      if (pipeline.name && pipeline.name.includes('Test Pipeline')) {
        await request.delete(`${API_BASE}/api/pipelines/${pipeline.id}`);
      }
    }
  });
});
