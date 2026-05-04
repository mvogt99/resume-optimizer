/**
 * Agent Dashboard E2E tests.
 *
 * Tests: dashboard loads, sub-tabs present, scout search form, pipeline view,
 * agent status endpoint.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';

test.describe('Agent Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'agent');
    await page.click('.tab-btn:has-text("AI Agents")');
    // Wait for agent dashboard to render
    await expect(page.locator('h2:has-text("AI Career Agents")')).toBeVisible({ timeout: 10000 });
  });

  test('agent dashboard header renders', async ({ page }) => {
    await expect(page.locator('h2:has-text("AI Career Agents")')).toBeVisible();
    await expect(page.locator('.agent-status-bar')).toBeVisible();
  });

  test('all 6 agent sub-tabs present', async ({ page }) => {
    const subTabs = ['Job Scout', 'Pipeline', 'Resume Tailor', 'Cover Letter', 'Interview Coach', 'Career Advisor'];
    for (const label of subTabs) {
      await expect(page.locator(`.agents-sub-nav button:has-text("${label}")`)).toBeVisible();
    }
  });

  test('Job Scout tab is default', async ({ page }) => {
    await expect(
      page.locator('.agents-sub-nav button:has-text("Job Scout")')
    ).toHaveClass(/active/);
  });

  test('switch to Pipeline sub-tab', async ({ page }) => {
    await page.click('.agents-sub-nav button:has-text("Pipeline")');
    await expect(
      page.locator('.agents-sub-nav button:has-text("Pipeline")')
    ).toHaveClass(/active/);
  });

  test('agent status endpoint accessible with auth', async ({ page }) => {
    // Endpoint requires auth — use token from localStorage set by registerAndLogin
    const token = await page.evaluate(() => localStorage.getItem('auth_token'));
    const response = await page.request.get('http://localhost:5000/api/agents/status', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('agents');
  });
});
