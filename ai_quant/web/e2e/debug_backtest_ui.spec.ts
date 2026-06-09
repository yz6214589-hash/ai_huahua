import { test } from '@playwright/test'

test('调试单个回测流程', async ({ page }) => {
  await page.goto('/strategy/backtest', { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForTimeout(2000)

  // 切换到直接选策略模式
  await page.evaluate(() => {
    const label = Array.from(document.querySelectorAll('label')).find(l => l.textContent?.includes('直接选策略'));
    if (label) {
      const radio = label.querySelector('input[type="radio"]');
      if (radio) (radio as HTMLInputElement).click();
    }
  })
  await page.waitForTimeout(1000)

  // 切换到单只股票回测
  await page.evaluate(() => {
    const label = Array.from(document.querySelectorAll('label')).find(l => l.textContent?.includes('单只股票回测'));
    if (label) {
      const radio = label.querySelector('input[type="radio"]');
      if (radio) (radio as HTMLInputElement).click();
    }
  })
  await page.waitForTimeout(1000)

  // 选择策略
  await page.locator('select').first().selectOption('ma_dual')
  await page.waitForTimeout(500)

  // 输入股票代码 - StockPicker组件需要搜索并选择
  const stockPickerArea = page.locator('.relative').filter({ has: page.locator('input[placeholder*="搜索股票"]') }).first()
  const stockInput = stockPickerArea.locator('input').first()
  await stockInput.click()
  await page.waitForTimeout(500)
  await stockInput.fill('002410.SZ')
  await page.waitForTimeout(2000)  // 等待防抖搜索完成

  // 截图搜索下拉
  await page.screenshot({ path: 'test-results/debug_stock_picker.png', fullPage: true })

  // 检查搜索结果
  const searchResults = await page.evaluate(() => {
    const items = document.querySelectorAll('.flex.items-center.justify-between');
    return Array.from(items).map(el => el.textContent?.substring(0, 100));
  })
  console.log('搜索结果:', JSON.stringify(searchResults))

  // 查找并点击"选择"按钮
  const selectBtn = page.locator('button').filter({ hasText: '选择' }).first()
  if (await selectBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await selectBtn.click({ force: true })
    console.log('已选择股票 002410.SZ')
  } else {
     console.log('未找到"选择"按钮，尝试回车')
     // 如果没找到按钮，直接用回车选择第一个结果
     const pickerInput = page.locator('input[placeholder*="搜索股票"]').first()
     await pickerInput.press('Enter')
     await page.waitForTimeout(500)
   }
   await page.waitForTimeout(1000)

  // 设置日期
  const dateInputs = page.locator('input[type="date"]')
  if (await dateInputs.count() >= 2) {
    await dateInputs.nth(0).fill('2023-01-01')
    await dateInputs.nth(1).fill('2024-12-31')
  }

  // 截图1: 回测前页面
  await page.screenshot({ path: 'test-results/debug_before_backtest.png', fullPage: true })

  // 点击开始回测
  await page.getByRole('button', { name: /开始回测/ }).click()
  console.log('已点击回测按钮')

  // 等待结果
  await page.waitForTimeout(5000)

  // 截图2: 回测后页面
  await page.screenshot({ path: 'test-results/debug_after_backtest.png', fullPage: true })

  // 获取页面完整文本
  const pageText = await page.evaluate(() => document.body.innerText)
  console.log('===== 回测后页面文本 =====')
  console.log(pageText)
  console.log('===== 结束 =====')

  // 检查是否包含特定文本
  const hasMetrics = pageText.includes('年化收益') || pageText.includes('总收益率') || pageText.includes('初始资金')
  const hasError = pageText.includes('失败') || pageText.includes('错误')
  console.log(`检测到指标: ${hasMetrics}, 检测到错误: ${hasError}`)
})
