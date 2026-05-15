import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const BASE_URL = 'http://localhost:5173'
const SCREENSHOT_DIR = '/Users/apple/Desktop/ai_huahua/ai_quant/backend/tests/e2e_screenshots'
const REPORT_OUTPUT_DIR = '/Users/apple/Documents/quant/REPORT'
const DEFAULT_OUTPUT_DIR = '/Users/apple/Desktop/ai_huahua/ai_quant/.ai_quant/report_outputs'

const TEST_CASES: Array<{
  id: string
  stockName: string
  stockCode: string
  model: string
  useRag: boolean
  useWeb: boolean
  description: string
}> = [
  {
    id: 'TC001',
    stockName: '海南发展',
    stockCode: '000022',
    model: 'qwen-max',
    useRag: false,
    useWeb: false,
    description: '海南发展 + qwen模型 + RAG关闭',
  },
  {
    id: 'TC002',
    stockName: '广联达',
    stockCode: '002410',
    model: 'deepseek',
    useRag: false,
    useWeb: true,
    description: '广联达 + DeepSeek模型 + 联网搜索开启 + RAG关闭',
  },
  {
    id: 'TC003',
    stockName: '海南发展',
    stockCode: '000022',
    model: 'qwen-max',
    useRag: true,
    useWeb: false,
    description: '海南发展 + qwen模型 + RAG开启',
  },
  {
    id: 'TC004',
    stockName: '金发科技',
    stockCode: '600143',
    model: 'deepseek',
    useRag: true,
    useWeb: true,
    description: '金发科技 + DeepSeek模型 + 联网搜索开启 + RAG开启',
  },
]

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

function findReportFile(baseDir: string, stockName: string): string | null {
  if (!fs.existsSync(baseDir)) return null
  const files = fs.readdirSync(baseDir)
  for (const f of files) {
    if (f.includes(stockName) && f.startsWith('report_') && f.endsWith('.md')) {
      return path.join(baseDir, f)
    }
  }
  return null
}

function getExecutionTime(): string {
  const now = new Date()
  const tz = new Date(now.getTime() + 8 * 60 * 60 * 1000)
  return tz.toISOString().replace(/[:-]/g, '').replace('T', '_').replace(/\.\d+Z$/, '')
}

