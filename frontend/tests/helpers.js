/**
 * Shared test helpers for Playwright E2E tests.
 */

const PASSWORD = 'TestPass123!';

/**
 * Register a fresh user and land on dashboard with onboarding dismissed.
 * Returns on dashboard ready for interaction.
 */
async function registerAndLogin(page, prefix = 'e2e') {
  await page.goto('/login');
  // Clear any stale auth + dismiss onboarding for future navigation
  await page.evaluate(() => {
    localStorage.removeItem('user_id');
    localStorage.removeItem('auth_token');
    localStorage.setItem('ro_onboarding_seen', '1');
  });
  await page.goto('/login');

  await page.locator('.toggle-form span').click();
  const email = `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}@test.com`;
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', PASSWORD);
  await page.fill('input[name="confirmPassword"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
  return email;
}

/**
 * Clear auth state and go to login page.
 */
async function clearAuthAndGoToLogin(page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.removeItem('user_id');
    localStorage.removeItem('auth_token');
    localStorage.setItem('ro_onboarding_seen', '1');
  });
  await page.goto('/login');
}

export { registerAndLogin, clearAuthAndGoToLogin, PASSWORD };
