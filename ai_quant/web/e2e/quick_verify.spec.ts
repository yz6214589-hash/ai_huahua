import { test, expect } from '@playwright/test'

test('宏观数据页面快速验证', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  const responseErrors: string[] = []
  page.on('response', (resp) => {
    if (resp.status() >= 400) responseErrors.push(`${resp.status()} ${resp.url()}`)
  })

  await page.goto('/info-access/macro', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(5000)

  const bodyText = await page.locator('body').innerText()
  console.log('=== 页面文本内容（前2000字符）===')
  console.log(bodyText.substring(0, 2000))

  const hasCPI = bodyText.includes('CPI')
  const hasPMI = bodyText.includes('PMI')
  const hasLPR = bodyText.includes('LPR')
  const hasVIX = bodyText.includes('VIX')
  const hasFearGreed = bodyText.includes('FearGreed') || bodyText.includes('恐惧贪婪')
  const hasNoData = bodyText.includes('暂无宏观数据')

  console.log('\n=== 指标检测结果 ===')
  console.log('CPI:', hasCPI)
  console.log('PMI:', hasPMI)
  console.log('LPR:', hasLPR)
  console.log('VIX:', hasVIX)
  console.log('FearGreed:', hasFearGreed)
  console.log('暂无宏观数据:', hasNoData)

  console.log('\n=== 控制台错误 ===')
  consoleErrors.forEach(e => console.log(e))
  console.log('\n=== 接口错误 ===')
  responseErrors.forEach(e => console.log(e))

  const indicatorCount = [hasCPI, hasPMI, hasLPR, hasVIX, hasFearGreed].filter(Boolean).length
  console.log('\n检测到的指标数量:', indicatorCount)
  expect(indicatorCount).toBeGreaterThanOrEqual(1)
})

test('000016.SH 个股详情页面验证', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  const responseErrors: string[] = []
  page.on('response', (resp) => {
    if (resp.status() >= 400) responseErrors.push(`${resp.status()} ${resp.url()}`)
  })

  await page.goto('/stock/000016.SH', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(5000)

  const bodyText = await page.locator('body').innerText()
  console.log('=== 000016.SH 页面文本内容（前2000字符）===')
  console.log(bodyText.substring(0, 2000))

  console.log('\n=== 控制台错误 ===')
  consoleErrors.forEach(e => console.log(e))
  console.log('\n=== 接口错误 ===')
  responseErrors.forEach(e => console.log(e))
})
