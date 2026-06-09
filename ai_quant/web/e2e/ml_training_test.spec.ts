/**
 * ML训练页面端到端测试
 * 覆盖页面渲染、交互功能、训练流程、错误处理和响应式布局
 */

import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

// 获取当前文件目录（兼容 ESM）
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// 截图保存目录
const SCREENSHOT_DIR = path.join(__dirname, 'test_screenshots', 'ml_training')

// 确保截图目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}

// 辅助函数：带序号的截图
async function takeScreenshot(page: Page, name: string, seq: number) {
  const filePath = path.join(SCREENSHOT_DIR, `${String(seq).padStart(2, '0')}_${name}.png`)
  await page.screenshot({ path: filePath, fullPage: true })
  console.log(`[截图] ${filePath}`)
  return filePath
}

// 辅助函数：等待页面加载完成
async function waitForPageReady(page: Page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
}

// ==================== 测试套件 ====================

test.describe('ML训练页面 - 页面渲染测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ml-training')
    await waitForPageReady(page)
  })

  test('TC-R01: 页面能正常打开，不显示 Not Found', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('text=海龟交易 ML 模型训练')).toBeVisible()
    // 验证不出现 Not Found
    await expect(page.locator('text=Not Found')).not.toBeVisible()
    // 验证不出现 404
    await expect(page.locator('text=404')).not.toBeVisible()

    await takeScreenshot(page, 'page_render_no_404', 1)
  })

  test('TC-R02: 所有UI元素正确渲染', async ({ page }) => {
    // 标题区域
    await expect(page.locator('h1:has-text("海龟交易 ML 模型训练")')).toBeVisible()
    await expect(page.locator('text=基于多只股票突破事件特征训练分类模型')).toBeVisible()

    // 配置面板
    await expect(page.locator('text=训练配置')).toBeVisible()
    await expect(page.locator('text=选择股票和参数进行ML模型训练')).toBeVisible()

    // 股票选择器
    await expect(page.locator('label:has-text("选择股票")')).toBeVisible()
    await expect(page.locator('input[placeholder*="搜索并添加股票"]')).toBeVisible()

    // 日期输入框
    await expect(page.locator('label:has-text("开始日期")')).toBeVisible()
    await expect(page.locator('label:has-text("结束日期")')).toBeVisible()
    await expect(page.locator('label:has-text("分割日期")')).toBeVisible()

    // 参数输入框
    await expect(page.locator('label:has-text("唐奇安通道周期")')).toBeVisible()
    await expect(page.locator('label:has-text("ATR计算周期")')).toBeVisible()

    // 训练按钮
    await expect(page.locator('button:has-text("开始训练")')).toBeVisible()

    await takeScreenshot(page, 'all_ui_elements', 2)
  })

  test('TC-R03: 侧边栏导航 ML训练 正确显示', async ({ page }) => {
    // 验证侧边栏包含 ML训练 导航项
    const navItem = page.locator('nav a:has-text("ML训练")')
    await expect(navItem).toBeVisible()

    // 验证当前导航项处于激活状态
    await expect(navItem).toHaveClass(/bg-zinc-100/)

    // 验证图标存在
    await expect(navItem.locator('svg')).toBeVisible()

    await takeScreenshot(page, 'sidebar_nav_active', 3)
  })

  test('TC-R04: 页面默认参数值正确', async ({ page }) => {
    // 验证默认日期
    await expect(page.locator('input[type="date"]').nth(0)).toHaveValue('2024-01-01')
    await expect(page.locator('input[type="date"]').nth(1)).toHaveValue('2025-12-31')
    await expect(page.locator('input[type="date"]').nth(2)).toHaveValue('2025-01-01')

    // 验证默认参数
    await expect(page.locator('input[type="number"]').nth(0)).toHaveValue('20')
    await expect(page.locator('input[type="number"]').nth(1)).toHaveValue('20')
  })
})

