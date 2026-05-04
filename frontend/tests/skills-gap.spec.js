/**
 * Skills gap analysis E2E tests.
 *
 * After optimization completes (step 3), a "View Detailed Skills Gap Analysis"
 * button appears. Clicking it opens the SkillsGap component inline, which calls
 * GET /api/skills-gap/<resume_id> and renders:
 *   - matched skills, missing skills, endorsed skills sections
 *   - close button to dismiss
 *
 * Selectors:
 *   .btn-skills-gap    — trigger button (step 3, optimize tab)
 *   .skills-gap        — container when open
 *   .skills-gap-header — header with close button
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';
import path from 'path';
import fs from 'fs';

const RESUME_TEXT = `Mike Vogt - Senior Solutions Architect
15+ years enterprise architecture. AWS, Kubernetes, Python, enterprise integration.
Led cloud migrations saving $5M. Designed microservices for Fortune 500 clients.
Skills: AWS, Kubernetes, Python, FastAPI, enterprise integration, Docker, Terraform, PostgreSQL.
Education: Stevens Institute of Technology MEng Computer Engineering.
Summary: Experienced architect with deep cloud and integration expertise.`;

const JOB_DESC = `Senior Solutions Architect - Cloud Platform

Requirements:
- 10+ years enterprise architecture experience
- Deep expertise in AWS (EC2, S3, Lambda, EKS)
- Kubernetes and container orchestration
- Python automation and APIs
- Enterprise integration patterns
- Infrastructure as Code (Terraform)
- Microservices design

Nice to have: PostgreSQL, Docker, FastAPI`;

test.describe('Skills Gap Analysis', () => {
  let resumePath;

  test.beforeAll(async () => {
    resumePath = path.join('/tmp', `sg_resume_${Date.now()}.txt`);
    fs.writeFileSync(resumePath, RESUME_TEXT);
  });

  test.afterAll(async () => {
    if (resumePath && fs.existsSync(resumePath)) fs.unlinkSync(resumePath);
  });

  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'sg');
  });

  async function runOptimization(page) {
    await page.locator('input[type="file"]:not([multiple])').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });
  }

  test('skills gap button appears after optimization', async ({ page }) => {
    await runOptimization(page);
    await expect(page.locator('.btn-skills-gap')).toBeVisible();
    const btnText = await page.locator('.btn-skills-gap').textContent();
    expect(btnText.toLowerCase()).toContain('skills gap');
  });

  test('clicking skills gap button opens analysis panel', async ({ page }) => {
    await runOptimization(page);
    await page.click('.btn-skills-gap');

    // Skills gap panel opens
    await expect(page.locator('.skills-gap')).toBeVisible({ timeout: 15000 });
  });

  test('skills gap panel has header and close button', async ({ page }) => {
    await runOptimization(page);
    await page.click('.btn-skills-gap');
    await expect(page.locator('.skills-gap')).toBeVisible({ timeout: 15000 });

    // Header section present
    await expect(page.locator('.skills-gap-header')).toBeVisible();

    // Close button present (.btn-close is the specific close button)
    const closeBtn = page.locator('.skills-gap-header .btn-close');
    await expect(closeBtn).toBeVisible();

    // Close dismisses the panel
    await closeBtn.click();
    await expect(page.locator('.skills-gap')).not.toBeVisible({ timeout: 5000 });
    // Trigger button returns
    await expect(page.locator('.btn-skills-gap')).toBeVisible();
  });

  test('skills gap panel loads content from API', async ({ page }) => {
    test.setTimeout(60000);
    await runOptimization(page);
    await page.click('.btn-skills-gap');

    // Wait for loading to complete (loading state has specific class)
    await expect(page.locator('.skills-gap-loading')).not.toBeVisible({ timeout: 15000 });

    // Content present — the skills-gap div should have substantive text
    const content = await page.locator('.skills-gap').textContent();
    expect(content.length).toBeGreaterThan(50);
  });
});
