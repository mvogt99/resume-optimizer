/**
 * LinkedIn import flow E2E tests.
 *
 * Covers:
 * 1. "Import from LinkedIn" button visible in step 1
 * 2. Clicking it creates a resume from the pre-cached profile and advances to step 2
 * 3. Job description can be entered after LinkedIn import → step 3 optimization
 *
 * The backend auto-loads the LinkedIn profile on startup (linkedin_profile_merged_api_preferred.json),
 * so POST /api/resume/from-linkedin works without any file upload.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';

const JOB_DESC = `Senior Solutions Architect - Enterprise Cloud

Requirements:
- 10+ years enterprise architecture experience
- AWS and Kubernetes expertise
- Python and FastAPI development
- Enterprise integration patterns and microservices
- Infrastructure as Code with Terraform
- Strong communication and leadership`;

test.describe('LinkedIn Import Flow', () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'li');
  });

  test('import from LinkedIn button is visible in step 1', async ({ page }) => {
    await expect(page.locator('.btn-linkedin')).toBeVisible();
    // Button text should indicate import from LinkedIn
    const btnText = await page.locator('.btn-linkedin').textContent();
    expect(btnText.toLowerCase()).toContain('linkedin');
  });

  test('import from LinkedIn creates resume and advances to step 2', async ({ page }) => {
    await page.click('.btn-linkedin');

    // Step 2 (job description) should appear after LinkedIn import
    await expect(page.locator('.job-description-input')).toBeVisible({ timeout: 15000 });

    // Step indicator should show step 2 active
    const steps = page.locator('.step-indicator .step');
    await expect(steps.nth(1)).toHaveClass(/active/);
  });

  test('LinkedIn import → job description → optimization completes', async ({ page }) => {
    test.setTimeout(60000);

    await page.click('.btn-linkedin');
    await expect(page.locator('.job-description-input')).toBeVisible({ timeout: 15000 });

    await page.fill('textarea', JOB_DESC);
    await expect(page.locator('.btn-primary')).toBeEnabled();
    await page.click('.btn-primary');

    // Step 3: score rings appear
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Score is numeric
    const scoreText = await page.locator('.score-ring-svg text').first().textContent();
    expect(parseInt(scoreText)).toBeGreaterThanOrEqual(0);
    expect(parseInt(scoreText)).toBeLessThanOrEqual(100);
  });

  test('back button from step 2 returns to step 1 after LinkedIn import', async ({ page }) => {
    await page.click('.btn-linkedin');
    await expect(page.locator('.job-description-input')).toBeVisible({ timeout: 15000 });

    await page.click('.btn-secondary');
    await expect(page.locator('.resume-upload')).toBeVisible();
  });
});
