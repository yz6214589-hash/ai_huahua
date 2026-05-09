# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: trading_api.spec.ts >> trading proxy via backend swagger >> GET state and POST connect
- Location: e2e/trading_api.spec.ts:4:3

# Error details

```
Error: locator.click: Target page, context or browser has been closed
Call log:
  - waiting for locator('.opblock').filter({ hasText: '/api/trading/state' }).first().locator('summary').first()

```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test'
  2  | 
  3  | test.describe('trading proxy via backend swagger', () => {
  4  |   test('GET state and POST connect', async ({ page }) => {
  5  |     test.setTimeout(120_000)
  6  | 
  7  |     await page.goto('http://localhost:8000/docs', { waitUntil: 'domcontentloaded' })
  8  |     await expect(page).toHaveTitle(/Swagger UI/i)
  9  | 
  10 |     const stateOp = page.locator('.opblock', { hasText: '/api/trading/state' }).first()
> 11 |     await stateOp.locator('summary').first().click()
     |                                              ^ Error: locator.click: Target page, context or browser has been closed
  12 |     await stateOp.locator('button:has-text("Try it out")').click()
  13 |     await stateOp.locator('button:has-text("Execute")').click()
  14 |     await expect(stateOp.locator('.responses-inner')).toContainText('200')
  15 |     await expect(stateOp.locator('.responses-inner')).not.toContainText('missing env: AI_QUANT_QMT_GATEWAY_BASE')
  16 | 
  17 |     const connectOp = page.locator('.opblock', { hasText: '/api/trading/connect' }).first()
  18 |     await connectOp.locator('summary').first().click()
  19 |     await connectOp.locator('button:has-text("Try it out")').click()
  20 |     await connectOp.locator('button:has-text("Execute")').click()
  21 | 
  22 |     await expect(connectOp.locator('.responses-inner')).not.toContainText('missing env: AI_QUANT_QMT_GATEWAY_BASE')
  23 |     await expect(connectOp.locator('.responses-inner')).not.toContainText('TimeoutError')
  24 |     await expect(connectOp.locator('.responses-inner')).not.toContainText('502')
  25 |   })
  26 | })
  27 | 
  28 | 
```