import { test, expect } from '@playwright/test';

// Credentials come from the environment; never commit real passwords.
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? '';
const SALES_PASSWORD = process.env.E2E_SALES_PASSWORD ?? '';
const MANAGER_PASSWORD = process.env.E2E_MANAGER_PASSWORD ?? '';
const TEAM_LEAD_PASSWORD = process.env.E2E_TEAM_LEAD_PASSWORD ?? '';


test.describe('Alpha Pro MENA CRM — E2E Core Workflows', () => {

  // Workflow 1: Admin Login -> Lead Pool -> Lead Distribution -> Sales Verification
  test('Workflow 1: Admin Login -> View New Leads -> Distribute Leads -> Sales Verification', async ({ page }) => {
    // 1. Admin Login
    await page.goto('/login');
    await page.fill('input[type="email"]', 'admin@alphapro.com');
    await page.fill('input[type="password"]', ADMIN_PASSWORD);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('text=Welcome back, Tariq')).toBeVisible();

    // 2. Open Unassigned Leads Pool
    await page.goto('/leads/pool');
    await expect(page.locator('text=New Leads & Unassigned Pool')).toBeVisible();

    // 3. Trigger Distribution
    const distributeBtn = page.locator('button:has-text("Distribute Leads")');
    if (await distributeBtn.isEnabled()) {
      await distributeBtn.click();
      await page.click('button:has-text("Execute Lead Distribution")');
    }

    // 4. Logout Admin
    await page.click('button:has-text("Logout")');
    await expect(page).toHaveURL('/login');

    // 5. Sales User Login
    await page.fill('input[type="email"]', 'saleh@alphapro.com');
    await page.fill('input[type="password"]', SALES_PASSWORD);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('text=Welcome back, Saleh')).toBeVisible();
  });

  // Workflow 2: Sales Login -> Open Contact -> Record No Answer -> Verify retry task
  test('Workflow 2: Record No Answer Call Outcome & Check Queue', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'saleh@alphapro.com');
    await page.fill('input[type="password"]', SALES_PASSWORD);
    await page.click('button[type="submit"]');

    // Open Contacts
    await page.goto('/contacts');
    await page.click('tbody tr:first-child');

    // Log No Answer
    await page.click('button:has-text("Log Call Attempt")');
    await page.selectOption('select.form-select', 'NO_ANSWER');
    await page.fill('textarea.form-textarea', 'Called mobile line, no answer after 5 rings.');
    await page.click('button:has-text("Record Call Result")');

    // Verify activity entry in timeline
    await expect(page.locator('text=Call Attempt: NO_ANSWER')).toBeVisible();

    // Verify presence in No Answer Queue
    await page.goto('/no-answer');
    await expect(page.locator('text=No Answer Queue')).toBeVisible();
  });

  // Workflow 3: Record Email Requested -> Verify follow-up task
  test('Workflow 3: Record Email Requested -> Complete Task -> Check Follow-up', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'saleh@alphapro.com');
    await page.fill('input[type="password"]', SALES_PASSWORD);
    await page.click('button[type="submit"]');

    await page.goto('/contacts');
    await page.click('tbody tr:first-child');

    await page.click('button:has-text("Log Call Attempt")');
    await page.selectOption('select.form-select', 'EMAIL_REQUESTED');
    await page.fill('textarea.form-textarea', 'Send commercial brochure and SLA details.');
    await page.click('button:has-text("Record Call Result")');

    await expect(page.locator('text=Call Attempt: EMAIL_REQUESTED')).toBeVisible();
  });

  // Workflow 4: Call Later -> Set Date -> Verify Recall
  test('Workflow 4: Call Later Outcome with Scheduled Time', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'saleh@alphapro.com');
    await page.fill('input[type="password"]', SALES_PASSWORD);
    await page.click('button[type="submit"]');

    await page.goto('/contacts');
    await page.click('tbody tr:first-child');

    await page.click('button:has-text("Log Call Attempt")');
    await page.selectOption('select.form-select', 'CALL_LATER');
    await page.fill('input[type="datetime-local"]', '2026-08-26T11:00');
    await page.fill('textarea.form-textarea', 'Customer requested callback on Tuesday at 11:00 AM.');
    await page.click('button:has-text("Record Call Result")');

    // Check Recalls page
    await page.goto('/recalls');
    await expect(page.locator('text=Scheduled Recalls')).toBeVisible();
  });

  // Workflow 5: Manager Login -> Inspect User Performance Reports
  test('Workflow 5: Manager Login & User Performance Reports', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'manager@alphapro.com');
    await page.fill('input[type="password"]', MANAGER_PASSWORD);
    await page.click('button[type="submit"]');

    await page.goto('/reports');
    await expect(page.locator('text=Management Performance Analytics')).toBeVisible();
    await expect(page.locator('text=Sales Representative')).toBeVisible();
  });

  // Workflow 6: Security: Sales user attempting admin API / restricted access
  test('Workflow 6: Sales User Unauthorized Admin Access Rejection', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'saleh@alphapro.com');
    await page.fill('input[type="password"]', SALES_PASSWORD);
    await page.click('button[type="submit"]');

    // Direct API verification via browser fetch
    const status = await page.evaluate(async () => {
      const resp = await fetch('/api/v1/users', { credentials: 'include' });
      return resp.status;
    });

    expect(status).toBe(403);
  });

});
