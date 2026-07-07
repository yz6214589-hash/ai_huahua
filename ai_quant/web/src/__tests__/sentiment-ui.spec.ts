import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5174';

test.describe('舆情监控 UI 测试', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/sentiment`);
    await page.waitForLoadState('networkidle');
  });

  test('3.1 页面加载 - 标题和区域可见', async ({ page }) => {
    // 确认页面没有 Not Found
    await expect(page.locator('body')).not.toContainText('Not Found');
    // 确认任务与调度区域可见
    await expect(page.getByText('任务与调度')).toBeVisible();
    // 确认手动分析股票区域可见
    await expect(page.getByText('手动分析股票')).toBeVisible();
    // 确认股票列表管理区域可见
    await expect(page.getByText('股票列表管理')).toBeVisible();
    // 确认监控结果区域可见
    await expect(page.getByText('监控结果')).toBeVisible();
    // 确认通知设置区域可见
    await expect(page.getByText('通知设置')).toBeVisible();
  });

  test('3.2 任务与调度 - 按钮可见', async ({ page }) => {
    // 调度状态按钮
    const toggleBtn = page.locator('button:has-text("已启用")');
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });
    // 立即扫描自选股按钮
    await expect(page.getByText('立即扫描自选股')).toBeVisible();
    // 定时配置按钮
    await expect(page.getByText('定时配置')).toBeVisible();
  });

  test('3.3 定时配置弹窗', async ({ page }) => {
    // 点击定时配置
    await page.getByText('定时配置').click();
    // 确认弹窗显示
    await expect(page.getByText('执行频率')).toBeVisible();
    // 确认频率下拉框
    const freqSelect = page.locator('select').first();
    const options = await freqSelect.locator('option').all();
    expect(options.length).toBe(5); // 每小时/每2小时/每4小时/每日/custom
    // 选择每2小时
    await freqSelect.selectOption('2h');
    // 点击保存
    await page.getByText('保存').click();
    // 确认弹窗关闭
    await expect(page.getByText('执行频率')).not.toBeVisible();
  });

  test('3.4 手动分析 - 组件可见', async ({ page }) => {
    // days 下拉框
    const daysSelect = page.locator('select').nth(1);
    await expect(daysSelect).toBeVisible();
    const daysOptions = await daysSelect.locator('option').all();
    expect(daysOptions.length).toBe(3); // 3/7/14
    // LLM 精检下拉框
    const llmSelect = page.locator('select').nth(2);
    await expect(llmSelect).toBeVisible();
    const llmOptions = await llmSelect.locator('option').all();
    expect(llmOptions.length).toBe(2); // 关闭/开启
  });

  test('3.5 股票列表管理', async ({ page }) => {
    // 确认显示股票数量
    const countText = page.locator('text=/\\d+只/');
    await expect(countText).toBeVisible({ timeout: 10000 });
    const count = await countText.textContent();
    expect(parseInt(count || '0')).toBeGreaterThan(0);
    // 确认股票列表中有条目
    const stockItems = page.locator('text=/\\d{6}/');
    const itemCount = await stockItems.count();
    expect(itemCount).toBeGreaterThan(0);
  });

  test('3.6 监控结果 - 三个 Tab', async ({ page }) => {
    // 三个 Tab
    await expect(page.getByText('事件列表')).toBeVisible();
    await expect(page.getByText('按股票分组')).toBeVisible();
    await expect(page.getByText('运行历史')).toBeVisible();
    // 默认显示事件列表
    const eventsTab = page.locator('button:has-text("事件列表")');
    await expect(eventsTab).toHaveClass(/bg-zinc-900/);
  });

  test('3.7 监控结果 - 事件列表有数据', async ({ page }) => {
    // 等待事件列表加载
    await page.waitForTimeout(3000);
    const eventsTab = page.locator('button:has-text("事件列表")');
    await eventsTab.click();
    // 检查事件列表行数
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();
    // 要么有数据要么显示占位提示
    if (rowCount === 1) {
      const cellText = await rows.first().textContent();
      expect(cellText).toMatch(/暂无舆情数据|加载中/);
    } else {
      expect(rowCount).toBeGreaterThan(0);
    }
  });

  test('3.8 监控结果 - 按股票分组', async ({ page }) => {
    await page.getByText('按股票分组').click();
    // 等待分组数据加载
    await page.waitForTimeout(2000);
    // 检查分组内容
    const groupCards = page.locator('text=/正:|负:|中:|共:/');
    const cardCount = await groupCards.count();
    if (cardCount === 0) {
      await expect(page.getByText('暂无数据')).toBeVisible();
    } else {
      expect(cardCount).toBeGreaterThan(0);
    }
  });

  test('3.9 监控结果 - 运行历史', async ({ page }) => {
    await page.getByText('运行历史').click();
    await page.waitForTimeout(2000);
    // 确认表格表头
    await expect(page.getByText('RunID')).toBeVisible();
    await expect(page.getByText('触发方式')).toBeVisible();
    await expect(page.getByText('创建时间')).toBeVisible();
    await expect(page.getByText('事件数')).toBeVisible();
    await expect(page.getByText('状态')).toBeVisible();
  });

  test('3.10 事件类型过滤', async ({ page }) => {
    await page.waitForTimeout(3000);
    // 找到事件类型下拉框
    const typeSelect = page.locator('select').filter({ hasText: /全部|利好|利空|政策/ }).first();
    const exists = await typeSelect.count();
    if (exists > 0) {
      await typeSelect.selectOption('利好');
      await page.waitForTimeout(1000);
      // 确认过滤生效
      const statusOk = await typeSelect.inputValue();
      expect(statusOk).toBe('利好');
    }
  });

  test('3.11 通知设置', async ({ page }) => {
    await expect(page.getByText('负面舆情通知')).toBeVisible();
    // 确认阈值下拉框
    const thresholdSelect = page.locator('select').filter({ hasText: /情感得分/ }).first();
    const exists = await thresholdSelect.count();
    if (exists > 0) {
      const options = await thresholdSelect.locator('option').all();
      expect(options.length).toBe(3);
    }
  });

  test('3.12 完整操作流程', async ({ page }) => {
    // 点击立即扫描自选股
    await page.getByText('立即扫描自选股').click();
    // 等待扫描完成
    await page.waitForTimeout(5000);
    // 确认事件列表有数据
    const eventsTab = page.locator('button:has-text("事件列表")');
    await eventsTab.click();
    // 切换到运行历史
    await page.getByText('运行历史').click();
    await page.waitForTimeout(2000);
    // 确认有新的运行记录
    const rows = page.locator('tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });
});