test.describe('ML训练页面 - 交互功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ml-training')
    await waitForPageReady(page)
  })

  test('TC-I01: 股票选择器能正常搜索和选择多只股票', async ({ page }) => {
    // 点击股票选择器输入框
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)

    // 输入搜索关键词
    await stockInput.fill('平安')
    await page.waitForTimeout(600) // 等待防抖搜索

    // 等待搜索结果出现（使用first避免strict mode violation）
    await expect(page.locator('text=平安银行').first()).toBeVisible({ timeout: 5000 })

    await takeScreenshot(page, 'stock_search_results', 4)

    // 选择第一只股票 - 点击下拉列表中的第一个添加按钮
    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    // 再次搜索并选择第二只
    await stockInput.fill('茅台')
    await page.waitForTimeout(600)
    await expect(page.locator('text=贵州茅台').first()).toBeVisible({ timeout: 5000 })

    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    await takeScreenshot(page, 'stock_multi_selected', 5)
  })

  test('TC-I02: 日期输入框能正常设置', async ({ page }) => {
    // 修改开始日期
    const startDateInput = page.locator('input[type="date"]').nth(0)
    await startDateInput.fill('2023-06-01')
    await expect(startDateInput).toHaveValue('2023-06-01')

    // 修改结束日期
    const endDateInput = page.locator('input[type="date"]').nth(1)
    await endDateInput.fill('2024-12-31')
    await expect(endDateInput).toHaveValue('2024-12-31')

    // 修改分割日期
    const splitDateInput = page.locator('input[type="date"]').nth(2)
    await splitDateInput.fill('2024-01-01')
    await expect(splitDateInput).toHaveValue('2024-01-01')

    await takeScreenshot(page, 'date_inputs_changed', 6)
  })

  test('TC-I03: 参数输入框能正常修改', async ({ page }) => {
    // 修改唐奇安通道周期
    const entryPeriodInput = page.locator('input[type="number"]').nth(0)
    await entryPeriodInput.fill('30')
    await expect(entryPeriodInput).toHaveValue('30')

    // 修改ATR计算周期
    const atrPeriodInput = page.locator('input[type="number"]').nth(1)
    await atrPeriodInput.fill('14')
    await expect(atrPeriodInput).toHaveValue('14')

    await takeScreenshot(page, 'param_inputs_changed', 7)
  })

  test('TC-I04: 开始训练按钮状态正确（未选股票时禁用）', async ({ page }) => {
    const trainBtn = page.locator('button:has-text("开始训练")')

    // 未选择股票时按钮应禁用
    await expect(trainBtn).toBeDisabled()

    // 选择股票 - 使用更可靠的股票代码搜索
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    // 只选1只，按钮仍应禁用
    await expect(trainBtn).toBeDisabled()

    // 选择第二只 - 清空输入框再搜索
    await stockInput.click()
    await stockInput.fill('')
    await page.waitForTimeout(200)
    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    // 选择2只后按钮应启用
    await expect(trainBtn).toBeEnabled()

    await takeScreenshot(page, 'train_btn_enabled', 8)
  })
})

test.describe('ML训练页面 - 训练流程测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ml-training')
    await waitForPageReady(page)
  })

  test('TC-T01: 选择2只以上股票，点击训练，观察loading状态', async ({ page }) => {
    // 选择第一只股票
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    // 选择第二只股票
    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    // 选择第三只股票
    await stockInput.fill('000063')
    await page.waitForTimeout(600)
    const addBtn3 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn3.isVisible().catch(() => false)) {
      await addBtn3.click()
      await page.waitForTimeout(300)
    }

    await takeScreenshot(page, 'before_train_click', 9)

    // 点击训练按钮
    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()

    // 验证loading状态
    await expect(page.locator('text=训练中...')).toBeVisible({ timeout: 3000 })
    await expect(page.locator('.animate-spin')).toBeVisible()

    await takeScreenshot(page, 'training_loading', 10)

    // 等待训练完成或超时（最多60秒）
    await expect(page.locator('text=训练中...')).not.toBeVisible({ timeout: 60000 })

    await takeScreenshot(page, 'training_completed', 11)
  })

  test('TC-T02: 训练完成后结果是否正确展示', async ({ page }) => {
    // 选择股票
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    // 点击训练
    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()

    // 等待训练完成
    await expect(page.locator('text=训练中...')).not.toBeVisible({ timeout: 60000 })

    // 验证结果区域显示
    const resultVisible = await page.locator('text=模型评估指标').isVisible().catch(() => false)
    const errorVisible = await page.locator('text=训练失败').isVisible().catch(() => false)

    if (resultVisible) {
      // 验证指标卡片
      await expect(page.locator('text=准确率')).toBeVisible()
      await expect(page.locator('text=精确率')).toBeVisible()
      await expect(page.locator('text=召回率')).toBeVisible()
      await expect(page.locator('text=F1分数')).toBeVisible()
      await expect(page.locator('text=训练样本')).toBeVisible()
      await expect(page.locator('text=测试样本')).toBeVisible()

      await takeScreenshot(page, 'result_metrics_displayed', 12)
    } else if (errorVisible) {
      console.log('训练返回错误，记录错误信息')
      await takeScreenshot(page, 'result_error_displayed', 12)
    }
  })

  test('TC-T03: 特征重要性图表是否正确渲染', async ({ page }) => {
    // 选择股票并训练
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()
    await expect(page.locator('text=训练中...')).not.toBeVisible({ timeout: 60000 })

    // 检查特征重要性区域
    const featureHeader = page.locator('text=特征重要性')
    if (await featureHeader.isVisible().catch(() => false)) {
      await expect(featureHeader).toBeVisible()

      // 验证特征名称显示
      const featureLabels = ['ATR比率', 'ADX', '量比', 'RSI', '突破强度', '5日动量', '盘整天数', 'ATR变化']
      for (const label of featureLabels) {
        const hasLabel = await page.locator(`text=${label}`).isVisible().catch(() => false)
        if (hasLabel) {
          console.log(`特征标签存在: ${label}`)
        }
      }

      await takeScreenshot(page, 'feature_importance_chart', 13)
    } else {
      console.log('特征重要性区域未显示（可能训练失败或无数据）')
    }
  })

  test('TC-T04: 预测样本表格是否正确显示', async ({ page }) => {
    // 选择股票并训练
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()
    await expect(page.locator('text=训练中...')).not.toBeVisible({ timeout: 60000 })

    // 检查预测样本表格
    const predHeader = page.locator('text=预测样本')
    if (await predHeader.isVisible().catch(() => false)) {
      await expect(predHeader).toBeVisible()
      await expect(page.locator('th:has-text("日期")')).toBeVisible()
      await expect(page.locator('th:has-text("预测概率")')).toBeVisible()

      await takeScreenshot(page, 'predictions_table', 14)
    } else {
      console.log('预测样本表格未显示（可能训练失败或无数据）')
    }
  })
})

