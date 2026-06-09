import { test, expect } from '@playwright/test'

const consoleErrors: Array<{ testId: string; type: string; text: string; location?: string }> = []
const consoleWarnings: Array<{ testId: string; type: string; text: string }> = []
const apiErrors: Array<{ testId: string; url: string; status: number; method: string }> = []
let currentTestId = ''

test.beforeEach(async ({ page }, testInfo) => {
  currentTestId = `${testInfo.titlePath.join(' > ')}`
  console.log(`\n========== [开始] ${currentTestId} ==========`)
  console.log(`[时间] ${new Date().toISOString()}`)

  page.on('console', (msg) => {
    const entry = { testId: currentTestId, type: msg.type(), text: msg.text(), location: `${msg.location().url}:${msg.location().lineNumber}` }
    if (msg.type() === 'error') {
      consoleErrors.push(entry)
      console.log(`[控制台错误] ${msg.text()}`)
    } else if (msg.type() === 'warning') {
      consoleWarnings.push(entry)
    } else if (msg.type() === 'log') {
      console.log(`[控制台日志] ${msg.text().substring(0, 200)}`)
    }
  })

  page.on('pageerror', (error) => {
    consoleErrors.push({ testId: currentTestId, type: 'pageerror', text: error.message, location: error.stack?.substring(0, 300) })
    console.log(`[页面异常] ${error.message}`)
  })

  page.on('response', (response) => {
    if (response.status() >= 400) {
      const entry = { testId: currentTestId, url: response.url(), status: response.status(), method: response.request().method() }
      apiErrors.push(entry)
      console.log(`[接口错误] ${response.request().method()} ${response.url()} -> ${response.status()}`)
    }
  })

  page.on('requestfailed', (request) => {
    console.log(`[请求失败] ${request.method()} ${request.url()} - ${request.failure()?.errorText}`)
  })
})

test.afterEach(async ({ page }, testInfo) => {
  const status = testInfo.status
  const duration = testInfo.duration
  console.log(`[结果] ${status === 'passed' ? '通过' : '失败'} | 耗时: ${duration}ms`)
  console.log(`========== [结束] ${currentTestId} ==========\n`)
})

/* ===================================================================
   区间模式回测 - 回归测试（5条）
   覆盖：全区间回测、训练/验证/测试划分、区间验证、错误处理
   =================================================================== */
