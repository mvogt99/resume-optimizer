/**
 * Visual regression screenshot tests.
 *
 * 6 tests capturing baseline screenshots of key pages/components.
 * Uses Playwright's toHaveScreenshot() for pixel-level comparison.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin, clearAuthAndGoToLogin } from './helpers.js';

test.describe('Visual Regression', () => {
  test('login page', async ({ page }) => {
    await clearAuthAndGoToLogin(page);
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page).toHaveScreenshot('login-page.png', {
      maxDiffPixels: 200,
    });
  });

  test('dashboard step 1', async ({ page }) => {
    await registerAndLogin(page, 'vis');
    await expect(page.locator('.dashboard-content')).toBeVisible();
    await expect(page.locator('.dashboard-content')).toHaveScreenshot('dashboard-step1.png', {
      maxDiffPixels: 200,
    });
  });

  test('tab bar with all tabs', async ({ page }) => {
    await registerAndLogin(page, 'vis');
    const tabBar = page.locator('.tab-navigation, .tab-bar, .tabs');
    const tabBtns = page.locator('.tab-btn');
    await expect(tabBtns.first()).toBeVisible();
    // Screenshot the tab button area
    await expect(tabBtns.first().locator('..')).toHaveScreenshot('tab-bar.png', {
      maxDiffPixels: 200,
    });
  });

  test('AI Agents tab', async ({ page }) => {
    await registerAndLogin(page, 'vis');
    await page.click('.tab-btn:has-text("AI Agents")');
    await expect(page.locator('.tab-btn:has-text("AI Agents")')).toHaveClass(/active/);
    // Wait for content to render
    await page.waitForTimeout(500);
    await expect(page.locator('.dashboard-content')).toHaveScreenshot('agents-tab.png', {
      maxDiffPixels: 200,
    });
  });

  test('Experience Interview tab', async ({ page }) => {
    await registerAndLogin(page, 'vis');
    await page.click('.tab-btn:has-text("Experience Interview")');
    await expect(page.locator('.tab-btn:has-text("Experience Interview")')).toHaveClass(/active/);
    await page.waitForTimeout(500);
    await expect(page.locator('.dashboard-content')).toHaveScreenshot('experience-tab.png', {
      maxDiffPixels: 200,
    });
  });

  test('Campaigns tab', async ({ page }) => {
    await registerAndLogin(page, 'vis');
    await page.click('.tab-btn:has-text("Campaigns")');
    await expect(page.locator('.tab-btn:has-text("Campaigns")')).toHaveClass(/active/);
    await page.waitForTimeout(500);
    await expect(page.locator('.dashboard-content')).toHaveScreenshot('campaigns-tab.png', {
      maxDiffPixels: 200,
    });
  });
});