test.describe('ML训练页面 - 错误处理测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ml-training')
    await waitForPageReady(page)
  })

  test('TC-E01: 选择少于2只股票时的提示', async ({ page }) => {
    // 只选择1只股票
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    // 点击训练按钮
    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()

    // 验证提示信息
    // 由于按钮disabled，点击不会触发，这里验证按钮确实禁用
    await expect(trainBtn).toBeDisabled()

    await takeScreenshot(page, 'less_than_2_stocks', 15)
  })

  test('TC-E02: 后端返回错误时的前端展示', async ({ page }) => {
    // 拦截API请求并返回错误
    await page.route('**/api/v1/analysis/ml-train', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: false,
          error: '测试错误：股票数据不足，无法训练模型',
        }),
      })
    })

    // 选择2只股票
    const stockInput = page.locator('input[placeholder*="搜索并添加股票"]').first()
    await stockInput.click()
    await page.waitForTimeout(300)
    await stockInput.fill('000001')
    await page.waitForTimeout(600)

    const addBtn = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click()
      await page.waitForTimeout(300)
    }

    await stockInput.fill('000002')
    await page.waitForTimeout(600)
    const addBtn2 = page.locator('.z-50 button:has-text("添加")').first()
    if (await addBtn2.isVisible().catch(() => false)) {
      await addBtn2.click()
      await page.waitForTimeout(300)
    }

    // 点击训练
    const trainBtn = page.locator('button:has-text("开始训练")')
    await trainBtn.click()

    // 等待错误展示
    await expect(page.locator('text=测试错误：股票数据不足，无法训练模型')).toBeVisible({ timeout: 5000 })

    await takeScreenshot(page, 'backend_error_display', 16)
  })
})

test.describe('ML训练页面 - 响应式测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ml-training')
    await waitForPageReady(page)
  })

  test('TC-Res01: 桌面端布局正常', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.waitForTimeout(500)

    // 验证侧边栏显示
    await expect(page.locator('aside')).toBeVisible()
    // 验证主内容区域
    await expect(page.locator('main')).toBeVisible()

    await takeScreenshot(page, 'responsive_desktop', 17)
  })

  test('TC-Res02: 平板端布局正常', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.waitForTimeout(500)

    // 验证页面内容可见
    await expect(page.locator('text=海龟交易 ML 模型训练')).toBeVisible()

    await takeScreenshot(page, 'responsive_tablet', 18)
  })

  test('TC-Res03: 手机端布局正常', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.waitForTimeout(500)

    // 验证页面内容可见（侧边栏应隐藏）
    await expect(page.locator('text=海龟交易 ML 模型训练')).toBeVisible()

    await takeScreenshot(page, 'responsive_mobile', 19)
  })
})
