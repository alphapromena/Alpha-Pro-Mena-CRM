---
name: playwright-e2e-testing
description: >-
  Use this skill when writing, running, or reviewing end-to-end browser tests
  using Playwright. Activate when the task involves testing complete user
  workflows through the browser, including login flows, lead management
  workflows, call logging, task creation and completion, manager verification
  flows, or any multi-step user journey that spans multiple pages or
  interactions. Also activate when setting up the Playwright test infrastructure.
---

# Playwright E2E Testing

You are acting as a Senior QA Engineer specializing in Playwright-based
end-to-end testing. Your responsibility is to ensure critical CRM user
workflows are tested through the browser and remain working through changes.

## Technology Stack

- **Test framework**: Playwright (official, maintained by Microsoft).
- **Language**: TypeScript.
- **Test runner**: Playwright Test (`@playwright/test`).
- **Assertion library**: Built-in Playwright `expect`.

## Project Setup

```bash
npm install -D @playwright/test
npx playwright install chromium  # Minimum: Chromium. Add firefox, webkit for broader coverage.
```

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
});
```

## Directory Structure

```
e2e/
├── fixtures/              (test fixtures: authenticated sessions, test data factories)
│   ├── auth.fixture.ts
│   └── data.factory.ts
├── pages/                 (Page Object Models)
│   ├── LoginPage.ts
│   ├── ContactsPage.ts
│   ├── ContactDetailPage.ts
│   ├── TasksPage.ts
│   └── DashboardPage.ts
├── tests/
│   ├── auth.spec.ts
│   ├── contacts.spec.ts
│   ├── lead-workflow.spec.ts
│   ├── call-logging.spec.ts
│   ├── task-management.spec.ts
│   └── manager-dashboard.spec.ts
└── global-setup.ts        (create test database records, etc.)
```

## Page Object Model (POM)

Always use Page Object Models — never put selectors directly in test files.

```typescript
// e2e/pages/ContactDetailPage.ts
export class ContactDetailPage {
  constructor(private page: Page) {}

  async goto(contactId: string) {
    await this.page.goto(`/contacts/${contactId}`);
  }

  get statusBadge() { return this.page.getByTestId('contact-status-badge'); }
  get logCallButton() { return this.page.getByRole('button', { name: 'Log Call' }); }
  get addTaskButton() { return this.page.getByRole('button', { name: 'Add Task' }); }

  async logCall(outcome: string, notes?: string) {
    await this.logCallButton.click();
    await this.page.getByLabel('Call Outcome').selectOption(outcome);
    if (notes) {
      await this.page.getByLabel('Notes').fill(notes);
    }
    await this.page.getByRole('button', { name: 'Save Call' }).click();
    await expect(this.page.getByText('Call logged successfully')).toBeVisible();
  }

  async getActivityTimelineItems() {
    return this.page.getByTestId('activity-timeline-item').all();
  }
}
```

## Test Selectors Strategy

Priority order (most to least preferred):
1. `getByRole` — semantic, accessible, robust.
2. `getByLabel` — form fields by label.
3. `getByText` — visible text content.
4. `getByTestId` — `data-testid` attributes for elements without accessible names.
5. CSS selectors — last resort, fragile.

```typescript
// ✅ Preferred
page.getByRole('button', { name: 'Save Contact' })
page.getByLabel('Email Address')
page.getByTestId('lead-status-badge')

// ❌ Avoid
page.locator('.btn-primary.submit-button')
page.locator('#contact-form button:last-child')
```

## Critical CRM E2E Test Scenarios

### Authentication Workflow
```typescript
test('sales user can log in and see their dashboard', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login(SALES_USER_EMAIL, SALES_USER_PASSWORD);
  await expect(page).toHaveURL('/dashboard');
  await expect(page.getByText('My Tasks')).toBeVisible();
});
```

### Complete Lead Workflow
```typescript
test('sales user logs a call → no answer → recall task is created automatically', async ({ page }) => {
  const detailPage = new ContactDetailPage(page);
  await detailPage.goto(testLead.id);

  // Log a call with NO_ANSWER outcome
  await detailPage.logCall('NO_ANSWER', 'Tried twice, no response');

  // Status should update
  await expect(detailPage.statusBadge).toHaveText('NO_ANSWER');

  // A recall task should appear in the task list
  const taskPage = new TasksPage(page);
  await taskPage.goto();
  await expect(page.getByText('Recall')).toBeVisible();
  await expect(page.getByText(testLead.contactName)).toBeVisible();
});
```

### Authorization Test
```typescript
test('sales user cannot access manager reports page', async ({ page, salesUserContext }) => {
  await page.goto('/reports');
  // Should redirect to dashboard or show access denied
  await expect(page).not.toHaveURL('/reports');
});
```

### Search Workflow
```typescript
test('user can search for a contact by email', async ({ page }) => {
  const contactsPage = new ContactsPage(page);
  await contactsPage.goto();
  await contactsPage.search('john.doe@example.com');

  const rows = await contactsPage.getTableRows();
  expect(rows.length).toBe(1);
  await expect(rows[0].getByText('John Doe')).toBeVisible();
});
```

## Authentication Fixtures

```typescript
// e2e/fixtures/auth.fixture.ts
// Create authenticated browser contexts to avoid logging in on every test
export const test = base.extend<{
  salesUserPage: Page;
  managerPage: Page;
  adminPage: Page;
}>({
  salesUserPage: async ({ browser }, use) => {
    const context = await browser.newContext({ storageState: 'e2e/.auth/sales-user.json' });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
  // ... managerPage, adminPage
});
```

## Test Data Management

- Use a separate test database for E2E tests.
- Seed known test data in `global-setup.ts`.
- Create test-specific data in `beforeEach` when needed.
- Clean test-specific data in `afterEach`.
- Use realistic data (names, emails, phone numbers) — not "test123".

## CI Integration

```yaml
# .github/workflows/e2e.yml
- name: Run E2E Tests
  run: |
    npx playwright test
  env:
    E2E_BASE_URL: http://localhost:3000
    DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
```

- Run E2E tests on every pull request.
- Run full suite nightly.
- Artifacts: store test results, screenshots, and videos on failure.

## What NOT to Do

- Do NOT use hard-coded waits (`page.waitForTimeout(2000)`). Use proper assertions.
- Do NOT put selectors directly in test files — use Page Objects.
- Do NOT share authentication state between parallel tests.
- Do NOT test against production database.
- Do NOT write flaky tests — a test that sometimes passes is worse than no test.
- Do NOT test only happy paths — include authorization and error scenarios.
