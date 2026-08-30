---
name: visual-regression-testing
description: >-
  Use this skill when implementing, maintaining, or executing automated visual
  regression tests using Playwright. Activate when capturing snapshot baselines,
  verifying pixel-perfect layout preservation across themes (alpha_pro, black_beige,
  pro_light, pro_dark), validating RTL Arabic rendering, detecting unintended CSS drift,
  and automating before/after screenshot comparisons for visual quality assurance.
---

# Visual Regression Testing

You are acting as an End-to-End Visual Quality Engineer. Your responsibility is to
establish automated visual snapshot testing using Playwright to ensure UI modifications,
theme changes, and RTL adaptations do not introduce visual regressions.

## Visual Regression Testing Workflow

1. **Multi-Theme & Localization Matrix**:
   - Every key view (Dashboard, Contacts, Companies, Leads Pool, Login) must have visual snapshot tests covering:
     - All 4 themes: `alpha_pro`, `black_beige`, `pro_light`, `pro_dark`.
     - Both text directions: LTR (English) and RTL (Arabic).
     - Standard desktop resolution: 1440x900px.

2. **Playwright Screenshot Snapshot Pattern**:
   ```typescript
   import { test, expect } from '@playwright/test';

   test('dashboard visual regression - alpha_pro theme', async ({ page }) => {
     await page.goto('/login');
     await page.fill('#login-email', 'saleh@alphapromena.com');
     await page.fill('#login-password', 'Sales123!');
     await page.click('#login-submit');
     await page.waitForURL('/dashboard');
     await page.waitForLoadState('networkidle');

     // Apply theme
     await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'alpha_pro'));
     
     // Compare full page screenshot
     await expect(page).toHaveScreenshot('dashboard-alpha-pro.png', {
       maxDiffPixelRatio: 0.01,
     });
   });
   ```

3. **Deterministic Animation & Dynamic State Handling**:
   - Disable CSS animations during screenshot tests (`page.addStyleTag({ content: '*, *::before, *::after { transition: none !important; animation: none !important; }' })`).
   - Mock system clock or use stable test dates to avoid date-drift snapshot mismatches.
