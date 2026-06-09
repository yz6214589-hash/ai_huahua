import { test, expect } from '@playwright/test';
import * as fs from 'fs';

// 测试结果记录
interface TestResult {
  strategyId: string;
  strategyName: string;
  instanceCreated: boolean;
  instanceError?: string;
  backtestSuccess: boolean;
  backtestError?: string;
}

const results: TestResult[] = [];
const bugList: string[] = [];

test.describe('策略UI自动化测试', () => {
  test.beforeAll(async () => {
    console.log('开始策略UI自动化测试...');
  });

  test('获取策略列表并测试所有策略', async ({ page }) => {
    // 访问首页，然后导航到策略库
    await page.goto('http://localhost:5173/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 导航到策略库页面
    await page.goto('http://localhost:5173/strategy/library');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 获取策略列表
    const strategies = await page.evaluate(() => {
      const cards = document.querySelectorAll('.Card');
      const list: Array<{ id: string; name: string }> = [];
      cards.forEach((card) => {
        const title = card.querySelector('.CardHeader')?.textContent?.trim();
        if (title) {
          // 尝试从"创建实例"链接中获取strategy_id
          const createLink = card.querySelector('a[href*="strategy_id"]');
          if (createLink) {
            const href = createLink.getAttribute('href');
            const match = href?.match(/strategy_id=([^&]+)/);
            if (match) {
              list.push({ id: match[1], name: title });
            }
          }
        }
      });
      return list;
    });

    console.log(`找到 ${strategies.length} 种策略`);

    // 测试每个策略
    for (const strategy of strategies) {
      console.log(`\n===== 测试策略: ${strategy.name} =====`);
      const result: TestResult = {
        strategyId: strategy.id,
        strategyName: strategy.name,
        instanceCreated: false,
        backtestSuccess: false,
      };

      try {
        // 1. 创建策略实例
        console.log('步骤1: 创建策略实例...');
        await page.goto(`http://localhost:5173/strategy/instances?strategy_id=${strategy.id}`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);

        // 检查表单是否自动打开
        const formVisible = await page.isVisible('[data-testid="create-instance-form"]');
        if (!formVisible) {
          await page.click('button:has-text("新建实例")');
          await page.waitForTimeout(1000);
        }

        // 保存实例
        await page.click('button:has-text("保存实例")');
        await page.waitForTimeout(3000);

        result.instanceCreated = true;
        console.log('✓ 策略实例创建成功');

        // 2. 执行回测
        console.log('步骤2: 执行回测测试...');
        
        // 导航到回测页面
        await page.goto('http://localhost:5173/strategy/backtest');
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);

        // 选择"直接选策略"模式
        await page.check('input[type="radio"][value="strategy"]');
        await page.waitForTimeout(500);

        // 选择策略
        await page.selectOption('select', strategy.id);
        await page.waitForTimeout(500);

        // 选择批量回测模式
        await page.check('input[type="radio"][value="batch"]');
        await page.waitForTimeout(500);

        // 选择股票列表模式
        await page.check('input[type="radio"][value="list"]');
        await page.waitForTimeout(500);

        // 搜索并选择广联达
        console.log('选择股票: 广联达 (002410)...');
        const stockPicker = page.locator('.StockPicker').first();
        await stockPicker.click();
        await page.waitForTimeout(500);
        // 尝试输入股票代码
        const input = stockPicker.locator('input').first();
        await input.fill('002410');
        await page.waitForTimeout(1000);
        // 点击第一个搜索结果
        const firstResult = page.locator('.StockPicker-dropdown').first().locator('.StockPicker-option').first();
        if (await firstResult.isVisible()) {
          await firstResult.click();
          await page.waitForTimeout(500);
        }

        // 搜索并选择老凤祥
        console.log('选择股票: 老凤祥 (600612)...');
        await input.fill('600612');
        await page.waitForTimeout(1000);
        const secondResult = page.locator('.StockPicker-dropdown').first().locator('.StockPicker-option').first();
        if (await secondResult.isVisible()) {
          await secondResult.click();
          await page.waitForTimeout(500);
        }

        // 设置日期范围
        await page.fill('input[type="date"]', '2023-01-01');
        await page.waitForTimeout(300);
        const dateInputs = await page.locator('input[type="date"]').all();
        if (dateInputs.length >= 2) {
          await dateInputs[1].fill('2023-12-31');
        }

        // 点击批量回测按钮
        console.log('执行批量回测...');
        const runButtons = await page.locator('button:has-text("回测"),button:has-text("运行")').all();
        for (const btn of runButtons) {
          if (await btn.isVisible() && await btn.isEnabled()) {
            await btn.click();
            break;
          }
        }

        // 等待回测完成 (较长时间)
        await page.waitForTimeout(15000);

        // 检查是否有错误信息
        const errorElement = await page.locator('.bg-red-50, .text-red-600, .text-red-700').first();
        if (await errorElement.isVisible()) {
          const errorText = await errorElement.textContent();
          result.backtestError = errorText || '未知错误';
          bugList.push(`策略 ${strategy.name} 回测失败: ${errorText}`);
          console.log(`✗ 回测失败: ${errorText}`);
        } else {
          result.backtestSuccess = true;
          console.log('✓ 回测成功');
        }

      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        if (!result.instanceCreated) {
          result.instanceError = errorMsg;
          bugList.push(`策略 ${strategy.name} 创建实例失败: ${errorMsg}`);
        } else {
          result.backtestError = errorMsg;
          bugList.push(`策略 ${strategy.name} 回测出错: ${errorMsg}`);
        }
        console.log(`✗ 测试失败: ${errorMsg}`);
      }

      results.push(result);
      await page.waitForTimeout(2000);
    }
  });

  test.afterAll(async () => {
    // 生成测试报告
    const reportContent = generateTestReport();
    fs.writeFileSync('/Users/apple/Desktop/ai_huahua/ai_quant/test_report_ui.txt', reportContent, 'utf-8');
    console.log('\n===== 测试完成 =====');
    console.log(`测试报告已保存到: /Users/apple/Desktop/ai_huahua/ai_quant/test_report_ui.txt`);
    console.log(reportContent);
  });
});

function generateTestReport(): string {
  const successCount = results.filter(r => r.backtestSuccess).length;
  const totalCount = results.length;

  let report = `
=========================================
        25种策略UI自动化测试报告
=========================================
测试时间: ${new Date().toLocaleString('zh-CN')}

一、总体统计
=========================================
总策略数: ${totalCount}
成功回测: ${successCount}
失败回测: ${totalCount - successCount}
成功率: ${((successCount / totalCount) * 100).toFixed(1)}%

二、详细测试结果
=========================================
`;

  results.forEach((result, index) => {
    report += `
${index + 1}. ${result.strategyName} (${result.strategyId})
   实例创建: ${result.instanceCreated ? '✅ 成功' : '❌ 失败'}
   回测结果: ${result.backtestSuccess ? '✅ 成功' : '❌ 失败'}
   ${result.instanceError ? `实例错误: ${result.instanceError}` : ''}
   ${result.backtestError ? `回测错误: ${result.backtestError}` : ''}
`;
  });

  report += `
三、Bug 列表
=========================================
`;

  if (bugList.length === 0) {
    report += '✅ 未发现明显 Bug\n';
  } else {
    bugList.forEach((bug, index) => {
      report += `${index + 1}. ${bug}\n`;
    });
  }

  report += `
=========================================
            报告结束
=========================================
`;

  return report;
}
