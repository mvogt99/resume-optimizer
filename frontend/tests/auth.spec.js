/**
 * Auth + Navigation E2E tests.
 *
 * Tests: login page render, register, login, invalid creds error, logout,
 * protected route redirect.
 */

import { test, expect } from '@playwright/test';
import { clearAuthAndGoToLogin, PASSWORD } from './helpers.js';

const EMAIL = `pw_auth_${Date.now()}@test.com`;

test.describe('Auth — Login & Registration', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuthAndGoToLogin(page);
  });

  test('login page renders with form fields', async ({ page }) => {
    await expect(page.locator('.login-box h1')).toHaveText('Resume Optimizer');
    await expect(page.locator('.login-box h2')).toHaveText('Sign In');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Login');
  });

  test('toggle to register mode shows confirm password', async ({ page }) => {
    await page.locator('.toggle-form span').click();
    await expect(page.locator('.login-box h2')).toHaveText('Create Account');
    await expect(page.locator('input[name="confirmPassword"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Register');
  });

  test('register new user and redirect to dashboard', async ({ page }) => {
    await page.locator('.toggle-form span').click();
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.fill('input[name="confirmPassword"]', PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await expect(page.locator('.dashboard-header h1')).toHaveText('Resume Optimizer');
  });

  test('login with registered user', async ({ page }) => {
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await expect(page.locator('.dashboard-header h1')).toHaveText('Resume Optimizer');
  });

  test('invalid credentials show error', async ({ page }) => {
    await page.fill('input[name="email"]', 'nobody@nowhere.com');
    await page.fill('input[name="password"]', 'wrongpass');
    await page.click('button[type="submit"]');

    await expect(page.locator('.error-message')).toBeVisible({ timeout: 5000 });
    expect(page.url()).toContain('/login');
  });

  test('password mismatch on register shows error', async ({ page }) => {
    await page.locator('.toggle-form span').click();
    await page.fill('input[name="email"]', `mismatch_${Date.now()}@test.com`);
    await page.fill('input[name="password"]', 'Password1');
    await page.fill('input[name="confirmPassword"]', 'Different2');
    await page.click('button[type="submit"]');

    await expect(page.locator('.error-message')).toHaveText('Passwords do not match');
  });
});

test.describe('Auth — Protected Routes & Logout', () => {
  test('unauthenticated user redirected to login', async ({ page }) => {
    // Navigate to a page first so we can access localStorage
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.removeItem('user_id');
      localStorage.removeItem('auth_token');
    });
    await page.goto('/dashboard');
    await page.waitForURL('**/login', { timeout: 5000 });
  });

  test('authenticated user on /login redirected to dashboard', async ({ page }) => {
    await clearAuthAndGoToLogin(page);
    await page.locator('.toggle-form span').click();
    const email = `redirect_${Date.now()}@test.com`;
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', PASSWORD);
    await page.fill('input[name="confirmPassword"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Now visit /login — should redirect back to dashboard
    await page.goto('/login');
    await page.waitForURL('**/dashboard', { timeout: 5000 });
  });

  test('logout clears auth and returns to login', async ({ page }) => {
    await clearAuthAndGoToLogin(page);
    await page.locator('.toggle-form span').click();
    const email = `logout_${Date.now()}@test.com`;
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', PASSWORD);
    await page.fill('input[name="confirmPassword"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Click logout (onboarding already dismissed via helper)
    await page.click('.btn-logout');
    await page.waitForURL('**/login', { timeout: 5000 });

    const userId = await page.evaluate(() => localStorage.getItem('user_id'));
    expect(userId).toBeNull();
  });
});
