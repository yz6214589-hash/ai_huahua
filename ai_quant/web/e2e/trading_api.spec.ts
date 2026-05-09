import { test, expect } from '@playwright/test'

test.describe('trading proxy via backend swagger', () => {
  test('GET state and POST connect', async ({ page }) => {
    test.setTimeout(120_000)

    await page.goto('http://localhost:8000/docs', { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveTitle(/Swagger UI/i)

    const stateOp = page.locator('.opblock', { hasText: '/api/trading/state' }).first()
    await stateOp.locator('summary').first().click()
    await stateOp.locator('button:has-text("Try it out")').click()
    await stateOp.locator('button:has-text("Execute")').click()
    await expect(stateOp.locator('.responses-inner')).toContainText('200')
    await expect(stateOp.locator('.responses-inner')).not.toContainText('missing env: AI_QUANT_QMT_GATEWAY_BASE')

    const connectOp = page.locator('.opblock', { hasText: '/api/trading/connect' }).first()
    await connectOp.locator('summary').first().click()
    await connectOp.locator('button:has-text("Try it out")').click()
    await connectOp.locator('button:has-text("Execute")').click()

    await expect(connectOp.locator('.responses-inner')).not.toContainText('missing env: AI_QUANT_QMT_GATEWAY_BASE')
    await expect(connectOp.locator('.responses-inner')).not.toContainText('TimeoutError')
    await expect(connectOp.locator('.responses-inner')).not.toContainText('502')
  })
})

