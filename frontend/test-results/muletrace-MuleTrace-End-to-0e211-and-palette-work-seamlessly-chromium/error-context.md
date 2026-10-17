# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: muletrace.spec.ts >> MuleTrace End-to-End Suite >> 2. Keyboard shortcuts and command palette work seamlessly
- Location: e2e\muletrace.spec.ts:44:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=MuleTrace')
Expected: visible
Error: strict mode violation: locator('text=MuleTrace') resolved to 2 elements:
    1) <span class="font-bold text-sm tracking-tight text-white leading-none flex items-center gap-1.5">…</span> aka getByRole('link', { name: 'MuleTrace FalkorDB Autonomous' })
    2) <span class="text-slate-400">MuleTrace</span> aka getByText('MuleTrace', { exact: true })

Call log:
  - Expect "toBeVisible" locator('text=MuleTrace') with timeout 10000ms
  - waiting for locator('text=MuleTrace')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - generic [ref=e5]:
      - generic [ref=e6]:
        - link "MuleTrace FalkorDB Autonomous Ring Tracer" [ref=e7] [cursor=pointer]:
          - /url: /
          - generic [ref=e16]:
            - generic [ref=e17]:
              - text: MuleTrace
              - generic [ref=e18]: FalkorDB
            - generic [ref=e19]: Autonomous Ring Tracer
        - button "Collapse sidebar" [ref=e20] [cursor=pointer]
      - navigation [ref=e23]:
        - link "Investigate Live" [ref=e24] [cursor=pointer]:
          - /url: /workspace
          - generic [ref=e28]:
            - generic [ref=e29]: Investigate
            - generic [ref=e30]: Live
        - link "Cases 20" [ref=e31] [cursor=pointer]:
          - /url: /cases
          - generic [ref=e35]:
            - generic [ref=e36]: Cases
            - generic [ref=e37]: "20"
        - link "Memory" [ref=e38] [cursor=pointer]:
          - /url: /memory
        - link "MCP Tools" [ref=e49] [cursor=pointer]:
          - /url: /tools
        - link "How It Works" [ref=e54] [cursor=pointer]:
          - /url: /how-it-works
    - generic [ref=e60]:
      - generic [ref=e61]:
        - generic [ref=e62]: FalkorDB
        - generic [ref=e68]: 6,669 nodes
      - generic [ref=e70]:
        - generic [ref=e71]: Groq LLM
        - generic [ref=e79]: Connected
  - generic [ref=e80]:
    - banner [ref=e81]:
      - generic [ref=e82]:
        - generic [ref=e83]: MuleTrace
        - generic [ref=e84]: /
        - generic [ref=e85]: Investigation Workspace
      - generic [ref=e86]:
        - button "Quick actions ⌘ K" [ref=e87] [cursor=pointer]:
          - generic [ref=e91]: Quick actions
          - generic [ref=e92]:
            - generic [ref=e93]: ⌘
            - generic [ref=e94]: K
        - generic [ref=e95]: Recorded Run
        - button "Enter presenter mode" [ref=e99] [cursor=pointer]
        - button "Toggle dark/light theme" [ref=e105] [cursor=pointer]
    - main [ref=e108]
  - region "Notifications alt+T"
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import path from 'path';
  3   | 
  4   | const SCREENSHOT_DIR = path.resolve(import.meta.dirname, '../../docs/screenshots');
  5   | 
  6   | test.describe('MuleTrace End-to-End Suite', () => {
  7   |   test('1. Investigation Workspace in recorded mode satisfies all acceptance rules', async ({ page }) => {
  8   |     // Navigate directly to workspace with recorded run
  9   |     await page.goto('/workspace?session_id=demo_ravi_run&mode=replay');
  10  | 
  11  |     // Wait for header and victim info
  12  |     await expect(page.locator('text=Victim: Ravi Kumar')).toBeVisible({ timeout: 15000 });
  13  |     await expect(page.locator('text=ACC_0461')).toBeVisible();
  14  | 
  15  |     // Verify Safety Disclaimer is prominently visible
  16  |     await expect(page.locator('text=Recommendation for human review. Nothing was frozen.')).toBeVisible();
  17  | 
  18  |     // Verify VerifiedBadge is present
  19  |     await expect(page.locator('text=Verified Against Graph')).toBeVisible();
  20  | 
  21  |     // Verify Timeline panel has steps
  22  |     await expect(page.locator('text=Agent Activity')).toBeVisible();
  23  |     await expect(page.locator('text=MCP Tool Belt')).toBeVisible();
  24  | 
  25  |     // Verify Freeze List has ranked items
  26  |     await expect(page.locator('text=Stolen Funds Recovery Split')).toBeVisible();
  27  |     await expect(page.locator('text=#1')).toBeVisible();
  28  | 
  29  |     // Switch to Cleared Tab and verify Decoy Account
  30  |     const clearedTab = page.locator('button[role="tab"]').filter({ hasText: 'Cleared' });
  31  |     await expect(clearedTab).toBeVisible();
  32  |     await clearedTab.click();
  33  | 
  34  |     await expect(page.locator('text=Cleared Legitimate Decoy')).toBeVisible();
  35  |     await expect(page.locator('text=CLEARED')).toBeVisible();
  36  |     await expect(page.locator('text=Exclusion Reason')).toBeVisible();
  37  | 
  38  |     // Switch to Linked Rings Tab
  39  |     const ringsTab = page.locator('button[role="tab"]').filter({ hasText: 'Rings' });
  40  |     await ringsTab.click();
  41  |     await expect(page.locator('text=LINK')).toBeVisible();
  42  |   });
  43  | 
  44  |   test('2. Keyboard shortcuts and command palette work seamlessly', async ({ page }) => {
  45  |     await page.goto('/workspace');
> 46  |     await expect(page.locator('text=MuleTrace')).toBeVisible();
      |                                                  ^ Error: expect(locator).toBeVisible() failed
  47  | 
  48  |     // Open Command Palette via TopBar button
  49  |     const cmdBtn = page.locator('button').filter({ hasText: 'Quick actions' });
  50  |     if (await cmdBtn.isVisible()) {
  51  |       await cmdBtn.click();
  52  |     } else {
  53  |       await page.keyboard.press('Control+k');
  54  |     }
  55  | 
  56  |     await expect(page.locator('text=Type a command or jump to page...')).toBeVisible();
  57  | 
  58  |     // Press Escape to close Command Palette
  59  |     await page.keyboard.press('Escape');
  60  |     await expect(page.locator('text=Type a command or jump to page...')).not.toBeVisible();
  61  | 
  62  |     // Press P to toggle Presenter Mode
  63  |     await page.keyboard.press('p');
  64  |     await expect(page.locator('text=Exit Presenter Mode (P)')).toBeVisible();
  65  | 
  66  |     // Press P again to exit Presenter Mode
  67  |     await page.keyboard.press('p');
  68  |     await expect(page.locator('text=Exit Presenter Mode (P)')).not.toBeVisible();
  69  |   });
  70  | 
  71  |   test('3. Responsive snapshots across required breakpoints', async ({ page }) => {
  72  |     const viewports = [
  73  |       { width: 1440, height: 900, name: 'workspace-1440x900' },
  74  |       { width: 1366, height: 768, name: 'workspace-1366x768' },
  75  |       { width: 1024, height: 768, name: 'workspace-1024x768' },
  76  |       { width: 390, height: 844, name: 'workspace-390x844' },
  77  |     ];
  78  | 
  79  |     for (const vp of viewports) {
  80  |       await page.setViewportSize({ width: vp.width, height: vp.height });
  81  |       await page.goto('/workspace?session_id=demo_ravi_run&mode=replay');
  82  |       await page.waitForTimeout(1000);
  83  |       await page.screenshot({
  84  |         path: path.join(SCREENSHOT_DIR, `${vp.name}.png`),
  85  |         fullPage: false,
  86  |       });
  87  |     }
  88  |   });
  89  | 
  90  |   test('4. Dark and Light screenshots of every page', async ({ page }) => {
  91  |     const pages = [
  92  |       { url: '/', name: 'landing' },
  93  |       { url: '/workspace?session_id=demo_ravi_run&mode=replay', name: 'workspace' },
  94  |       { url: '/cases', name: 'cases' },
  95  |       { url: '/memory', name: 'memory' },
  96  |       { url: '/tools', name: 'tools' },
  97  |       { url: '/how-it-works', name: 'how-it-works' },
  98  |     ];
  99  | 
  100 |     await page.setViewportSize({ width: 1440, height: 900 });
  101 | 
  102 |     for (const p of pages) {
  103 |       // Dark Theme Snapshot
  104 |       await page.goto(p.url);
  105 |       await page.evaluate(() => {
  106 |         document.documentElement.classList.add('dark');
  107 |         document.documentElement.classList.remove('light');
  108 |       });
  109 |       await page.waitForTimeout(800);
  110 |       await page.screenshot({
  111 |         path: path.join(SCREENSHOT_DIR, `${p.name}-dark.png`),
  112 |         fullPage: p.name === 'landing' || p.name === 'how-it-works',
  113 |       });
  114 | 
  115 |       // Light Theme Snapshot
  116 |       await page.evaluate(() => {
  117 |         document.documentElement.classList.remove('dark');
  118 |         document.documentElement.classList.add('light');
  119 |       });
  120 |       await page.waitForTimeout(800);
  121 |       await page.screenshot({
  122 |         path: path.join(SCREENSHOT_DIR, `${p.name}-light.png`),
  123 |         fullPage: p.name === 'landing' || p.name === 'how-it-works',
  124 |       });
  125 |     }
  126 |   });
  127 | });
  128 | 
```