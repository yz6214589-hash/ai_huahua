import { test } from '@playwright/test'

test('调试页面结构', async ({ page }) => {
  await page.goto('/strategy/backtest', { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForTimeout(3000)

  // 截图看看页面
  await page.screenshot({ path: 'test-results/debug_backtest.png', fullPage: true })

  // 获取页面文本内容
  const text = await page.evaluate(() => document.body.innerText)
  console.log('页面文本内容:')
  console.log(text.substring(0, 1000))

  // 检查 radio 按钮
  const radioInfo = await page.evaluate(() => {
    const radios = document.querySelectorAll('input[type="radio"]')
    return Array.from(radios).map(r => ({
      checked: (r as HTMLInputElement).checked,
      parentText: r.closest('label')?.textContent?.trim() || r.closest('div')?.textContent?.trim() || 'no parent text',
    }))
  })
  console.log('Radio 按钮状态:')
  radioInfo.forEach((r, i) => console.log(`  [${i}] checked=${r.checked} text="${r.parentText}"`))

  // 检查 select 下拉框
  const selectInfo = await page.evaluate(() => {
    const selects = document.querySelectorAll('select')
    return Array.from(selects).map(s => ({
      options: Array.from(s.options).map(o => ({ value: o.value, text: o.text })),
    }))
  })
  console.log('Select 下拉框:')
  selectInfo.forEach((s, i) => {
    console.log(`  Select [${i}]: ${s.options.length} 个选项`)
    s.options.slice(0, 5).forEach(o => console.log(`    - ${o.text} (${o.value})`))
    if (s.options.length > 5) console.log(`    ... 还有 ${s.options.length - 5} 个`)
  })
})
