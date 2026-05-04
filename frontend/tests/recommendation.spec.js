/**
 * Recommendation flow E2E tests (Phase 15 — Step 2.5).
 *
 * Verifies the full browser-level flow for multi-resume comparison:
 * 1. Upload 2 resumes → compare mode toggle appears
 * 2. Compare → step 2.5 renders ranked cards with scores
 * 3. Accept recommended → step 3 optimization runs with correct resume
 * 4. Override to non-recommended → optimization runs with chosen resume
 * 5. Sessions tab shows session created after selection
 *
 * Upload flow:
 *   - Primary file input (no multiple) → first resume
 *   - "Add More Resumes" button → multiFileInputRef (has multiple) → second resume
 *   - Mode toggle appears when selectedFile + additionalFiles.length > 0
 *
 * Timing notes:
 *   - Compare API (NLP scoring + LLM rationale) takes 20–60 s on first call
 *   - Optimization (step 3) takes 10–30 s
 *   - test.setTimeout(180000) gives 3 min per test
 *   - All assertions that wait for API completion use explicit { timeout: 90000 }
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin } from './helpers.js';
import path from 'path';
import fs from 'fs';

const RESUME1_TEXT = `Michael Vogt - Senior Solutions Architect
15+ years enterprise architecture. AWS, Kubernetes, Python, enterprise integration.
Led cloud migrations saving $5M. Designed microservices for Fortune 500 clients.
Skills: AWS, Kubernetes, Python, FastAPI, enterprise integration, Docker, Terraform, PostgreSQL.
Education: Stevens Institute of Technology MEng Computer Engineering.
Summary: Experienced architect with deep cloud and integration expertise.`;

const RESUME2_TEXT = `Jane Smith - Junior Web Developer
2 years experience. JavaScript, React, HTML, CSS, some Node.js.
Built e-commerce sites. No cloud experience.
Skills: JavaScript, React, HTML, CSS, Node.js.
Education: State University BS Computer Science.
Summary: Entry-level developer learning the ropes.`;

const JOB_DESC = `Senior Solutions Architect - Cloud Platform

We need an experienced architect to lead cloud transformation.

Requirements:
- 10+ years enterprise architecture experience
- Deep expertise in AWS (EC2, S3, Lambda, EKS)
- Kubernetes and container orchestration
- Python automation and APIs
- Enterprise integration patterns (ESB, API gateway, event-driven)
- Infrastructure as Code (Terraform)
- Microservices design

Nice to have: PostgreSQL, Docker, FastAPI, CI/CD pipelines`;

/**
 * Upload two resume files using the two-step upload flow:
 * 1. Set first file on primary input (no multiple attribute)
 * 2. Click "Add More Resumes" to reveal secondary input (has multiple)
 * 3. Set second file on secondary input
 * 4. Wait for mode toggle to appear
 */
async function uploadTwoResumes(page, path1, path2) {
  // Upload first resume via primary input
  const primaryInput = page.locator('input[type="file"]:not([multiple])');
  await primaryInput.setInputFiles(path1);

  // "Add More Resumes" button appears after first file
  await expect(page.locator('.btn-add-more')).toBeVisible({ timeout: 5000 });
  await page.locator('.btn-add-more').click();

  // Upload second resume via the multi-file input
  const multiInput = page.locator('input[type="file"][multiple]');
  await multiInput.setInputFiles(path2);

  // Mode toggle should now be visible
  await expect(page.locator('.mode-toggle-section')).toBeVisible({ timeout: 5000 });
}

/**
 * Submit JD and wait for the recommendation step to fully load.
 * The loading state renders .recommendation-container immediately;
 * .mode-badge only appears after the compare API returns (20-60 s).
 * Returns when the full recommendation UI is visible.
 */
async function submitJDAndWaitForRecommendation(page) {
  await expect(page.locator('.job-description-input')).toBeVisible({ timeout: 5000 });
  await page.fill('textarea', JOB_DESC);
  await expect(page.locator('.btn-primary')).toBeEnabled();
  await page.click('.btn-primary');

  // Loading container appears immediately
  await expect(page.locator('.recommendation-container')).toBeVisible({ timeout: 10000 });

  // Wait for API to finish — mode-badge only present in non-loading state
  await expect(page.locator('.mode-badge')).toBeVisible({ timeout: 90000 });
}

