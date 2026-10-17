import { test, expect } from '@playwright/test';
import path from 'path';

const SCREENSHOT_DIR = path.resolve(import.meta.dirname, '../../docs/screenshots');

test.describe('MuleTrace End-to-End Suite', () => {
  test('1. Investigation Workspace in recorded mode satisfies all acceptance rules', async ({ page }) => {
    // Navigate directly to workspace with recorded run
    await page.goto('/workspace?session_id=demo_ravi_run&mode=replay');

    // Wait for header and victim info
    await expect(page.locator('text=Victim: Ravi Kumar')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=ACC_0461')).toBeVisible();

    // Verify Safety Disclaimer is prominently visible
    await expect(page.locator('text=Recommendation for human review. Nothing was frozen.')).toBeVisible();

    // Verify VerifiedBadge is present
    await expect(page.locator('text=Verified Against Graph')).toBeVisible();

    // Verify Timeline panel has steps
    await expect(page.locator('text=Agent Activity')).toBeVisible();
    await expect(page.locator('text=MCP Tool Belt')).toBeVisible();

    // Verify Freeze List has ranked items
    await expect(page.locator('text=Stolen Funds Recovery Split')).toBeVisible();
    await expect(page.locator('text=#1')).toBeVisible();

    // Switch to Cleared Tab and verify Decoy Account
    const clearedTab = page.locator('button[role="tab"]').filter({ hasText: 'Cleared' });
    await expect(clearedTab).toBeVisible();
    await clearedTab.click();

    await expect(page.locator('text=Cleared Legitimate Decoy')).toBeVisible();
    await expect(page.locator('text=CLEARED')).toBeVisible();
    await expect(page.locator('text=Exclusion Reason')).toBeVisible();

    // Switch to Linked Rings Tab
    const ringsTab = page.locator('button[role="tab"]').filter({ hasText: 'Rings' });
    await ringsTab.click();
    await expect(page.locator('text=LINK')).toBeVisible();
  });

  test('2. Keyboard shortcuts and command palette work seamlessly', async ({ page }) => {
    await page.goto('/workspace');
    await expect(page.locator('text=MuleTrace')).toBeVisible();

    // Open Command Palette via TopBar button
    const cmdBtn = page.locator('button').filter({ hasText: 'Quick actions' });
    if (await cmdBtn.isVisible()) {
      await cmdBtn.click();
    } else {
      await page.keyboard.press('Control+k');
    }

    await expect(page.locator('text=Type a command or jump to page...')).toBeVisible();

    // Press Escape to close Command Palette
    await page.keyboard.press('Escape');
    await expect(page.locator('text=Type a command or jump to page...')).not.toBeVisible();

    // Press P to toggle Presenter Mode
    await page.keyboard.press('p');
    await expect(page.locator('text=Exit Presenter Mode (P)')).toBeVisible();

    // Press P again to exit Presenter Mode
    await page.keyboard.press('p');
    await expect(page.locator('text=Exit Presenter Mode (P)')).not.toBeVisible();
  });

  test('3. Responsive snapshots across required breakpoints', async ({ page }) => {
    const viewports = [
      { width: 1440, height: 900, name: 'workspace-1440x900' },
      { width: 1366, height: 768, name: 'workspace-1366x768' },
      { width: 1024, height: 768, name: 'workspace-1024x768' },
      { width: 390, height: 844, name: 'workspace-390x844' },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/workspace?session_id=demo_ravi_run&mode=replay');
      await page.waitForTimeout(1000);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${vp.name}.png`),
        fullPage: false,
      });
    }
  });

  test('4. Dark and Light screenshots of every page', async ({ page }) => {
    const pages = [
      { url: '/', name: 'landing' },
      { url: '/workspace?session_id=demo_ravi_run&mode=replay', name: 'workspace' },
      { url: '/cases', name: 'cases' },
      { url: '/memory', name: 'memory' },
      { url: '/tools', name: 'tools' },
      { url: '/how-it-works', name: 'how-it-works' },
    ];

    await page.setViewportSize({ width: 1440, height: 900 });

    for (const p of pages) {
      // Dark Theme Snapshot
      await page.goto(p.url);
      await page.evaluate(() => {
        document.documentElement.classList.add('dark');
        document.documentElement.classList.remove('light');
      });
      await page.waitForTimeout(800);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${p.name}-dark.png`),
        fullPage: p.name === 'landing' || p.name === 'how-it-works',
      });

      // Light Theme Snapshot
      await page.evaluate(() => {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
      });
      await page.waitForTimeout(800);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${p.name}-light.png`),
        fullPage: p.name === 'landing' || p.name === 'how-it-works',
      });
    }
  });
});
