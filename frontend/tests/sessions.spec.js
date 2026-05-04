/**
 * Session management E2E tests.
 *
 * Tests: session created after optimization, session appears in list,
 * ATS score shown, delete session, multiple sessions.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';
import path from 'path';
import fs from 'fs';

const RESUME_TEXT = `Jane Smith - Data Engineer
8 years Python, SQL, Spark, AWS Glue, Airflow, dbt.
Built data pipelines processing 10TB daily.
Skills: Python, SQL, Apache Spark, AWS, Airflow, dbt, PostgreSQL, Redshift.`;

const JOB_DESC_1 = `Data Engineer - Analytics Platform

Requirements:
- 5+ years Python and SQL experience
- Apache Spark or PySpark for large-scale data processing
- AWS services (Glue, Redshift, S3, Lambda)
- Workflow orchestration (Airflow, Step Functions)
- Data modeling and warehouse design
- dbt for transformation layer
- Strong problem-solving skills`;

const JOB_DESC_2 = `Senior Backend Engineer - Platform Team

Requirements:
- 7+ years backend development in Python or Go
- RESTful API design and microservices architecture
- PostgreSQL and Redis experience
- Docker and Kubernetes deployment
- CI/CD pipeline design
- Monitoring and observability (Datadog, Prometheus)
- Team mentoring and code review experience`;

test.describe('Session Management', () => {
  test.setTimeout(60000); // optimization roundtrips take time
  let resumePath;

  test.beforeAll(async () => {
    resumePath = path.join('/tmp', `test_resume_sess_${Date.now()}.txt`);
    fs.writeFileSync(resumePath, RESUME_TEXT);
  });

  test.afterAll(async () => {
    if (resumePath && fs.existsSync(resumePath)) {
      fs.unlinkSync(resumePath);
    }
  });

  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'sess');
  });

  test('optimization creates a session', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_1);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Click Start Over to see session list
    await page.click('text=Optimize Another Resume');
    await expect(page.locator('.session-card')).toBeVisible({ timeout: 5000 });
  });

  test('session card shows ATS score badge', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_1);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    await page.click('text=Optimize Another Resume');
    await expect(page.locator('.session-score-badge')).toBeVisible({ timeout: 5000 });
    const badgeText = await page.locator('.session-score-badge').first().textContent();
    expect(badgeText).toMatch(/\d+%/);
  });

  test('delete session removes it from list', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_1);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    await page.click('text=Optimize Another Resume');
    await expect(page.locator('.session-card')).toBeVisible({ timeout: 5000 });

    const countBefore = await page.locator('.session-card').count();
    await page.locator('.session-card-delete').first().click();

    if (countBefore === 1) {
      await expect(page.locator('.session-card')).toHaveCount(0, { timeout: 5000 });
    } else {
      await expect(page.locator('.session-card')).toHaveCount(countBefore - 1, { timeout: 5000 });
    }
  });

  test('load session restores optimization results', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_1);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    await page.click('text=Optimize Another Resume');
    await expect(page.locator('.session-card')).toBeVisible({ timeout: 5000 });

    // Click session card to load it
    await page.locator('.session-card').first().click();
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 15000 });
  });

  test('multiple sessions appear as separate cards', async ({ page }) => {
    // Session 1
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_1);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    // Start over for session 2
    await page.click('text=Optimize Another Resume');
    await page.click('.btn-new-session');

    // Session 2
    await page.locator('input[type="file"]').setInputFiles(resumePath);
    await page.click('.btn-next');
    await page.fill('textarea', JOB_DESC_2);
    await page.click('.btn-primary');
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 30000 });

    await page.click('text=Optimize Another Resume');
    const count = await page.locator('.session-card').count();
    expect(count).toBeGreaterThanOrEqual(2);
  });
});
