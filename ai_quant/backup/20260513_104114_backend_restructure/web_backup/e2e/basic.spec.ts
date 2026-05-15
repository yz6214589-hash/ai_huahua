import { test, expect } from '@playwright/test'

test('watchlist page loads', async ({ page }) => {
  await page.goto('/watchlist')
  await expect(page.getByText('手动添加')).toBeVisible()
  await expect(page.getByText('自选股列表')).toBeVisible()
})

test('jobs page loads and can switch domain', async ({ page }) => {
  await page.goto('/jobs')
  await expect(page.getByText('任务列表')).toBeVisible()
  await expect(page.getByText('历史运行记录')).toBeVisible()
})

