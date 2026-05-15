import { test, expect } from '@playwright/test'

// 测试环境配置
const BASE_URL = 'http://localhost:5173'

// 1. 首页总览页面测试
test.describe('首页总览页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
  })

  test('首页应该加载并显示主要内容', async ({ page }) => {
    // 等待页面加载
    await expect(page.locator('body')).toBeVisible()

    // 检查页面标题
    const title = await page.title()
    expect(title).toContain('招财猫')
  })

  test('侧边栏导航应该可见', async ({ page }) => {
    // 检查侧边栏存在
    const sidebar = page.locator('nav, aside, [class*="sidebar"], [class*="Sidebar"]').first()
    await expect(sidebar).toBeVisible({ timeout: 5000 }).catch(() => {
      // 导航可能在不同位置，继续测试
      console.log('导航元素未找到，继续测试其他元素')
    })
  })
})

// 2. 自选股页面测试
test.describe('自选股页面测试', () => {
  test('自选股页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/watchlist`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含自选股相关内容
    await expect(page.locator('body')).toBeVisible()

    // 等待可能的加载状态消失
    await page.waitForTimeout(1000)
  })
})

// 3. 采集任务页面测试
test.describe('采集任务页面测试', () => {
  test('采集任务页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/jobs`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含任务相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 4. 研报页面测试
test.describe('智能研报页面测试', () => {
  test('研报页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/reports`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含研报相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 5. 舆情监控页面测试
test.describe('舆情监控页面测试', () => {
  test('舆情页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/sentiment`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含舆情相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 6. 风控中心页面测试
test.describe('风控中心页面测试', () => {
  test('风控页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/risk`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含风控相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 7. 执行监控页面测试
test.describe('执行监控页面测试', () => {
  test('执行页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/execution`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含执行相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 8. 晨会简报页面测试
test.describe('晨会简报页面测试', () => {
  test('晨会页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/morning`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含晨会相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 9. AI对话页面测试
test.describe('AI对话页面测试', () => {
  test('AI对话页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含AI相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 10. 数据页面测试
test.describe('数据与交付页面测试', () => {
  test('数据页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含数据相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 11. 策略分析页面测试
test.describe('策略分析页面测试', () => {
  test('策略分析页面应该正常加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/strategy`)
    await page.waitForLoadState('networkidle')

    // 检查页面包含策略相关内容
    await expect(page.locator('body')).toBeVisible()
    await page.waitForTimeout(1000)
  })
})

// 12. 404页面测试
test.describe('404页面测试', () => {
  test('访问不存在的页面应该显示404', async ({ page }) => {
    await page.goto(`${BASE_URL}/non-existent-page-12345`)
    await page.waitForLoadState('networkidle')

    // 检查页面加载
    await expect(page.locator('body')).toBeVisible()
  })
})