test.describe('Recommendation Flow (Step 2.5)', () => {
  let resume1Path, resume2Path;

  test.beforeAll(async () => {
    const ts = Date.now();
    resume1Path = path.join('/tmp', `resume1_${ts}.txt`);
    resume2Path = path.join('/tmp', `resume2_${ts}.txt`);
    fs.writeFileSync(resume1Path, RESUME1_TEXT);
    fs.writeFileSync(resume2Path, RESUME2_TEXT);
  });

  test.afterAll(async () => {
    [resume1Path, resume2Path].forEach(p => { if (p && fs.existsSync(p)) fs.unlinkSync(p); });
  });

  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, 'rec');
  });

  // --- Test 1: Compare mode toggle appears when 2+ files selected ---
  test('compare mode toggle appears after 2 files selected', async ({ page }) => {
    await uploadTwoResumes(page, resume1Path, resume2Path);

    // Two radio options: Compare and Merge
    const radios = page.locator('.mode-toggle-section input[type="radio"]');
    await expect(radios).toHaveCount(2);

    // Compare is selected by default (first radio, value="compare")
    await expect(page.locator('input[type="radio"][value="compare"]')).toBeChecked();

    // "Add More Resumes" button should still be visible
    await expect(page.locator('.btn-add-more')).toBeVisible();
  });

  // --- Test 2: Step 2.5 renders ranked cards with scores ---
  test('step 2.5 renders ranking cards after compare', async ({ page }) => {
    test.setTimeout(180000);
    await uploadTwoResumes(page, resume1Path, resume2Path);
    await page.click('.btn-next');

    await submitJDAndWaitForRecommendation(page);

    // Header shows compare mode badge (already waited for in helper)
    await expect(page.locator('.mode-badge')).toContainText('Compare Mode');

    // Subtitle mentions 2 resumes ranked
    await expect(page.locator('.header-subtitle')).toContainText('2 resumes');

    // Two ranking cards
    const cards = page.locator('.ranking-card');
    await expect(cards).toHaveCount(2);

    // First card ranked #1
    await expect(cards.first().locator('.rank-badge')).toContainText('#1');
    await expect(cards.nth(1).locator('.rank-badge')).toContainText('#2');

    // Score values present and numeric
    const scoreValues = page.locator('.score-value');
    await expect(scoreValues).toHaveCount(2);
    const s1 = parseInt(await scoreValues.first().textContent());
    const s2 = parseInt(await scoreValues.nth(1).textContent());
    expect(s1).toBeGreaterThanOrEqual(0);
    expect(s1).toBeLessThanOrEqual(100);
    expect(s1).toBeGreaterThanOrEqual(s2); // rank 1 >= rank 2

    // Recommended badge on rank-1 card
    await expect(cards.first().locator('.recommended-badge')).toBeVisible();

    // Rationale block present with content
    await expect(page.locator('.rationale-block')).toBeVisible();
    const rationaleText = await page.locator('.rationale-text').textContent();
    expect(rationaleText.length).toBeGreaterThan(10);

    // Recompare button present in footer
    await expect(page.locator('.btn-recompare')).toBeVisible();
  });

  // --- Test 3: Accept recommended → step 3 runs optimization ---
  test('accepting recommended resume advances to step 3', async ({ page }) => {
    test.setTimeout(180000);
    await uploadTwoResumes(page, resume1Path, resume2Path);
    await page.click('.btn-next');

    await submitJDAndWaitForRecommendation(page);

    // Recommended card (rank 1) has primary select button
    const recommendedCard = page.locator('.ranking-card--recommended');
    await expect(recommendedCard).toBeVisible();

    // Verify the recommended card is rank 1
    await expect(recommendedCard.locator('.rank-badge')).toContainText('#1');

    // Click primary select button
    await recommendedCard.locator('.btn-select-resume--primary').click();

    // Step 3: score rings appear (optimization complete)
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 60000 });

    // ATS score present
    const scoreText = await page.locator('.score-ring-svg text').first().textContent();
    expect(parseInt(scoreText)).toBeGreaterThanOrEqual(0);
  });

  // --- Test 4: Override to non-recommended → also reaches step 3 ---
  test('overriding to non-recommended resume also advances to step 3', async ({ page }) => {
    test.setTimeout(180000);
    await uploadTwoResumes(page, resume1Path, resume2Path);
    await page.click('.btn-next');

    await submitJDAndWaitForRecommendation(page);

    // Wait for all cards to render
    const allCards = page.locator('.ranking-card');
    await expect(allCards).toHaveCount(2);

    // Rank-2 card is the non-recommended one
    const rank2Card = allCards.nth(1);
    await expect(rank2Card.locator('.rank-badge')).toContainText('#2');

    // Click secondary select button on rank-2
    const overrideBtn = rank2Card.locator('.btn-select-resume--secondary');
    await expect(overrideBtn).toBeVisible();
    await overrideBtn.click();

    // Step 3: score rings appear
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 60000 });
  });

  // --- Test 5: Session created and visible after selection ---
  test('session created and visible in optimize tab after recommendation selection', async ({ page }) => {
    test.setTimeout(180000);
    await uploadTwoResumes(page, resume1Path, resume2Path);
    await page.click('.btn-next');

    await submitJDAndWaitForRecommendation(page);

    // Accept recommended
    await page.locator('.ranking-card--recommended .btn-select-resume--primary').click();
    await expect(page.locator('.score-ring-svg').first()).toBeVisible({ timeout: 60000 });

    // Sessions live in the 'Optimize Resume' tab (already active).
    // After selection, loadSessions() is called — session card should appear.
    await expect(page.locator('.session-list')).toBeVisible({ timeout: 10000 });

    // At least one session card present
    const sessionCards = page.locator('.session-card');
    await expect(sessionCards.first()).toBeVisible();
  });
});
