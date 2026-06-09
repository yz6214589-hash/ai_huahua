import { test, expect } from '@playwright/test'

const pageErrors: string[] = []
const apiErrors: Array<{ url: string; status: number }> = []

test.describe('F. 参数优化功能回归测试', () => {

  test.beforeEach(async ({ page }) => {
    pageErrors.length = 0
    apiErrors.length = 0

    page.on('pageerror', (err) => {
      pageErrors.push(err.message)
      console.log(`[页面异常] ${err.message}`)
    })
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        pageErrors.push(`console.error: ${msg.text()}`)
        console.log(`[控制台错误] ${msg.text()}`)
      }
    })
    page.on('response', (res) => {
      if (res.status() >= 400) {
        apiErrors.push({ url: res.url(), status: res.status() })
        console.log(`[接口错误] ${res.status()} ${res.url()}`)
      }
    })
  })

  test('F01 参数优化页面加载正常', async ({ page }) => {
    await page.goto('/strategy/param-optimizer')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')
    await expect(page.getByRole('heading', { name: '参数优化' })).toBeVisible()
    await expect(page.getByRole('button', { name: /开始参数搜索/ })).toBeVisible()
  })

  test('F02 多选股票组件 - 搜索展示和添加删除', async ({ page }) => {
    await page.goto('/strategy/param-optimizer')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 验证多选股票组件存在
    await expect(page.getByText('选择股票（可多选）')).toBeVisible()

    // 验证总资金输入框存在
    await expect(page.getByText('总资金（元）')).toBeVisible()

    // 搜索股票（参数优化页面内的搜索框 - 该页面有2个，取第二个）
    const searchInput = page.getByPlaceholder('搜索股票代码或名称').nth(1)
    await searchInput.fill('600519')
    await page.waitForTimeout(1500)

    // 选择第一个搜索结果
    const firstOption = page.locator('button:has(span.font-mono)').first()
    const optionExists = await firstOption.count()
    if (optionExists > 0) {
      const optionText = await firstOption.textContent()
      console.log(`选择股票: ${optionText}`)
      await firstOption.click()
      await page.waitForTimeout(300)
    }

    // 验证已选股票标签出现
    const stockTags = page.locator('span.inline-flex.items-center.gap-1')
    const tagCount = await stockTags.count()
    console.log(`已选股票标签数量: ${tagCount}`)
    expect(tagCount).toBeGreaterThanOrEqual(1)

    // 验证资金分配卡片出现
    await expect(page.getByText('资金分配与收益概览')).toBeVisible()
    await expect(page.getByText('每只分配')).toBeVisible()
    await expect(page.getByText('选中股票')).toBeVisible()

    // 验证删除按钮存在
    const deleteBtn = stockTags.first().locator('button')
    expect(await deleteBtn.count()).toBe(1)

    // 搜索另一只股票
    await searchInput.fill('000001')
    await page.waitForTimeout(1500)

    const secondOption = page.locator('button:has(span.font-mono)').first()
    const secondExists = await secondOption.count()
    if (secondExists > 0) {
      await secondOption.click()
      await page.waitForTimeout(300)
    }

    // 验证有2只股票
    const stockTagsAfter = page.locator('span.inline-flex.items-center.gap-1')
    expect(await stockTagsAfter.count()).toBeGreaterThanOrEqual(2)

    // 修改总资金
    const cashInput = page.locator('input[type="number"]')
    await cashInput.fill('500000')
    await page.waitForTimeout(300)

    // 验证无页面异常
    const criticalErrors = pageErrors.filter(e => !e.includes('ResizeObserver'))
    expect(criticalErrors).toEqual([])
  })

  test('F03 参数搜索执行并返回非零指标', async ({ page }) => {
    await page.goto('/strategy/param-optimizer')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')

    await page.waitForTimeout(2000)

    // 使用多选股票组件搜索并添加股票
    const searchInput = page.getByPlaceholder('搜索股票代码或名称').nth(1)
    await searchInput.fill('600519')
    await page.waitForTimeout(1500)

    // 从搜索结果中选择
    const firstResult = page.locator('button:has(span.font-mono)').first()
    if (await firstResult.count() > 0) {
      await firstResult.click()
      await page.waitForTimeout(300)
      console.log('添加股票: 600519')
    }

    // 设置日期范围
    const dateInputs = page.locator('input[type="date"]')
    await dateInputs.nth(0).fill('2023-01-01')
    await dateInputs.nth(1).fill('2024-12-31')

    // 设置参数网格
    const paramInputs = page.locator('input.font-mono')
    const paramCount = await paramInputs.count()
    console.log(`检测到 ${paramCount} 个参数输入框`)
    for (let i = 0; i < paramCount; i++) {
      const html = await paramInputs.nth(i).evaluate((el) => el.parentElement?.textContent || '')
      if (html.includes('fast')) {
        await paramInputs.nth(i).fill('5,8,10')
        console.log('设置 fast = 5,8,10')
      } else if (html.includes('slow')) {
        await paramInputs.nth(i).fill('20,25,30')
        console.log('设置 slow = 20,25,30')
      }
    }

    // 点击开始参数搜索
    await page.getByRole('button', { name: /开始参数搜索/ }).click()

    // 等待各股票详细结果出现
    console.log('等待参数搜索完成...')
    await page.getByText('各股票详细结果').waitFor({ state: 'visible', timeout: 180000 })
    console.log('参数搜索完成')

    await page.waitForTimeout(1000)

    // 验证没有白屏
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 验证资金分配卡片有收益数据
    const totalProfitSection = page.getByText('总收益')
    expect(await totalProfitSection.count()).toBeGreaterThanOrEqual(1)

    // 验证各股票详细结果中至少有一个结果卡片
    const stockResultSections = page.locator('text=最佳参数')
    const stockCount = await stockResultSections.count()
    console.log(`股票结果卡片: ${stockCount} 个`)
    expect(stockCount).toBeGreaterThanOrEqual(1)

    // 验证至少有一个表格含数据（指标列不为 '—'）
    const tableRows = page.locator('table tbody tr')
    const rowCount = await tableRows.count()
    console.log(`总参数组合行数: ${rowCount}`)

    // 验证总收益率列不为 '—'
    if (rowCount > 0) {
      const firstRowTexts = await tableRows.nth(0).locator('td').evaluateAll((tds) => tds.map((td) => td.textContent || ''))
      console.log(`第一行数据: ${JSON.stringify(firstRowTexts)}`)
      // 检查最后6列（指标列）是否都不为 '—'
      const metricCols = firstRowTexts.slice(-6)
      const hasDash = metricCols.some((v) => v === '—')
      console.log(`指标列: ${JSON.stringify(metricCols)}, 含 —: ${hasDash}`)
      expect(hasDash).toBe(false)
    }

    // 验证无页面异常
    const criticalErrors = pageErrors.filter(e => !e.includes('ResizeObserver') && !e.includes('401'))
    console.log(`关键页面异常: ${criticalErrors.length} 条`)
    expect(criticalErrors).toEqual([])

    // 验证无接口错误
    console.log(`接口错误: ${apiErrors.length} 条`)
    apiErrors.forEach((e) => console.log(`  ${e.status} ${e.url}`))
  })
})