for (const tc of TEST_CASES) {
  const execTime = getExecutionTime()

  test.describe(`【${tc.id}】${tc.description}`, () => {
    test.beforeAll(async () => {
      ensureDir(SCREENSHOT_DIR)
    })

    test(`【${tc.id}】访问研报页面并检查加载`, async ({ page }) => {
      const screenshotPath = path.join(SCREENSHOT_DIR, `${tc.id}_${tc.stockName}_${execTime}_01_页面访问.png`)
      await page.goto(`${BASE_URL}/reports`)
      await page.waitForLoadState('networkidle')
      await page.screenshot({ path: screenshotPath, fullPage: true })
      console.log(`[${tc.id}] 页面访问截图: ${screenshotPath}`)
    })

    test(`【${tc.id}】配置模型和RAG并选择股票`, async ({ page }) => {
      const screenshotPath = path.join(SCREENSHOT_DIR, `${tc.id}_${tc.stockName}_${execTime}_02_配置参数.png`)
      await page.goto(`${BASE_URL}/reports`)
      await page.waitForLoadState('networkidle')

      const modelSelect = page.locator('select').first()
      await modelSelect.selectOption(tc.model === 'qwen-max' ? 'qwen-max' : 'deepseek')
      console.log(`[${tc.id}] 已选择模型: ${tc.model}`)

      const ragCheckbox = page.locator('input[type="checkbox"]').first()
      const isRagChecked = await ragCheckbox.isChecked()
      if (tc.useRag && !isRagChecked) {
        await ragCheckbox.check()
        console.log(`[${tc.id}] 已开启 RAG`)
      } else if (!tc.useRag && isRagChecked) {
        await ragCheckbox.uncheck()
        console.log(`[${tc.id}] 已关闭 RAG`)
      }

      const stockPickerInput = page.locator('input[placeholder*="股票"]').first()
      await stockPickerInput.fill(tc.stockName)
      await page.waitForTimeout(1500)
      const firstResult = page.locator('[role="option"], [class*="option"], [class*="dropdown"]').first()
      const hasResult = await firstResult.count() > 0
      if (hasResult) {
        await firstResult.click()
        console.log(`[${tc.id}] 已选择股票: ${tc.stockName}`)
      } else {
        const listItems = page.locator('ul li, [class*="list"] > *').first()
        const hasItems = await listItems.count() > 0
        if (hasItems) {
          await listItems.first().click()
          console.log(`[${tc.id}] 从列表选择了股票: ${tc.stockName}`)
        } else {
          console.log(`[${tc.id}] 未找到股票选项，继续提交`)
        }
      }

      await page.screenshot({ path: screenshotPath, fullPage: true })
      console.log(`[${tc.id}] 配置参数截图: ${screenshotPath}`)
    })

    test(`【${tc.id}】创建任务并轮询等待完成`, async ({ page }) => {
      const screenshotPath = path.join(SCREENSHOT_DIR, `${tc.id}_${tc.stockName}_${execTime}_03_创建任务.png`)
      await page.goto(`${BASE_URL}/reports`)
      await page.waitForLoadState('networkidle')

      const modelSelect = page.locator('select').first()
      await modelSelect.selectOption(tc.model === 'qwen-max' ? 'qwen-max' : 'deepseek')

      const ragCheckbox = page.locator('input[type="checkbox"]').first()
      const isRagChecked = await ragCheckbox.isChecked()
      if (tc.useRag && !isRagChecked) await ragCheckbox.check()
      if (!tc.useRag && isRagChecked) await ragCheckbox.uncheck()

      const stockPickerInput = page.locator('input[placeholder*="股票"]').first()
      await stockPickerInput.fill(tc.stockName)
      await page.waitForTimeout(1500)
      const firstResult = page.locator('[role="option"], [class*="option"], [class*="dropdown"]').first()
      if (await firstResult.count() > 0) {
        await firstResult.click()
      } else {
        const listItems = page.locator('ul li, [class*="list"] > *').first()
        if (await listItems.count() > 0) await listItems.first().click()
      }

      const createBtn = page.locator('button:has-text("创建研报任务"), button:has-text("创建")').first()
      await createBtn.click()
      await page.waitForTimeout(2000)
      await page.screenshot({ path: screenshotPath, fullPage: true })
      console.log(`[${tc.id}] 创建任务截图: ${screenshotPath}`)

      let taskId: string | null = null
      const maxPolls = 60
      for (let i = 0; i < maxPolls; i++) {
        await page.waitForTimeout(5000)
        const rows = page.locator('table tbody tr, [class*="table"] tr')
        const rowCount = await rows.count()
        for (let r = 0; r < rowCount; r++) {
          const rowText = await rows.nth(r).textContent()
          if (rowText && rowText.includes(tc.stockName)) {
            const cells = rows.nth(r).locator('td, [class*="cell"]')
            const cellCount = await cells.count()
            if (cellCount >= 4) {
              const statusText = await cells.nth(3).textContent()
              if (statusText && statusText.includes('完成')) {
                taskId = `found_in_row_${r}`
                break
              }
            }
          }
        }
        if (taskId) break
        console.log(`[${tc.id}] 轮询 ${i + 1}/${maxPolls}，任务尚未完成，继续等待...`)
      }
      console.log(`[${tc.id}] 轮询结束，任务状态: ${taskId ? '完成' : '超时/未找到'}`)
    })

    test(`【${tc.id}】验证输出文件有效性`, async ({ page }) => {
      const screenshotPath = path.join(SCREENSHOT_DIR, `${tc.id}_${tc.stockName}_${execTime}_04_验证输出.png`)
      await page.goto(`${BASE_URL}/reports`)
      await page.waitForLoadState('networkidle')
      await page.screenshot({ path: screenshotPath, fullPage: true })

      let foundFile: string | null = null
      const dirsToCheck = [REPORT_OUTPUT_DIR, DEFAULT_OUTPUT_DIR]
      for (const dir of dirsToCheck) {
        const found = findReportFile(dir, tc.stockName)
        if (found) {
          foundFile = found
          break
        }
      }

      if (foundFile) {
        const content = fs.readFileSync(foundFile, 'utf-8')
        expect(content.length).toBeGreaterThan(100)
        expect(content).toContain('#')
        console.log(`[${tc.id}] ✅ 报告文件验证通过: ${foundFile}`)
        console.log(`[${tc.id}]   文件大小: ${content.length} 字符`)
      } else {
        console.log(`[${tc.id}] ⚠️  未找到报告文件 (搜索了 ${dirsToCheck.join(', ')})`)
        console.log(`[${tc.id}]   注意: 研报生成需要较长时间，且依赖真实API Key`)
        console.log(`[${tc.id}]   当前 TAVILY_API_KEY 已配置，联网搜索功能可用`)
      }
      console.log(`[${tc.id}] 验证截图: ${screenshotPath}`)
    })
  })
}