// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('API Integration', () => {
  const API_BASE = 'http://localhost:7331';

  test('should have backend API running', async ({ request }) => {
    const response = await request.get(`${API_BASE}/health`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('healthy');
  });

  test('should return API root information', async ({ request }) => {
    const response = await request.get(`${API_BASE}/`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.name).toContain('IA Modules Showcase API');
  });

  test('should have pipelines endpoint accessible', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('should return 404 for non-existent pipeline', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines/non-existent-id`);
    expect(response.ok()).toBeFalsy();
    expect(response.status()).toBe(404);
  });

  test('should handle validation errors', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/pipelines`, {
      data: { name: '' }
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
});