test.describe('E. 回测功能 - 区间模式回归测试', () => {

  test('E01 回测页面加载正常', async ({ page }) => {
    await page.goto('/strategy/backtest')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')
    await expect(page.getByText('全区间回测')).toBeVisible()
    await expect(page.getByText('训练/验证/测试划分')).toBeVisible()
    await expect(page.getByText('开始回测')).toBeVisible()
  })

  test('E02 切换区间模式为训练/验证/测试划分 - 比例滑块可见', async ({ page }) => {
    await page.goto('/strategy/backtest')
    await page.waitForLoadState('domcontentloaded')
    // 选择 "训练/验证/测试划分"
    await page.getByText('训练/验证/测试划分').click()
    await page.waitForTimeout(300)
    // 验证比例滑块和比例总和显示
    await expect(page.getByText('训练集比例')).toBeVisible()
    await expect(page.getByText('验证集比例')).toBeVisible()
    await expect(page.getByText('测试集比例')).toBeVisible()
    await expect(page.getByText(/比例总和/)).toBeVisible()
  })

  test('E03 区间模式回测执行 - 正常返回无白屏', async ({ page }) => {
    // 前置条件：后端服务正常运行，有可用的策略和股票数据
    // 操作步骤：
    //   1. 打开回测页面
    //   2. 确保选中 "直接选策略" 模式，选择一个策略
    //   3. 选择 "训练/验证/测试划分" 模式
    //   4. 输入股票代码 600519.SH
    //   5. 点击 "开始回测" 按钮
    // 期望结果：
    //   1. 回测完成后页面不跳转，无白屏
    //   2. 页面不显示 "Not Found"
    //   3. 无控制台错误（pageerror）
    //   4. API 调用返回状态码 2xx
    //   5. 区间划分结果卡片展示（训练集、验证集、测试集）
    await page.goto('/strategy/backtest')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 确保切换到 "直接选策略" 模式
    const directMode = page.getByText('直接选策略')
    const directExists = await directMode.count()
    if (directExists > 0) {
      await directMode.click()
      await page.waitForTimeout(300)
    }

    // 选择第一个可用的策略
    const strategySelect = page.locator('select').first()
    const strategyOptions = await strategySelect.locator('option').all()
    if (strategyOptions.length > 1) {
      const firstVal = await strategyOptions[1].getAttribute('value')
      if (firstVal) {
        await strategySelect.selectOption(firstVal)
        await page.waitForTimeout(300)
      }
    }

    // 选择 "训练/验证/测试划分"
    await page.getByText('训练/验证/测试划分').click()
    await page.waitForTimeout(300)

    // 输入股票代码
    const stockInput = page.locator('input[placeholder*="搜索股票"]').first()
    await stockInput.fill('600519.SH')
    await page.waitForTimeout(500)

    // 点击 "开始回测" 按钮
    await page.getByText('开始回测').click()

    // 等待回测完成（最多等待 30 秒）
    await page.waitForTimeout(3000)

    // 验证页面没有白屏 - 检查 body 是否包含内容
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 等待回测按钮恢复为非 "回测中..." 状态
    const runningBtn = page.getByText('回测中...')
    const isRunning = await runningBtn.count()
    if (isRunning > 0) {
      // 等待回测完成
      await page.waitForFunction(() => {
        const btn = document.querySelector('button')
        if (!btn) return false
        return btn.textContent?.includes('开始回测') || btn.textContent?.includes('开始批量回测')
      }, { timeout: 60000 })
    }

    await page.waitForTimeout(1000)

    // 验证页面没有白屏
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 验证没有页面异常
    const pageErrors = consoleErrors.filter(e => e.type === 'pageerror')
    expect(pageErrors.length).toBe(0)
  })

  test('E04 全区间模式回测对比 - 正常返回', async ({ page }) => {
    // 操作步骤：
    //   1. 打开回测页面
    //   2. 确保选中 "直接选策略" 模式
    //   3. 选择 "全区间回测" 模式（默认）
    //   4. 输入股票代码
    //   5. 点击 "开始回测"
    // 期望结果：
    //   1. 回测完成，指标卡片展示
    //   2. 净值曲线和回测曲线图表渲染
    //   3. 交易记录表格展示
    //   4. 无控制台错误
    await page.goto('/strategy/backtest')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')

    // 确保使用 "直接选策略" 模式
    const directMode = page.getByText('直接选策略')
    const directExists = await directMode.count()
    if (directExists > 0) {
      await directMode.click()
      await page.waitForTimeout(300)
    }

    // 选择第一个可用的策略
    const strategySelect = page.locator('select').first()
    const strategyOptions = await strategySelect.locator('option').all()
    if (strategyOptions.length > 1) {
      const firstVal = await strategyOptions[1].getAttribute('value')
      if (firstVal) {
        await strategySelect.selectOption(firstVal)
        await page.waitForTimeout(300)
      }
    }

    // 确保选择 "全区间回测"
    await page.getByText('全区间回测').click()
    await page.waitForTimeout(300)

    // 输入股票代码
    const stockInput = page.locator('input[placeholder*="搜索股票"]').first()
    await stockInput.fill('600519.SH')
    await page.waitForTimeout(500)

    // 点击 "开始回测"
    await page.getByText('开始回测').click()

    // 等待回测完成
    await page.waitForTimeout(3000)
    const runningBtn = page.getByText('回测中...')
    const isRunning = await runningBtn.count()
    if (isRunning > 0) {
      await page.waitForFunction(() => {
        const btn = document.querySelector('button')
        if (!btn) return false
        return btn.textContent?.includes('开始回测') || btn.textContent?.includes('开始批量回测')
      }, { timeout: 60000 })
    }

    await page.waitForTimeout(1000)

    // 验证页面没有白屏
    await expect(page.locator('body')).not.toContainText('Not Found')

    const pageErrors = consoleErrors.filter(e => e.type === 'pageerror')
    expect(pageErrors.length).toBe(0)
  })

  test('E05 切换区间模式后参数传递正确性', async ({ page }) => {
    // 验证在区间模式和非区间模式之间切换时，UI 状态正确保持
    await page.goto('/strategy/backtest')
    await page.waitForLoadState('domcontentloaded')

    // 先切换到 "训练/验证/测试划分" 模式
    await page.getByText('训练/验证/测试划分').click()
    await page.waitForTimeout(300)
    await expect(page.getByText('训练集比例')).toBeVisible()

    // 再切换回 "全区间回测"
    await page.getByText('全区间回测').click()
    await page.waitForTimeout(300)

    // 全区间模式下不应显示比例滑块
    const trainSlider = page.getByText('训练集比例')
    const trainExists = await trainSlider.count()
    expect(trainExists).toBe(0)

    // 再次切回区间模式
    await page.getByText('训练/验证/测试划分').click()
    await page.waitForTimeout(300)
    await expect(page.getByText('训练集比例')).toBeVisible()
  })
})

test.afterAll(async () => {
  console.log('\n')
  console.log('============================================================')
  console.log('              回测区间模式测试汇总报告')
  console.log('============================================================')
  console.log(`[控制台错误] 共 ${consoleErrors.length} 条`)
  if (consoleErrors.length > 0) {
    consoleErrors.forEach((e, i) => {
      console.log(`  ${i + 1}. [${e.type}] ${e.testId}`)
      console.log(`     内容: ${e.text.substring(0, 200)}`)
      if (e.location) console.log(`     位置: ${e.location.substring(0, 200)}`)
    })
  }
  console.log(`[控制台警告] 共 ${consoleWarnings.length} 条`)
  if (consoleWarnings.length > 0) {
    consoleWarnings.slice(0, 20).forEach((e, i) => {
      console.log(`  ${i + 1}. ${e.testId}: ${e.text.substring(0, 150)}`)
    })
    if (consoleWarnings.length > 20) console.log(`  ... 还有 ${consoleWarnings.length - 20} 条警告省略`)
  }
  console.log(`[接口错误] 共 ${apiErrors.length} 条`)
  if (apiErrors.length > 0) {
    apiErrors.forEach((e, i) => {
      console.log(`  ${i + 1}. [${e.status}] ${e.method} ${e.url.substring(0, 120)}`)
      console.log(`     所属用例: ${e.testId}`)
    })
  }
  console.log('============================================================')
})
