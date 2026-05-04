/**
 * Core optimize flow E2E tests.
 *
 * Tests: resume upload, job description input, full optimization, ATS score display,
 * matching/missing keywords, start over.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';
import path from 'path';
import fs from 'fs';

const RESUME_TEXT = `Mike Vogt - Senior Software Engineer
10+ years experience in Python, AWS, Docker, Kubernetes.
Led cloud migration projects saving $2M annually.
Skills: Python, FastAPI, Flask, React, PostgreSQL, Redis, Docker, AWS, CI/CD.
Education: Stevens Institute of Technology, MEng.`;

const JOB_DESC = `Senior Software Engineer - Cloud Platform

Requirements:
- 7+ years of Python development experience
- Strong background in AWS cloud services (EC2, S3, Lambda, ECS)
- Experience with containerization (Docker, Kubernetes)
- REST API development with Flask or FastAPI
- Database design with PostgreSQL
- CI/CD pipeline development
- Infrastructure as Code (Terraform preferred)
- Experience with microservices architecture
- Strong communication and leadership skills

Nice to have:
- React or Vue.js frontend experience
- Redis caching
- Message queue systems (RabbitMQ, Kafka)`;

test.describe('Optimize Flow', () => {
  let resumePath;

  test.beforeAll(async () => {
    resumePath = path.join('/tmp', `test_resume_${Date.now()}.txt`);
    fs.writeFileSync(resumePath, RESUME_TEXT);
  });

  test.afterAll(async () => {
    if (resumePath && fs.existsSync(resumePath)) {
      fs.unlinkSync(resumePath);
    }
  });

  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'opt');
  });

  test('step 1 — upload area and import buttons visible', async ({ page }) => {
    await expect(page.locator('.resume-upload h2')).toContainText('Upload Your Resume');
    await expect(page.locator('.upload-area')).toBeVisible();
    await expect(page.locator('.btn-linkedin')).toBeVisible();
    await expect(page.locator('.btn-gdrive')).toBeVisible();

    // Step indicator shows step 1 active
    const steps = page.locator('.step-indicator .step');
    await expect(steps.first()).toHaveClass(/active/);
  });

  test('step 1 → step 2 via file upload', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(resumePath);

    await expect(page.locator('.file-name')).toBeVisible();
    await expect(page.locator('.btn-next')).toBeVisible();

    await page.click('.btn-next');
    await expect(page.locator('.job-description-input h2')).toContainText('Enter Job Description');
  });

  test('step 2 — job description textarea and validation', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');

    await expect(page.locator('textarea')).toBeVisible();
    await expect(page.locator('.char-count')).toBeVisible();

    // Button disabled with short text
    await page.fill('textarea', 'Too short');
    await expect(page.locator('.btn-primary')).toBeDisabled();

    // Back button works
    await page.click('.btn-secondary');
    await expect(page.locator('.resume-upload h2')).toContainText('Upload Your Resume');
  });

  test('full optimization flow — upload → JD → results', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');

    await page.fill('textarea', JOB_DESC);
    await expect(page.locator('.btn-primary')).toBeEnabled();
    await page.click('.btn-primary');

    // Wait for optimization to complete (multiple score rings appear)
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Score ring should have a percentage
    const scoreText = await page.locator('.score-ring-svg text').first().textContent();
    const score = parseInt(scoreText);
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);
  });

  test('optimization results show score and content', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Page should contain keyword or score related content
    const pageText = await page.textContent('.dashboard-content');
    expect(
      pageText.toLowerCase().includes('keyword') ||
      pageText.toLowerCase().includes('match') ||
      pageText.toLowerCase().includes('score') ||
      pageText.toLowerCase().includes('relevance')
    ).toBe(true);
  });

  test('start over resets to step 1', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    await page.click('text=Optimize Another Resume');
    await expect(page.locator('.resume-upload h2')).toContainText('Upload Your Resume');
  });

  test('all 4 score rings render', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    const rings = page.locator('.score-ring-svg');
    const count = await rings.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('score ring labels present', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Each score-ring-wrapper should contain a label
    const ringContainers = page.locator('.score-ring-wrapper');
    const count = await ringContainers.count();
    expect(count).toBeGreaterThanOrEqual(4);
    for (let i = 0; i < Math.min(count, 4); i++) {
      const text = await ringContainers.nth(i).textContent();
      expect(text.length).toBeGreaterThan(0);
    }
  });

  test('all ring values are numeric', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    const svgTexts = page.locator('.score-ring-svg text');
    const count = await svgTexts.count();
    for (let i = 0; i < count; i++) {
      const text = await svgTexts.nth(i).textContent();
      expect(text).toMatch(/\d+/);
    }
  });
});
