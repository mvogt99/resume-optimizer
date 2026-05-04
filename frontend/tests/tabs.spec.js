/**
 * Tab navigation E2E tests.
 *
 * Covers all 19 tabs across 6 groups. Verifies each tab renders without
 * crashing and sets its button to active. Does not test tab content depth —
 * content tests live in feature-specific specs.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';

// All tabs from Dashboard.jsx tabGroups, in definition order.
const ALL_TABS = [
  // Resume group
  { label: 'Optimize Resume', group: 'Resume' },
  { label: 'Build from Scratch', group: 'Resume' },
  { label: 'Resume Builder', group: 'Resume' },
  { label: 'Version Diff', group: 'Resume' },
  { label: 'Templates', group: 'Resume' },
  // Knowledge group
  { label: 'Client Projects', group: 'Knowledge' },
  { label: 'AI Journey', group: 'Knowledge' },
  { label: 'Deep Analysis', group: 'Knowledge' },
  { label: 'Google Drive', group: 'Knowledge' },
  // Marketing group
  { label: 'Campaigns', group: 'Marketing' },
  { label: 'Campaign Analytics', group: 'Marketing' },
  { label: 'LinkedIn Update', group: 'Marketing' },
  { label: 'Portfolio', group: 'Marketing' },
  // Job Search group
  { label: 'AI Agents', group: 'Job Search' },
  { label: 'Experience Interview', group: 'Job Search' },
  { label: 'Cover Letter', group: 'Job Search' },
  // Interview group
  { label: 'Interview Coach', group: 'Interview' },
  { label: 'Recommendations', group: 'Interview' },
  // Analytics group
  { label: 'Analytics', group: 'Analytics' },
];

test.describe('Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'tabs');
  });

  test('all 19 tabs are present', async ({ page }) => {
    for (const { label } of ALL_TABS) {
      await expect(page.getByRole('button', { name: label, exact: true })).toBeVisible();
    }
  });

  test('tab groups render with group labels', async ({ page }) => {
    const groups = ['Resume', 'Knowledge', 'Marketing', 'Job Search', 'Interview', 'Analytics'];
    for (const group of groups) {
      await expect(page.locator(`.tab-group-label:has-text("${group}")`)).toBeVisible();
    }
  });

  test('optimize tab active by default', async ({ page }) => {
    await expect(page.locator('.tab-btn:has-text("Optimize Resume")')).toHaveClass(/active/);
    await expect(page.locator('.step-indicator')).toBeVisible();
  });

  // Test each non-default tab: click → button becomes active → no crash
  for (const { label } of ALL_TABS.filter(t => t.label !== 'Optimize Resume')) {
    test(`click "${label}" tab — renders without crash`, async ({ page }) => {
      const btn = page.getByRole('button', { name: label, exact: true });
      await btn.click();
      await expect(btn).toHaveClass(/active/);
      // Dashboard content area still present (no white screen / crash)
      await expect(page.locator('.dashboard-content')).toBeVisible();
    });
  }

  test('AI Agents tab renders agent dashboard header', async ({ page }) => {
    await page.click('.tab-btn:has-text("AI Agents")');
    await expect(page.locator('h2:has-text("AI Career Agents")')).toBeVisible({ timeout: 5000 });
  });

  test('tab switching back to Optimize preserves step indicator', async ({ page }) => {
    await page.click('.tab-btn:has-text("AI Agents")');
    await page.click('.tab-btn:has-text("Optimize Resume")');
    await expect(page.locator('.tab-btn:has-text("Optimize Resume")')).toHaveClass(/active/);
    await expect(page.locator('.step-indicator')).toBeVisible();
  });
});
