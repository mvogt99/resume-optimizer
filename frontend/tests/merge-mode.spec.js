/**
 * Multi-resume Merge mode E2E tests.
 *
 * When 2+ resumes are uploaded and the user selects "Merge" mode (vs "Compare"),
 * the wizard skips step 2.5 (ResumeRecommendation) entirely and goes directly
 * to step 3 optimization using all resume content merged for context.
 *
 * Upload flow: same two-step process as recommendation.spec.js
 *   1. Primary input (no multiple) → first resume
 *   2. "Add More Resumes" → secondary input (has multiple) → second resume
 *   3. Mode toggle appears with Compare (default) and Merge radio buttons
 *   4. Select Merge radio → click continue → step 2 (JD) → step 3 (results)
 *
 * Key assertion: step 2.5 (.recommendation-container) never appears.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';
import path from 'path';
import fs from 'fs';

const RESUME1_TEXT = `Michael Vogt - Senior Solutions Architect
15+ years enterprise architecture. AWS, Kubernetes, Python.
Skills: AWS, Kubernetes, Python, FastAPI, Docker, Terraform.
Education: Stevens Institute of Technology MEng Computer Engineering.
Summary: Experienced architect with deep cloud expertise.`;

const RESUME2_TEXT = `Michael Vogt - Additional Experience
3 years PostgreSQL DBA. Enterprise database design.
Skills: PostgreSQL, Oracle, SQL Server, database tuning.
Education: Stevens Institute of Technology MEng Computer Engineering.
Summary: Additional database expertise supplement.`;

const JOB_DESC = `Senior Solutions Architect - Cloud Platform

Requirements:
- 10+ years enterprise architecture experience
- AWS and Kubernetes expertise
- Python automation and APIs
- PostgreSQL database design
- Infrastructure as Code with Terraform
- Microservices and enterprise integration`;

test.describe('Merge Mode (Multi-Resume)', () => {
  let resume1Path, resume2Path;

  test.beforeAll(async () => {
    const ts = Date.now();
    resume1Path = path.join('/tmp', `merge_r1_${ts}.txt`);
    resume2Path = path.join('/tmp', `merge_r2_${ts}.txt`);
    fs.writeFileSync(resume1Path, RESUME1_TEXT);
    fs.writeFileSync(resume2Path, RESUME2_TEXT);
  });

  test.afterAll(async () => {
    [resume1Path, resume2Path].forEach(p => { if (p && fs.existsSync(p)) fs.unlinkSync(p); });
  });

  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'merge');
  });

  async function uploadTwoResumes(page) {
    const primaryInput = page.locator('input[type="file"]:not([multiple])');
    await primaryInput.setInputFiles(resume1Path);
    await expect(page.locator('.btn-add-more')).toBeVisible({ timeout: 5000 });
    await page.locator('.btn-add-more').click();
    const multiInput = page.locator('input[type="file"][multiple]');
    await multiInput.setInputFiles(resume2Path);
    await expect(page.locator('.mode-toggle-section')).toBeVisible({ timeout: 5000 });
  }

  test('mode toggle shows Compare and Merge options', async ({ page }) => {
    await uploadTwoResumes(page);

    const radios = page.locator('.mode-toggle-section input[type="radio"]');
    await expect(radios).toHaveCount(2);

    // Compare is default
    await expect(page.locator('input[type="radio"][value="compare"]')).toBeChecked();
    await expect(page.locator('input[type="radio"][value="merge"]')).not.toBeChecked();
  });

  test('selecting Merge mode unchecks Compare', async ({ page }) => {
    await uploadTwoResumes(page);

    await page.click('input[type="radio"][value="merge"]');
    await expect(page.locator('input[type="radio"][value="merge"]')).toBeChecked();
    await expect(page.locator('input[type="radio"][value="compare"]')).not.toBeChecked();
  });

  test('Merge mode skips step 2.5 and goes directly to step 3', async ({ page }) => {
    test.setTimeout(90000);
    await uploadTwoResumes(page);

    // Switch to Merge
    await page.click('input[type="radio"][value="merge"]');

    // Advance to step 2
    await page.click('.btn-next');
    await expect(page.locator('.job-description-input')).toBeVisible({ timeout: 5000 });

    await page.fill('textarea', JOB_DESC);
    await expect(page.locator('.btn-primary')).toBeEnabled();
    await page.click('.btn-primary');

    // Step 2.5 (recommendation-container loading) should NOT appear
    // Step 3 score rings should appear directly
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 60000 });

    // Confirm we did NOT pass through step 2.5 (no ranking cards)
    await expect(page.locator('.ranking-card')).toHaveCount(0);
  });

  test('Merge mode optimization produces a valid ATS score', async ({ page }) => {
    test.setTimeout(90000);
    await uploadTwoResumes(page);

    await page.click('input[type="radio"][value="merge"]');
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 60000 });

    const scoreText = await page.locator('.score-ring-svg text').first().textContent();
    const score = parseInt(scoreText);
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);
  });
});
