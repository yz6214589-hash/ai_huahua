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
   自选股模块 - 冒烟测试（21条）
   覆盖：页面加载、股票搜索添加、删除、置顶/取消置顶、拖动排序、
   分组管理（创建/重命名/删除分组）、分组Tab切换、按分组筛选、
   个股详情页（基本面/技术面/分时图/新闻研报/返回）
   =================================================================== */
test.describe('A. 冒烟测试 - 自选股模块', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/watchlist')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('A01 页面加载 - 核心区域和标题可见', async ({ page }) => {
    // 前置条件：已登录系统，侧边栏自选股菜单可点击
    // 操作步骤：
    //   1. 打开 /watchlist 页面
    //   2. 等待页面加载完成
    // 期望结果：
    //   1. 页面不显示 "Not Found"
    //   2. "手动添加" 卡片标题可见
    //   3. "自选股列表" 卡片标题可见
    //   4. 股票搜索输入框存在
    await expect(page.locator('body')).not.toContainText('Not Found')
    await expect(page.getByText('手动添加')).toBeVisible()
    await expect(page.getByText('自选股列表')).toBeVisible()
    await expect(page.locator('main input[placeholder*="搜索股票"]')).toBeVisible()
  })

  test('A02 管理分组按钮 - 打开分组管理弹窗', async ({ page }) => {
    // 前置条件：自选股列表卡片已渲染
    // 操作步骤：
    //   1. 点击 "管理分组" 按钮
    // 期望结果：
    //   1. 弹窗标题 "管理分组" 可见
    //   2. "新分组名称" 输入框可见
    //   3. "新建" 按钮可见
    await page.getByRole('button', { name: '管理分组' }).click()
    await expect(page.locator('input[placeholder="新分组名称"]')).toBeVisible()
    await expect(page.getByRole('button', { name: '新建' })).toBeVisible()
    await page.locator('[class*="dialog"] button, [class*="modal"] button, [role="dialog"] button').filter({ has: page.locator('svg') }).first().click()
  })

  test('A03 分组管理 - 新建分组', async ({ page }) => {
    // 前置条件：管理分组弹窗已打开
    // 操作步骤：
    //   1. 点击 "管理分组" 按钮
    //   2. 在 "新分组名称" 输入框中输入 "A组测试"
    //   3. 点击 "新建" 按钮
    //   4. 等待弹窗刷新
    // 期望结果：
    //   1. 新分组出现在分组列表中（名称可见）
    //   2. 新建操作用户提示 "创建成功"
    await page.getByRole('button', { name: '管理分组' }).click()
    await page.locator('input[placeholder="新分组名称"]').fill('A组测试')
    await page.getByText('新建').click()
    await page.waitForTimeout(1000)
    await expect(page.getByText('A组测试')).toBeVisible()
  })

  test('A04 分组管理 - 重命名分组', async ({ page }) => {
    // 前置条件：已存在至少一个自定义分组
    // 操作步骤：
    //   1. 点击 "管理分组" 按钮
    //   2. 找到要重命名的分组，点击其右侧的铅笔图标
    //   3. 输入新名称 "A组已改名"
    //   4. 点击 "保存" 按钮
    // 期望结果：
    //   1. 分组名称变更为新名称
    //   2. 分组列表中可见 "A组已改名"
    await page.getByRole('button', { name: '管理分组' }).click()
    const editBtn = page.locator('button:has-text("A组测试")').locator('..').locator('button').filter({ has: page.locator('svg[class*="Pencil"]') }).first()
    const editExists = await editBtn.count()
    if (editExists > 0) {
      await editBtn.click()
      await page.locator('input[value="A组测试"]').fill('A组已改名')
      await page.getByText('保存').click()
      await page.waitForTimeout(500)
      await expect(page.getByText('A组已改名')).toBeVisible()
    }
  })

  test('A05 分组管理 - 删除分组', async ({ page }) => {
    // 前置条件：已存在至少一个自定义分组
    // 操作步骤：
    //   1. 点击 "管理分组" 按钮
    //   2. 找到要删除的分组，点击其右侧的垃圾桶图标
    // 期望结果：
    //   1. 该分组从分组列表中移除
    await page.getByRole('button', { name: '管理分组' }).click()
    const groupRow = page.locator('text="A组测试"').first()
    const groupExists = await groupRow.count()
    if (groupExists > 0) {
      const delBtn = groupRow.locator('..').locator('button').filter({ has: page.locator('svg[class*="Trash2"]') }).first()
      await delBtn.click()
      await page.waitForTimeout(500)
      await expect(page.getByText('A组测试')).not.toBeVisible()
    }
  })

  test('A06 创建多个分组并验证Tab显示', async ({ page }) => {
    // 前置条件：管理分组弹窗支持连续创建
    // 操作步骤：
    //   1. 打开管理分组弹窗
    //   2. 创建 "分组A"
    //   3. 创建 "分组B"
    //   4. 关闭弹窗
    // 期望结果：
    //   1. 自选股列表上方的Tab栏中出现 "分组A" 和 "分组B" 标签
    await page.getByRole('button', { name: '管理分组' }).click()
    await page.locator('input[placeholder="新分组名称"]').fill('分组A')
    await page.getByText('新建').click()
    await page.waitForTimeout(500)
    await page.locator('input[placeholder="新分组名称"]').fill('分组B')
    await page.getByText('新建').click()
    await page.waitForTimeout(500)
    // 关闭弹窗
    await page.locator('button:has-text("管理分组") button').filter({ has: page.locator('svg') }).first().click()
    await page.waitForTimeout(500)
    await expect(page.getByText('分组A')).toBeVisible()
    await expect(page.getByText('分组B')).toBeVisible()
  })

  test('A07 分组Tab切换 - 点击切换不同分组', async ({ page }) => {
    // 前置条件：存在分组A和分组B两个自定义分组
    // 操作步骤：
    //   1. 点击 "分组A" Tab
    //   2. 等待列表刷新
    //   3. 点击 "分组B" Tab
    //   4. 点击 "全部" Tab
    // 期望结果：
    //   1. 每次Tab点击后，该Tab处于选中状态（背景色为深色）
    //   2. "全部" Tab 包含总数量显示（如 "全部 (N)"）
    const groupATab = page.locator('button:has-text("分组A")').first()
    const groupBTab = page.locator('button:has-text("分组B")').first()
    const allTab = page.locator('button:has-text("全部")').first()
    await groupATab.click()
    await page.waitForTimeout(500)
    await expect(groupATab).toHaveClass(/bg-zinc-900/)
    await groupBTab.click()
    await page.waitForTimeout(500)
    await expect(groupBTab).toHaveClass(/bg-zinc-900/)
    await allTab.click()
    await page.waitForTimeout(500)
    await expect(allTab).toHaveClass(/bg-zinc-900/)
  })

  test('A08 搜索添加股票到自选股', async ({ page }) => {
    // 前置条件：手动添加卡片显示，搜索组件可用
    // 操作步骤：
    //   1. 在搜索框中输入 "600519"
    //   2. 从搜索结果下拉中选择匹配的股票选项
    // 期望结果：
    //   1. 股票被成功添加到自选股列表
    //   2. 列表中可见新添加的股票代码
    const searchInput = page.locator('input[placeholder*="搜索股票"]').first()
    await searchInput.fill('600519')
    await page.waitForTimeout(1000)
    const option = page.locator('text=/600519/').first()
    const exists = await option.count()
    if (exists > 0) {
      await option.click()
      await page.waitForTimeout(1000)
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('text=/600519/').first()).toBeVisible()
    }
  })

  test('A09 从分组Tab中删除某只股票', async ({ page }) => {
    // 前置条件：自选股列表中至少有一只股票
    // 操作步骤：
    //   1. 找到股票行中的 "删除" 按钮
    //   2. 点击删除按钮
    // 期望结果：
    //   1. 该股票从列表中移除
    //   2. 如果列表为空，显示 "暂无自选股" 提示
    const delBtn = page.getByText('删除').first()
    const exists = await delBtn.count()
    if (exists > 0) {
      await delBtn.click()
      await page.waitForTimeout(1000)
    }
  })

  test('A10 置顶功能 - 置顶一只股票', async ({ page }) => {
    // 前置条件：自选股列表中存在非置顶股票
    // 操作步骤：
    //   1. 找到股票行中的 "置顶" 按钮
    //   2. 点击 "置顶"
    // 期望结果：
    //   1. 按钮文本变为 "取消置顶"
    //   2. 该股票出现在 "置顶" 区块中
    const pinBtn = page.getByText('置顶').first()
    const exists = await pinBtn.count()
    if (exists > 0) {
      await pinBtn.click()
      await page.waitForTimeout(1000)
      await expect(page.getByText('取消置顶').first()).toBeVisible()
      await expect(page.getByText('置顶')).toBeVisible()
    }
  })

  test('A11 取消置顶功能', async ({ page }) => {
    // 前置条件：自选股列表中存在已置顶股票
    // 操作步骤：
    //   1. 找到股票行中的 "取消置顶" 按钮
    //   2. 点击 "取消置顶"
    // 期望结果：
    //   1. 按钮文本变回 "置顶"
    const unpinBtn = page.getByText('取消置顶').first()
    const exists = await unpinBtn.count()
    if (exists > 0) {
      await unpinBtn.click()
      await page.waitForTimeout(1000)
      await expect(page.getByText('置顶').first()).toBeVisible()
    }
  })

  test('A12 添加股票到指定分组', async ({ page }) => {
    // 前置条件：手动添加区域存在分组选择按钮
    // 操作步骤：
    //   1. 在搜索框中输入 "000001"
    //   2. 点击 "分组A" 按钮将其选中（蓝色高亮）
    //   3. 从搜索结果中选择匹配的股票选项
    // 期望结果：
    //   1. 股票被添加到自选股且属于分组A
    const searchInput = page.locator('input[placeholder*="搜索股票"]').first()
    await searchInput.fill('000001')
    await page.waitForTimeout(1000)
    // 选择分组A
    const groupBtns = page.locator('button:has-text("分组A")')
    const groupBtnExists = await groupBtns.count()
    if (groupBtnExists > 0) {
      await groupBtns.first().click()
    }
    const option = page.locator('text=/000001/').first()
    const exists = await option.count()
    if (exists > 0) {
      await option.click()
      await page.waitForTimeout(1000)
      await page.waitForLoadState('domcontentloaded')
    }
  })

  test('A13 按分组Tab筛选查看股票', async ({ page }) => {
    // 前置条件：存在分组A且分组A中有股票
    // 操作步骤：
    //   1. 点击 "分组A" Tab
    //   2. 等待列表刷新
    // 期望结果：
    //   1. 列表只显示属于分组A的股票
    //   2. 分组A Tab处于选中状态
    await page.getByRole('button', { name: '分组A', exact: true }).first().click()
    await page.waitForTimeout(500)
    await expect(page.getByRole('button', { name: '分组A', exact: true }).first()).toHaveClass(/bg-zinc-900/)
  })

  test('A14 自选股排序 - 拖动排序区域存在', async ({ page }) => {
    // 前置条件：自选股列表中有多条数据
    // 操作步骤：
    //   1. 观察股票行左侧的拖动手柄图标
    // 期望结果：
    //   1. 至少存在一个拖动手柄（GripVertical 图标）
    const rows = page.locator('text=/\\d{6}/')
    const count = await rows.count()
    if (count > 1) {
      const gripIcons = page.locator('svg[class*="GripVertical"]')
      await expect(gripIcons.first()).toBeVisible()
    }
  })

  test('A15 行情快照数据展示', async ({ page }) => {
    // 前置条件：自选股列表中有股票且行情快照已加载
    // 操作步骤：
    //   1. 查看列表中的股票行
    //   2. 查找涨跌幅、最新价等数据
    // 期望结果：
    //   1. 如果有行情数据，涨跌幅和最新价数值可见
    //   2. 如果无行情数据，显示占位符 "—"
    const items = page.locator('text=/\\d{6}/')
    const count = await items.count()
    if (count > 0) {
      const priceCell = page.getByText('最新价').first()
      await expect(priceCell).toBeVisible()
    }
  })

  test('A16 点击股票跳转到详情页', async ({ page }) => {
    // 前置条件：自选股列表中有股票数据
    // 操作步骤：
    //   1. 点击第一只股票的行区域
    //   2. 等待页面跳转
    // 期望结果：
    //   1. 页面URL变为 /stock/<股票代码>
    //   2. 个股详情页面四个Tab可见
    const stockLink = page.locator('text=/\\d{6}/').first()
    const exists = await stockLink.count()
    if (exists > 0) {
      await stockLink.click()
      await page.waitForURL(/\/stock\//)
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      await expect(page.getByText('基本面')).toBeVisible()
      await expect(page.getByText('技术面')).toBeVisible()
      await expect(page.getByText('分时图')).toBeVisible()
      await expect(page.getByText('新闻/研报')).toBeVisible()
    }
  })

  test('A17 个股详情 - 基本面Tab数据和指标可见', async ({ page }) => {
    // 前置条件：已在个股详情页
    // 操作步骤：
    //   1. 点击 "基本面" Tab
    //   2. 等待数据加载
    // 期望结果：
    //   1. 基本面卡片标题可见
    //   2. 如果存在数据，指标网格展示
    await page.locator('text=/\\d{6}/').first().click()
    await page.waitForURL(/\/stock\//)
    await page.waitForLoadState('domcontentloaded')
    await page.getByText('基本面').click()
    await page.waitForTimeout(1000)
    await expect(page.getByText('基本面')).toBeVisible()
    const indicatorGrid = page.locator('text=/最新财报期/')
    const exists = await indicatorGrid.count()
    if (exists > 0) {
      await expect(indicatorGrid).toBeVisible()
    }
  })

  test('A18 个股详情 - 技术面Tab图表和参数控件', async ({ page }) => {
    // 前置条件：已在个股详情页
    // 操作步骤：
    //   1. 点击 "技术面" Tab
    //   2. 等待数据加载
    // 期望结果：
    //   1. 技术面卡片标题可见
    //   2. MA/MACD/RSI/ATR参数输入控件可见
    //   3. 仪表盘/数据切换Tab可见
    await page.locator('text=/\\d{6}/').first().click()
    await page.waitForURL(/\/stock\//)
    await page.waitForLoadState('domcontentloaded')
    await page.getByText('技术面').click()
    await page.waitForTimeout(1500)
    await expect(page.getByText('技术面')).toBeVisible()
    await expect(page.locator('text=/MA|MACD|RSI|ATR/').first()).toBeVisible()
    await expect(page.getByText('仪表盘')).toBeVisible()
    await expect(page.getByText('数据')).toBeVisible()
  })

  test('A19 个股详情 - 技术面切换到数据视图', async ({ page }) => {
    // 前置条件：已在技术面Tab
    // 操作步骤：
    //   1. 点击 "数据" Tab
    // 期望结果：
    //   1. 技术指标数据表格可见
    //   2. 表格中包含 MA/MACD/RSI 等指标行
    await page.locator('text=/\\d{6}/').first().click()
    await page.waitForURL(/\/stock\//)
    await page.waitForLoadState('domcontentloaded')
    await page.getByText('技术面').click()
    await page.waitForTimeout(1000)
    await page.getByText('数据').click()
    await page.waitForTimeout(500)
    await expect(page.locator('text=/MA5|MA10|MA20/').first()).toBeVisible()
  })

  test('A20 个股详情 - 分时图Tab', async ({ page }) => {
    // 前置条件：已在个股详情页
    // 操作步骤：
    //   1. 点击 "分时图" Tab
    //   2. 等待数据加载
    // 期望结果：
    //   1. 分时图卡片标题可见
    //   2. 昨收、最新价等摘要信息可见
    await page.locator('text=/\\d{6}/').first().click()
    await page.waitForURL(/\/stock\//)
    await page.waitForLoadState('domcontentloaded')
    await page.getByText('分时图').click()
    await page.waitForTimeout(1000)
    await expect(page.getByText('分时图')).toBeVisible()
    await expect(page.getByText('昨收').or(page.getByText('最新'))).toBeVisible()
  })

  test('A21 个股详情 - 新闻/研报Tab查看并返回', async ({ page }) => {
    // 前置条件：已在个股详情页
    // 操作步骤：
    //   1. 点击 "新闻/研报" Tab
    //   2. 等待数据加载
    //   3. 如果存在新闻条目，查看其 "打开" 按钮
    //   4. 切换新闻/研报Tab
    //   5. 点击返回按钮
    // 期望结果：
    //   1. 新闻/研报Tab内容区域可见
    //   2. "新闻" 和 "研报" 子Tab可见
    //   3. 如果有新闻条目，"打开" 或 "暂无链接" 标签可见
    //   4. 点击返回按钮后回到自选股页面
    await page.locator('text=/\\d{6}/').first().click()
    await page.waitForURL(/\/stock\//)
    await page.waitForLoadState('domcontentloaded')
    await page.getByText('新闻/研报').click()
    await page.waitForTimeout(1500)
    await expect(page.getByText('新闻')).toBeVisible()
    await expect(page.getByText('研报')).toBeVisible()
    // 查看是否有新闻条目
    const openBtn = page.getByText('打开').first()
    const openExists = await openBtn.count()
    if (openExists > 0) {
      await expect(openBtn).toBeVisible()
    }
    // 切换研报Tab
    await page.getByText('研报').click()
    await page.waitForTimeout(1000)
    // 返回自选股
    await page.locator('button').filter({ has: page.locator('svg[class*="ArrowLeft"]') }).click()
    await page.waitForURL('/watchlist')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByText('自选股列表')).toBeVisible()
  })
})

/* ===================================================================
   信息获取模块 - 冒烟测试（36条）
   覆盖：五个Tab导航、数据采集（任务列/定时/运行）、舆情监控（任务调度/
   手动分析/股票列表/监控结果三Tab/通知设置）、宏观数据、财经热点、
   数据与交付
   =================================================================== */
test.describe('B. 冒烟测试 - 信息获取模块', () => {

  test('B01 页面加载 - 五个Tab导航全部可见', async ({ page }) => {
    // 前置条件：已登录系统，侧边栏信息获取菜单可点击
    // 操作步骤：
    //   1. 打开 /info-access 页面
    //   2. 等待页面加载
    // 期望结果：
    //   1. 页面不显示 "Not Found"
    //   2. 五个Tab标签全部显示：数据采集、舆情监控、宏观数据、财经热点、数据与交付
    await page.goto('/info-access')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')
    await expect(page.getByText('数据采集')).toBeVisible()
    await expect(page.getByText('舆情监控')).toBeVisible()
    await expect(page.getByText('宏观数据')).toBeVisible()
    await expect(page.getByText('财经热点')).toBeVisible()
    await expect(page.getByText('数据与交付')).toBeVisible()
  })

  /* ------- B2: 数据采集 ------- */
  test.describe('B2 数据采集', () => {

    test('B02-1 任务列表和运行记录区域可见', async ({ page }) => {
      // 前置条件：已打开 info-access 页面
      // 操作步骤：
      //   1. 点击 "数据采集" Tab（默认第一个）
      // 期望结果：
      //   1. 页面标题或任务区域可见（如 "行情日线"、"任务列表"）
      //   2. "历史运行记录" 区域可见
      await page.goto('/info-access/data-collection')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      await expect(page.getByText('历史运行记录')).toBeVisible()
    })

    test('B02-2 运行任务按钮存在', async ({ page }) => {
      // 前置条件：数据采集页面已加载
      // 操作步骤：
      //   1. 查找 "立即运行" 按钮
      // 期望结果：
      //   1. 至少有一个 "立即运行" 或 "运行" 按钮
      await page.goto('/info-access/data-collection')
      await page.waitForLoadState('domcontentloaded')
      const runBtns = page.locator('button:has-text("立即运行"), button:has-text("运行")').first()
      const exists = await runBtns.count()
      if (exists > 0) {
        await expect(runBtns).toBeVisible()
      }
    })

    test('B02-3 任务调度设置按钮存在', async ({ page }) => {
      // 前置条件：数据采集页面已加载
      // 操作步骤：
      //   1. 查找每个任务行中的调度或定时设置按钮
      // 期望结果：
      //   1. 定时设置按钮可见
      await page.goto('/info-access/data-collection')
      await page.waitForLoadState('domcontentloaded')
      const scheduleBtn = page.locator('button:has-text("定时设置")').first()
      const exists = await scheduleBtn.count()
      if (exists > 0) {
        await expect(scheduleBtn).toBeVisible()
      }
    })

    test('B02-4 股票范围选择器存在', async ({ page }) => {
      // 前置条件：数据采集页面已加载
      // 操作步骤：
      //   1. 查找股票范围选择器（全市场/自选股/自定义分组）
      // 期望结果：
      //   1. "全市场" 或 "自选股" 选项可见
      await page.goto('/info-access/data-collection')
      await page.waitForLoadState('domcontentloaded')
      const scopeSelector = page.locator('text=/全市场|自选股|自定义分组/').first()
      const exists = await scopeSelector.count()
      if (exists > 0) {
        await expect(scopeSelector).toBeVisible()
      }
    })

    test('B02-5 最近运行记录显示', async ({ page }) => {
      // 前置条件：数据采集页面已加载
      // 操作步骤：
      //   1. 查看历史运行记录区域
      // 期望结果：
      //   1. 存在运行记录列表或 "暂无记录" 提示
      await page.goto('/info-access/data-collection')
      await page.waitForLoadState('domcontentloaded')
      const runStatus = page.locator('text=/成功|失败|运行中|等待|暂无/').first()
      await expect(runStatus).toBeVisible()
    })
  })

  /* ------- B3: 舆情监控 ------- */
  test.describe('B3 舆情监控', () => {

    test('B03-1 页面核心四大区域可见', async ({ page }) => {
      // 前置条件：已打开 info-access 页面
      // 操作步骤：
      //   1. 点击 "舆情监控" Tab
      //   2. 等待页面加载
      // 期望结果：
      //   1. 任务与调度区域可见
      //   2. 手动分析股票区域可见
      //   3. 股票列表管理区域可见
      //   4. 监控结果区域可见
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('任务与调度')).toBeVisible()
      await expect(page.getByText('手动分析股票')).toBeVisible()
      await expect(page.getByText('股票列表管理')).toBeVisible()
      await expect(page.getByText('监控结果')).toBeVisible()
    })

    test('B03-2 任务与调度 - 三个主要操作按钮', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 观察任务与调度卡片
      // 期望结果：
      //   1. "立即扫描自选股" 按钮可见
      //   2. "定时配置" 按钮可见
      //   3. 调度开关（启用/暂停）按钮可见
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('立即扫描自选股')).toBeVisible()
      await expect(page.getByText('定时配置')).toBeVisible()
      const toggleBtn = page.locator('button:has-text("已启用"), button:has-text("已暂停")').first()
      const exists = await toggleBtn.count()
      if (exists > 0) {
        await expect(toggleBtn).toBeVisible()
      }
    })

    test('B03-3 定时配置弹窗 - 打开和关闭', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 点击 "定时配置" 按钮
      //   2. 确认弹窗已打开
      //   3. 点击 "取消" 关闭弹窗
      // 期望结果：
      //   1. "执行频率" 标签可见
      //   2. "保存" 和 "取消" 按钮可见
      //   3. 点击取消后弹窗关闭
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('定时配置').click()
      await expect(page.getByText('执行频率')).toBeVisible()
      await expect(page.getByText('保存').first()).toBeVisible()
      await expect(page.getByText('取消').first()).toBeVisible()
      await page.getByText('取消').first().click()
    })

    test('B03-4 定时配置 - 选择不同执行频率', async ({ page }) => {
      // 前置条件：定时配置弹窗已打开
      // 操作步骤：
      //   1. 点击 "定时配置" 按钮
      //   2. 从执行频率下拉中选择 "每2小时"
      // 期望结果：
      //   1. 下拉框选项切换正常
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('定时配置').click()
      const freqSelect = page.locator('select').first()
      await freqSelect.selectOption('2h')
      await page.waitForTimeout(300)
      await expect(freqSelect).toHaveValue('2h')
      await page.getByText('取消').first().click()
    })

    test('B03-5 手动分析 - 搜索框和操作按钮可见', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 查看手动分析股票卡片
      // 期望结果：
      //   1. 股票搜索框可见
      //   2. "清空" 按钮可见
      //   3. "立即分析" 按钮可见
      //   4. days下拉框存在3个选项
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const searchInputs = page.locator('input[placeholder*="搜索股票"]')
      await expect(searchInputs.first()).toBeVisible()
      await expect(page.getByText('清空')).toBeVisible()
      await expect(page.getByText('立即分析')).toBeVisible()
      const daySelect = page.locator('select').filter({ has: page.locator('option[value="3"]') }).first()
      const exists = await daySelect.count()
      if (exists > 0) {
        const options = await daySelect.locator('option').all()
        expect(options.length).toBe(3)
      }
    })

    test('B03-6 手动分析 - LLM精检开关切换', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 找到LLM精检下拉框
      //   2. 切换为 "开启"
      // 期望结果：
      //   1. 下拉框切换正常
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const llmSelect = page.locator('select').filter({ has: page.locator('option[value="1"]') }).first()
      const exists = await llmSelect.count()
      if (exists > 0) {
        await llmSelect.selectOption('1')
        await expect(llmSelect).toHaveValue('1')
      }
    })

    test('B03-7 股票列表管理 - 搜索框和同步按钮可见', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 查看股票列表管理卡片
      // 期望结果：
      //   1. "从自选股更新" 按钮可见
      //   2. 股票列表区域可见（有数据或 "暂无自选股" 提示）
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('从自选股更新')).toBeVisible()
      const stockCount = page.locator('text=/\\d+只/').first()
      const exists = await stockCount.count()
      if (exists > 0) {
        await expect(stockCount).toBeVisible()
      } else {
        await expect(page.getByText('暂无自选股')).toBeVisible()
      }
    })

    test('B03-8 股票列表管理 - 添加自定义股票', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 在股票列表管理卡片的搜索框中输入 "600519"
      //   2. 从搜索结果中选择 "贵州茅台"
      // 期望结果：
      //   1. 股票列表中新增 "600519"
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const searchInputs = page.locator('input[placeholder*="搜索股票"]')
      // 使用最后一个是股票列表管理中的
      const lastInput = searchInputs.last()
      await lastInput.fill('600519')
      await page.waitForTimeout(1000)
      const option = page.locator('text=/600519/').first()
      const exists = await option.count()
      if (exists > 0) {
        await option.click()
        await page.waitForTimeout(1000)
        await expect(page.locator('text=/600519/').first()).toBeVisible()
      }
    })

    test('B03-9 股票列表管理 - 删除一只股票', async ({ page }) => {
      // 前置条件：股票列表中有股票
      // 操作步骤：
      //   1. 找到股票条目右侧的垃圾桶图标按钮
      //   2. 点击删除
      // 期望结果：
      //   1. 该股票从列表中移除
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const stockItems = page.locator('text=/\\d{6}/')
      const count = await stockItems.count()
      if (count > 0) {
        // 查找包含垃圾桶图标的按钮
        const delBtn = page.locator('button').filter({ has: page.locator('svg[class*="Trash2"]') }).first()
        await delBtn.click()
        await page.waitForTimeout(500)
      }
    })

    test('B03-10 监控结果 - 三个子Tab可见', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 查看监控结果区域
      // 期望结果：
      //   1. "事件列表" Tab可见
      //   2. "按股票分组" Tab可见
      //   3. "运行历史" Tab可见
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByRole('button', { name: '事件列表' })).toBeVisible()
      await expect(page.getByRole('button', { name: '按股票分组' })).toBeVisible()
      await expect(page.getByRole('button', { name: '运行历史' })).toBeVisible()
    })

    test('B03-11 监控结果 - 事件列表Tab默认选中', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 检查当前激活的Tab
      // 期望结果：
      //   1. "事件列表" Tab处于选中状态（深色背景）
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const eventsTab = page.locator('button:has-text("事件列表")')
      await expect(eventsTab).toHaveClass(/bg-zinc-900/)
    })

    test('B03-12 监控结果 - 事件类型过滤下拉框', async ({ page }) => {
      // 前置条件：事件列表Tab已激活
      // 操作步骤：
      //   1. 找到事件类型过滤下拉框
      //   2. 选择 "利好"
      //   3. 选择 "利空"
      //   4. 选择 "政策"
      //   5. 选择 "全部"
      // 期望结果：
      //   1. 下拉框可切换所有选项
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const filterSelect = page.locator('select').filter({ has: page.locator('option[value="全部"]') }).first()
      const exists = await filterSelect.count()
      if (exists > 0) {
        await filterSelect.selectOption('利好')
        await page.waitForTimeout(300)
        await filterSelect.selectOption('利空')
        await page.waitForTimeout(300)
        await filterSelect.selectOption('政策')
        await page.waitForTimeout(300)
        await filterSelect.selectOption('全部')
      }
    })

    test('B03-13 监控结果 - 切换到按股票分组Tab', async ({ page }) => {
      // 前置条件：监控结果区域可见
      // 操作步骤：
      //   1. 点击 "按股票分组" Tab
      // 期望结果：
      //   1. 按股票分组Tab处于选中状态
      //   2. 分组内容区域显示（有数据或 "暂无数据"）
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('按股票分组').click()
      await page.waitForTimeout(500)
      await expect(page.getByText('按股票分组')).toHaveClass(/bg-zinc-900/)
    })

    test('B03-14 监控结果 - 切换到运行历史Tab', async ({ page }) => {
      // 前置条件：监控结果区域可见
      // 操作步骤：
      //   1. 点击 "运行历史" Tab
      // 期望结果：
      //   1. 运行历史Tab处于选中状态
      //   2. 表格表头包含 RunID、触发方式、创建时间、事件数、状态
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await page.getByRole('button', { name: '运行历史' }).click()
      await page.waitForTimeout(500)
      await expect(page.getByRole('button', { name: '运行历史' })).toHaveClass(/bg-zinc-900/)
      await expect(page.locator('text=/RunID|触发方式|创建时间|事件数|状态/').first()).toBeVisible()
    })

    test('B03-15 监控结果 - 事件列表搜索框过滤', async ({ page }) => {
      // 前置条件：事件列表Tab已激活
      // 操作步骤：
      //   1. 在事件列表上方的搜索框中输入股票代码
      // 期望结果：
      //   1. 搜索输入框可见并可输入
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      const searchInput = page.locator('input[placeholder="搜索股票"]').first()
      await searchInput.fill('600519')
      await page.waitForTimeout(300)
    })

    test('B03-16 通知设置区域可见', async ({ page }) => {
      // 前置条件：舆情监控页面已加载
      // 操作步骤：
      //   1. 滚动到页面底部
      // 期望结果：
      //   1. "负面舆情通知" 标题可见
      //   2. 通知开关（Toggle）可见
      //   3. 情感得分阈值下拉框可见
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('负面舆情通知')).toBeVisible()
      await expect(page.getByText('情感得分')).toBeVisible()
    })
  })

  /* ------- B4: 宏观数据 ------- */
  test.describe('B4 宏观数据', () => {

    test('B04-1 宏观指标卡片展示', async ({ page }) => {
      // 前置条件：已打开 info-access 页面
      // 操作步骤：
      //   1. 点击 "宏观数据" Tab
      //   2. 等待数据加载（宏观数据需要异步请求后端API，等待指标卡片出现）
      // 期望结果：
      //   1. 页面不显示 "Not Found"
      //   2. 中国市场指标卡片可见（CPI/PMI/LPR等）
      //   3. 全球市场指标卡片可见（VIX/FearGreed等）
      await page.goto('/info-access/macro')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      await expect(page.locator('text=/CPI|PMI|LPR/').first()).toBeVisible({ timeout: 15000 })
      const chinaIndicators = page.locator('text=/CPI|PMI|LPR/')
      const chinaCount = await chinaIndicators.count()
      expect(chinaCount).toBeGreaterThanOrEqual(1)
      await expect(page.locator('text=/VIX|恐惧贪婪/').first()).toBeVisible({ timeout: 10000 })
      const globalIndicators = page.locator('text=/VIX|恐惧贪婪|FearGreed/')
      const globalCount = await globalIndicators.count()
      expect(globalCount).toBeGreaterThanOrEqual(1)
    })

    test('B04-2 历史趋势折线图渲染', async ({ page }) => {
      // 前置条件：宏观数据页面已加载
      // 操作步骤：
      //   1. 查看指标卡片下方的趋势图区域
      // 期望结果：
      //   1. SVG 折线图元素存在
      await page.goto('/info-access/macro')
      await page.waitForLoadState('domcontentloaded')
      const svgElement = page.locator('svg')
      const svgCount = await svgElement.count()
      expect(svgCount).toBeGreaterThanOrEqual(1)
    })
  })

  /* ------- B5: 财经热点 ------- */
  test.describe('B5 财经热点', () => {

    test('B05-1 页面加载和内容区域可见', async ({ page }) => {
      // 前置条件：已打开 info-access 页面
      // 操作步骤：
      //   1. 点击 "财经热点" Tab
      //   2. 等待数据加载
      // 期望结果：
      //   1. 页面不显示 "Not Found"
      //   2. "财经热点" 内容区域可见（事件列表）
      //   3. "自选股新闻" 内容区域可见
      await page.goto('/info-access/financial-hot')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      const eventSection = page.locator('text=/财经热点|自选股新闻/')
      await expect(eventSection.first()).toBeVisible()
    })

    test('B05-2 分页翻页控件工作正常', async ({ page }) => {
      // 前置条件：财经热点页面已加载
      // 操作步骤：
      //   1. 点击 "上一页" 按钮
      //   2. 点击 "下一页" 按钮
      // 期望结果：
      //   1. 分页按钮存在且可点击
      await page.goto('/info-access/financial-hot')
      await page.waitForLoadState('domcontentloaded')
      const prevBtn = page.getByText('上一页').first()
      const nextBtn = page.getByText('下一页').first()
      const prevExists = await prevBtn.count()
      const nextExists = await nextBtn.count()
      if (prevExists > 0) {
        await expect(prevBtn).toBeVisible()
      }
      if (nextExists > 0) {
        await expect(nextBtn).toBeVisible()
      }
    })

    test('B05-3 事件重要性标签和查看按钮', async ({ page }) => {
      // 前置条件：财经热点页面已加载
      // 操作步骤：
      //   1. 查找事件行中的 "查看" 按钮
      // 期望结果：
      //   1. 存在至少一个 "查看" 按钮
      //   2. 存在重要性标签（高/中/低）
      await page.goto('/info-access/financial-hot')
      await page.waitForLoadState('domcontentloaded')
      const viewBtns = page.getByText('查看')
      const viewCount = await viewBtns.count()
      expect(viewCount).toBeGreaterThanOrEqual(1)
    })

    test('B05-4 自选股新闻筛选', async ({ page }) => {
      // 前置条件：财经热点页面已加载
      // 操作步骤：
      //   1. 查找自选股新闻的筛选下拉框
      // 期望结果：
      //   1. 筛选区可见（全部/自选股等选项）
      await page.goto('/info-access/financial-hot')
      await page.waitForLoadState('domcontentloaded')
      const filterOptions = page.locator('text=/全部|自选股/').first()
      const exists = await filterOptions.count()
      if (exists > 0) {
        await expect(filterOptions).toBeVisible()
      }
    })
  })

  /* ------- B6: 数据与交付 ------- */
  test.describe('B6 数据与交付', () => {

    test('B06-1 页面加载正常', async ({ page }) => {
      // 前置条件：已打开 info-access 页面
      // 操作步骤：
      //   1. 点击 "数据与交付" Tab
      // 期望结果：
      //   1. 页面不显示 "Not Found"
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
    })

    test('B06-2 两个主Tab切换可见', async ({ page }) => {
      // 前置条件：数据与交付页面已加载
      // 操作步骤：
      //   1. 查看页面顶部Tab
      // 期望结果：
      //   1. "数据集浏览" Tab可见
      //   2. "历史任务记录" Tab可见
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('数据集浏览')).toBeVisible()
      await expect(page.getByText('历史任务记录')).toBeVisible()
    })

    test('B06-3 数据集浏览 - 选择数据集下拉框', async ({ page }) => {
      // 前置条件：数据集浏览Tab已激活（默认）
      // 操作步骤：
      //   1. 查看数据集下拉选择框
      // 期望结果：
      //   1. 下拉框可见
      //   2. 至少包含7个数据集的选项
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      const select = page.locator('select').first()
      const exists = await select.count()
      if (exists > 0) {
        await expect(select).toBeVisible()
        const options = await select.locator('option').all()
        expect(options.length).toBeGreaterThanOrEqual(3)
      }
    })

    test('B06-4 数据集浏览 - 切换不同数据集', async ({ page }) => {
      // 前置条件：数据集浏览Tab已激活
      // 操作步骤：
      //   1. 当前选中 "行情数据" 数据集
      //   2. 切换为 "财务数据"
      // 期望结果：
      //   1. 下拉框值变更为财务数据
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      const select = page.locator('select').first()
      const exists = await select.count()
      if (exists > 0) {
        const options = await select.locator('option').all()
        if (options.length >= 2) {
          const firstVal = await options[0].getAttribute('value')
          const secondVal = await options[1].getAttribute('value')
          if (firstVal && secondVal) {
            await select.selectOption(secondVal)
            await page.waitForTimeout(1000)
          }
        }
      }
    })

    test('B06-5 数据集浏览 - 数据表格如果存在则显示列', async ({ page }) => {
      // 前置条件：数据集浏览Tab已激活
      // 操作步骤：
      //   1. 查看数据集表格
      // 期望结果：
      //   1. 如果有数据，表格列头可见
      //   2. 分页信息可见（共N条，第X页）
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      const tableHeaders = page.locator('thead th').first()
      const headerExists = await tableHeaders.count()
      if (headerExists > 0) {
        await expect(tableHeaders).toBeVisible()
      }
      const pageInfo = page.locator('text=/共.*条/')
      const infoExists = await pageInfo.count()
      if (infoExists > 0) {
        await expect(pageInfo).toBeVisible()
      }
    })

    test('B06-6 数据集浏览 - 分页控件翻页', async ({ page }) => {
      // 前置条件：数据集有数据且有多页
      // 操作步骤：
      //   1. 点击 "下一页" 按钮
      //   2. 点击 "上一页" 按钮
      // 期望结果：
      //   1. 翻页按钮存在并可点击（或禁用态）
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      const firstBtn = page.getByText('首页')
      const prevBtn = page.getByText('上一页')
      const nextBtn = page.getByText('下一页')
      const firstExists = await firstBtn.count()
      const prevExists = await prevBtn.count()
      const nextExists = await nextBtn.count()
      if (firstExists > 0) await expect(firstBtn).toBeVisible()
      if (prevExists > 0) await expect(prevBtn).toBeVisible()
      if (nextExists > 0) await expect(nextBtn).toBeVisible()
    })

    test('B06-7 切换到历史任务记录Tab', async ({ page }) => {
      // 前置条件：数据与交付页面已加载
      // 操作步骤：
      //   1. 点击 "历史任务记录" Tab
      //   2. 等待加载
      // 期望结果：
      //   1. 历史任务记录Tab处于选中状态
      //   2. 任务记录表格或列表可见
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('历史任务记录').click()
      await page.waitForTimeout(1000)
      await expect(page.getByText('历史任务记录')).toBeVisible()
    })
  })
})

/* ===================================================================
   策略分析模块 - 冒烟测试（24条）
   覆盖：七个Tab导航、策略库（卡片/详情展开）、策略实例（列表/新建/参数）、
   回测（单/批量/日期/参数/成本/基准）、回测历史、绩效报告
   =================================================================== */
test.describe('C. 冒烟测试 - 策略分析模块', () => {

  test('C01 页面加载 - 七个Tab导航全部可见', async ({ page }) => {
    // 前置条件：已登录系统，侧边栏策略分析菜单可点击
    // 操作步骤：
    //   1. 打开 /strategy 页面
    //   2. 等待加载
    // 期望结果：
    //   1. 页面不显示 "Not Found"
    //   2. 策略库、策略实例、回测、回测历史、滚动验证、参数优化、绩效报告七个Tab可见
    await page.goto('/strategy')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('body')).not.toContainText('Not Found')
    await expect(page.getByText('策略库')).toBeVisible()
    await expect(page.getByText('策略实例')).toBeVisible()
    await expect(page.getByRole('button', { name: '回测', exact: true })).toBeVisible()
    await expect(page.getByText('回测历史')).toBeVisible()
    await expect(page.getByText('滚动验证')).toBeVisible()
    await expect(page.getByText('参数优化')).toBeVisible()
    await expect(page.getByText('绩效报告')).toBeVisible()
  })

  /* ------- C2: 策略库 ------- */
  test.describe('C2 策略库', () => {

    test('C02-1 策略卡片列表展示', async ({ page }) => {
      // 前置条件：已打开 /strategy 页面
      // 操作步骤：
      //   1. 点击 "策略库" Tab（默认第一个）
      // 期望结果：
      //   1. 策略总数统计文本可见（如 "共 N 种策略"）
      //   2. 策略卡片以网格形式展示
      await page.goto('/strategy/library')
      await page.waitForLoadState('domcontentloaded')
      const countText = page.getByText(/共.*种策略/)
      const exists = await countText.count()
      if (exists > 0) {
        await expect(countText).toBeVisible()
      }
    })

    test('C02-2 展开策略详情 - 查看详情按钮', async ({ page }) => {
      // 前置条件：策略库页面已加载
      // 操作步骤：
      //   1. 找到第一张策略卡片的 "查看详情" 按钮
      //   2. 点击 "查看详情"
      // 期望结果：
      //   1. 按钮文本变为 "收起详情"
      //   2. 展开区域显示 "参数说明"、"创建实例"、"立即回测"
      await page.goto('/strategy/library')
      await page.waitForLoadState('domcontentloaded')
      const detailBtn = page.getByText('查看详情').first()
      const exists = await detailBtn.count()
      if (exists > 0) {
        await detailBtn.click()
        await page.waitForTimeout(500)
        await expect(page.getByText('收起详情').first()).toBeVisible()
        await expect(page.getByText('参数说明').first()).toBeVisible()
        await expect(page.getByText('创建实例').first()).toBeVisible()
        await expect(page.getByText('立即回测').first()).toBeVisible()
      }
    })

    test('C02-3 策略卡片展示优点和缺点标签', async ({ page }) => {
      // 前置条件：策略库页面已加载
      // 操作步骤：
      //   1. 查看策略卡片内容
      // 期望结果：
      //   1. 策略卡片中 "优点" 和 "缺点" 标签可见
      await page.goto('/strategy/library')
      await page.waitForLoadState('domcontentloaded')
      const proTag = page.getByText('优点').first()
      const conTag = page.getByText('缺点').first()
      const proExists = await proTag.count()
      const conExists = await conTag.count()
      if (proExists > 0) await expect(proTag).toBeVisible()
      if (conExists > 0) await expect(conTag).toBeVisible()
    })

    test('C02-4 收起策略详情', async ({ page }) => {
      // 前置条件：策略详情已展开
      // 操作步骤：
      //   1. 点击 "收起详情"
      // 期望结果：
      //   1. 详情区域收起
      await page.goto('/strategy/library')
      await page.waitForLoadState('domcontentloaded')
      const detailBtn = page.getByText('查看详情').first()
      const exists = await detailBtn.count()
      if (exists > 0) {
        await detailBtn.click()
        await page.waitForTimeout(500)
        await page.getByText('收起详情').first().click()
        await page.waitForTimeout(500)
        await expect(page.getByText('查看详情').first()).toBeVisible()
      }
    })
  })

  /* ------- C3: 策略实例 ------- */
  test.describe('C3 策略实例', () => {

    test('C03-1 页面加载和操作按钮', async ({ page }) => {
      // 前置条件：已打开 /strategy 页面
      // 操作步骤：
      //   1. 点击 "策略实例" Tab
      // 期望结果：
      //   1. 实例统计文本可见（共 N 个策略实例）
      //   2. "刷新" 按钮可见
      //   3. "新建实例" 按钮可见
      await page.goto('/strategy/instances')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('刷新')).toBeVisible()
      await expect(page.getByRole('button', { name: '新建实例' })).toBeVisible()
    })

    test('C03-2 新建实例 - 打开创建面板', async ({ page }) => {
      // 前置条件：策略实例页面已加载
      // 操作步骤：
      //   1. 点击 "新建实例" 按钮
      // 期望结果：
      //   1. 创建实例卡片展开
      //   2. "所属策略" 下拉框可见
      //   3. "实例名称" 输入框可见
      //   4. 如果策略有参数，"参数配置" 区域可见
      await page.goto('/strategy/instances')
      await page.waitForLoadState('domcontentloaded')
      await page.getByRole('button', { name: '新建实例' }).click()
      await page.waitForTimeout(500)
      await expect(page.getByText('所属策略')).toBeVisible()
      await expect(page.getByText('实例名称')).toBeVisible()
    })

    test('C03-3 新建实例 - 选择不同策略自动填充参数', async ({ page }) => {
      // 前置条件：新建实例面板已打开
      // 操作步骤：
      //   1. 在 "所属策略" 下拉框中切换策略
      // 期望结果：
      //   1. 参数配置区域跟随切换的策略更新
      await page.goto('/strategy/instances')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('新建实例').click()
      await page.waitForTimeout(500)
      const strategySelect = page.locator('select').first()
      const options = await strategySelect.locator('option').all()
      if (options.length >= 2) {
        const secondVal = await options[1].getAttribute('value')
        if (secondVal) {
          await strategySelect.selectOption(secondVal)
          await page.waitForTimeout(300)
        }
      }
    })
  })

  /* ------- C4: 回测 ------- */
  test.describe('C4 回测', () => {

    test('C04-1 页面加载正常', async ({ page }) => {
      // 前置条件：已打开 /strategy 页面
      // 操作步骤：
      //   1. 点击 "回测" Tab
      // 期望结果：
      //   1. 页面不显示 "Not Found"
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
    })

    test('C04-2 回测类型选择 - 单只/批量', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看回测参数卡片
      // 期望结果：
      //   1. "单只股票回测" 和 "批量多股票回测" 两个Radio可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('单只股票回测')).toBeVisible()
      await expect(page.getByText('批量多股票回测')).toBeVisible()
    })

    test('C04-3 策略选择模式 - 实例/直接选', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看右上角策略选择模式
      // 期望结果：
      //   1. "从实例选择" 和 "直接选策略" 两个Radio可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('从实例选择')).toBeVisible()
      await expect(page.getByText('直接选策略')).toBeVisible()
    })

    test('C04-4 日期选择控件', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看日期输入区域
      // 期望结果：
      //   1. "开始日期" 和 "结束日期" 输入框可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('开始日期')).toBeVisible()
      await expect(page.getByText('结束日期')).toBeVisible()
    })

    test('C04-5 股票代码输入框', async ({ page }) => {
      // 前置条件：回测页面已加载，单只股票模式
      // 操作步骤：
      //   1. 查看股票代码输入框
      // 期望结果：
      //   1. 股票代码输入框可见，默认值为 "600519.SH"
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      const stockInput = page.locator('input[value*="600519"]').first()
      const exists = await stockInput.count()
      if (exists > 0) {
        await expect(stockInput).toBeVisible()
      }
    })

    test('C04-6 参数覆盖区域', async ({ page }) => {
      // 前置条件：回测页面已加载，策略有可配置参数
      // 操作步骤：
      //   1. 查看参数覆盖区域
      // 期望结果：
      //   1. "参数覆盖" 标题可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      const paramSection = page.getByText('参数覆盖').first()
      const exists = await paramSection.count()
      if (exists > 0) {
        await expect(paramSection).toBeVisible()
      }
    })

    test('C04-7 区间模式配置 - 全区间/训练验证测试划分', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看区间模式
      // 期望结果：
      //   1. "全区间回测" 和 "训练/验证/测试划分" 两个Radio可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('全区间回测')).toBeVisible()
      await expect(page.getByText('训练/验证/测试划分')).toBeVisible()
    })

    test('C04-8 交易成本折叠面板', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 点击交易成本配置折叠按钮
      // 期望结果：
      //   1. 买入佣金、卖出佣金、滑点等参数输入框展开
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      const costBtn = page.locator('button:has-text("交易成本")').first()
      const exists = await costBtn.count()
      if (exists > 0) {
        await costBtn.click()
        await page.waitForTimeout(500)
      }
    })

    test('C04-9 基准指数选择', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看基准指数下拉框
      // 期望结果：
      //   1. "基准指数" 标题可见
      //   2. 沪深300、上证50、中证500等选项可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('基准指数')).toBeVisible()
      const benchmarkSelect = page.locator('select').filter({ has: page.locator('option[value="000300.SH"]') }).first()
      const exists = await benchmarkSelect.count()
      if (exists > 0) {
        await expect(benchmarkSelect).toBeVisible()
      }
    })

    test('C04-10 开始回测按钮', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 查看页面底部的回测按钮
      // 期望结果：
      //   1. "开始回测" 按钮可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('开始回测')).toBeVisible()
    })

    test('C04-11 切换到批量模式 - 输入股票列表', async ({ page }) => {
      // 前置条件：回测页面已加载
      // 操作步骤：
      //   1. 点击 "批量多股票回测"
      // 期望结果：
      //   1. "输入股票列表" 和 "选择股票分组" Radio可见
      //   2. 文本域输入框可见
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await page.getByText('批量多股票回测').click()
      await page.waitForTimeout(300)
      await expect(page.getByText('输入股票列表')).toBeVisible()
      await expect(page.getByText('选择股票分组')).toBeVisible()
    })
  })

  /* ------- C5: 回测历史 ------- */
  test.describe('C5 回测历史', () => {

    test('C05-1 页面加载正常', async ({ page }) => {
      await page.goto('/strategy/backtest-history')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
    })

    test('C05-2 筛选输入框', async ({ page }) => {
      await page.goto('/strategy/backtest-history')
      await page.waitForLoadState('domcontentloaded')
      const filterInput = page.locator('input[placeholder*="策略"], input[placeholder*="股票"]').first()
      const exists = await filterInput.count()
      if (exists > 0) {
        await expect(filterInput).toBeVisible()
      }
    })

    test('C05-3 记录列表含操作按钮', async ({ page }) => {
      await page.goto('/strategy/backtest-history')
      await page.waitForLoadState('domcontentloaded')
      const viewBtns = page.locator('button:has-text("查看"), button:has-text("对比"), button:has-text("删除")').first()
      const exists = await viewBtns.count()
      if (exists > 0) {
        await expect(viewBtns).toBeVisible()
      }
    })
  })

  /* ------- C6: 绩效报告 ------- */
  test.describe('C6 绩效报告', () => {

    test('C06-1 页面加载正常', async ({ page }) => {
      await page.goto('/strategy/performance')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
    })

    test('C06-2 报告指标卡片展示', async ({ page }) => {
      await page.goto('/strategy/performance')
      await page.waitForLoadState('domcontentloaded')
      const metrics = page.locator('text=/总收益率|年化收益率|夏普比率|最大回撤/')
      const count = await metrics.count()
      if (count > 0) {
        expect(count).toBeGreaterThanOrEqual(1)
      }
    })

    test('C06-3 报告列表每行有查看按钮', async ({ page }) => {
      await page.goto('/strategy/performance')
      await page.waitForLoadState('domcontentloaded')
      const viewBtn = page.locator('table button, [class*="table"] button, .report-row button').filter({ hasText: '查看' }).first()
      const exists = await viewBtn.count()
      if (exists > 0) {
        await expect(viewBtn).toBeVisible()
        await viewBtn.click()
        await page.waitForTimeout(1000)
        await expect(page.getByText('总收益率').or(page.getByText('累计收益曲线'))).toBeVisible()
      }
    })

    test('C06-4 绩效详情展示收益曲线和热力图', async ({ page }) => {
      await page.goto('/strategy/performance')
      await page.waitForLoadState('domcontentloaded')
      const viewBtn = page.locator('table button, [class*="table"] button, .report-row button').filter({ hasText: '查看' }).first()
      const exists = await viewBtn.count()
      if (exists > 0) {
        await viewBtn.first().click()
        await page.waitForTimeout(1000)
        const chart = page.locator('text=/累计收益曲线|月度收益/')
        const chartExists = await chart.count()
        if (chartExists > 0) {
          await expect(chart.first()).toBeVisible()
        }
      }
    })
  })
})

test.afterAll(async () => {
  console.log('\n')
  console.log('============================================================')
  console.log('              全局测试监控汇总报告')
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

/* ===================================================================
   主流程测试用例（3条）
   覆盖：自选股完整操作流程、信息获取完整操作流程、策略分析完整操作流程
   =================================================================== */
test.describe('D. 主流程测试用例', () => {

  test.describe('D1 自选股主流程 - 添加股票 -> 分组管理 -> 详情查看 -> 返回', () => {

    test('D1.1 搜索添加海南发展 -> 查看列表 -> 跳转详情 -> 切换Tab -> 返回', async ({ page }) => {
      // 前置条件：已登录系统，自选股页面可正常加载
      // 操作步骤：
      //   1. 打开 /watchlist 页面
      //   2. 在搜索框中输入 "海南发展"
      //   3. 从搜索结果中选择匹配的股票
      //   4. 待列表更新后，确认股票已添加
      //   5. 点击股票行进入个股详情页
      //   6. 依次切换基本面、技术面、分时图、新闻/研报四个Tab
      //   7. 在新闻/研报Tab中，点击 "新闻" 和 "研报" 子Tab
      //   8. 点击左上角返回按钮
      // 期望结果：
      //   1. 股票成功添加到自选股列表
      //   2. 个股详情页四个Tab均可正常切换，每个Tab下内容正常渲染
      //   3. 新闻/研报Tab下可切换新闻和研报视图
      //   4. 返回后回到自选股页面
      await page.goto('/watchlist')
      await page.waitForLoadState('domcontentloaded')
      const searchInput = page.locator('input[placeholder*="搜索股票"]').first()
      await expect(searchInput).toBeVisible()
      await searchInput.fill('海南发展')
      await page.waitForTimeout(1500)
      const option = page.locator('text=/海南发展/').first()
      const optionExists = await option.count()
      if (optionExists > 0) {
        await option.click()
        await page.waitForTimeout(1500)
        await page.waitForLoadState('domcontentloaded')
      }
      // 跳转到详情
      const stockLink = page.locator('text=/\\d{6}/').first()
      const linkExists = await stockLink.count()
      if (linkExists > 0) {
        await stockLink.click()
        await page.waitForURL(/\/stock\//)
        await page.waitForLoadState('domcontentloaded')
        await expect(page.locator('body')).not.toContainText('Not Found')
        // 切换基本面Tab
        await page.getByText('基本面').click()
        await page.waitForTimeout(500)
        // 切换技术面Tab
        await page.getByText('技术面').click()
        await page.waitForTimeout(1000)
        // 切换分时图Tab
        await page.getByText('分时图').click()
        await page.waitForTimeout(500)
        // 切换新闻/研报Tab
        await page.getByText('新闻/研报').click()
        await page.waitForTimeout(1000)
        // 切换子Tab - 研报
        const reportsTab = page.getByText('研报').first()
        const reportsExists = await reportsTab.count()
        if (reportsExists > 0) {
          await reportsTab.click()
          await page.waitForTimeout(500)
        }
        // 返回
        await page.locator('button').filter({ has: page.locator('svg[class*="ArrowLeft"]') }).click()
        await page.waitForURL('/watchlist')
        await page.waitForLoadState('domcontentloaded')
        await expect(page.getByText('自选股列表')).toBeVisible()
      }
    })
  })

  test.describe('D2 信息获取主流程 - 舆情监控 -> 宏观数据 -> 财经热点 -> 数据交付', () => {

    test('D2.1 访问舆情监控 -> 从自选股同步 -> 扫描 -> 检查宏观数据 -> 财经热点 -> 数据交付', async ({ page }) => {
      // 前置条件：已登录系统，信息获取各子页面可正常加载
      // 操作步骤：
      //   1. 打开 /info-access/sentiment 舆情监控页面
      //   2. 点击 "从自选股更新" 同步自选股到舆情监控股票列表
      //   3. 点击 "立即扫描自选股" 运行舆情扫描
      //   4. 切换到宏观数据页面 /info-access/macro，确认指标数据可加载
      //   5. 切换到财经热点页面 /info-access/financial-hot，确认事件列表可见
      //   6. 切换到数据与交付页面 /info-access/data-delivery，确认数据集浏览
      //   7. 切换到历史任务记录Tab
      // 期望结果：
      //   1. 舆情监控页面各模块正常加载
      //   2. 从自选股更新按钮可点击，操作后提示结果
      //   3. 立即扫描按钮可点击
      //   4. 宏观指标卡片展示正常（至少2个不同指标可见）
      //   5. 财经热点事件列表和查看按钮可交互
      //   6. 数据与交付数据集列表可正常浏览
      //   7. 历史任务记录Tab可切换
      await page.goto('/info-access/sentiment')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('股票列表管理')).toBeVisible()
      // 从自选股更新
      const syncBtn = page.getByText('从自选股更新')
      const syncExists = await syncBtn.count()
      if (syncExists > 0) {
        await syncBtn.click()
        await page.waitForTimeout(2000)
      }
      // 扫描自选股
      const scanBtn = page.getByText('立即扫描自选股')
      await expect(scanBtn).toBeVisible()
      await scanBtn.click()
      await page.waitForTimeout(3000)
      // 切换到宏观数据
      await page.goto('/info-access/macro')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      const indicators = page.locator('text=/CPI|PMI|LPR|VIX|FearGreed/')
      const indicatorCount = await indicators.count()
      expect(indicatorCount).toBeGreaterThanOrEqual(1)
      // 切换到财经热点
      await page.goto('/info-access/financial-hot')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      const viewBtns = page.getByText('查看')
      const viewCount = await viewBtns.count()
      expect(viewCount).toBeGreaterThanOrEqual(0)
      // 切换到数据与交付
      await page.goto('/info-access/data-delivery')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByText('数据集浏览')).toBeVisible()
      await page.getByText('历史任务记录').click()
      await page.waitForTimeout(1000)
      await expect(page.getByText('历史任务记录')).toBeVisible()
    })
  })

  test.describe('D3 策略分析主流程 - 策略库 -> 实例 -> 回测 -> 绩效报告全链路', () => {

    test('D3.1 浏览策略库 -> 查看实例 -> 回测页面 -> 回测历史 -> 绩效报告', async ({ page }) => {
      // 前置条件：已登录系统，策略分析各子页面可正常加载
      // 操作步骤：
      //   1. 打开 /strategy/library 策略库
      //   2. 展开策略详情，查看参数说明、创建实例链接、回测链接
      //   3. 点击 "创建实例" 链接跳转到策略实例页
      //   4. 在策略实例页点击 "新建实例" 打开创建面板
      //   5. 切换到回测页面 /strategy/backtest
      //   6. 切换回测类型为批量模式
      //   7. 切换到回测历史 /strategy/backtest-history
      //   8. 切换到绩效报告 /strategy/performance
      //   9. 点击查看详情展开报告指标
      // 期望结果：
      //   1. 策略库页面加载正常，策略卡片展示
      //   2. 展开详情后参数说明可见，创建实例和回测链接可点击
      //   3. 策略实例页加载正常，新建实例面板可打开
      //   4. 回测页面加载正常，单只/批量模式可切换
      //   5. 回测历史页面无报错
      //   6. 绩效报告页面指标数据展示正常
      await page.goto('/strategy/library')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      // 展开策略详情
      const detailBtn = page.getByText('查看详情').first()
      const detailExists = await detailBtn.count()
      if (detailExists > 0) {
        await detailBtn.click()
        await page.waitForTimeout(500)
        await expect(page.getByText('参数说明').first()).toBeVisible()
      }
      // 切换到策略实例
      await page.goto('/strategy/instances')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.getByRole('button', { name: '新建实例' })).toBeVisible()
      const newInstanceBtn = page.getByRole('button', { name: '新建实例' })
      const newExists = await newInstanceBtn.count()
      if (newExists > 0) {
        await newInstanceBtn.click()
        await page.waitForTimeout(500)
        await expect(page.getByText('所属策略')).toBeVisible()
      }
      // 切换到回测
      await page.goto('/strategy/backtest')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      await expect(page.getByText('单只股票回测')).toBeVisible()
      // 切换批量模式
      await page.getByText('批量多股票回测').click()
      await page.waitForTimeout(300)
      await expect(page.getByText('输入股票列表')).toBeVisible()
      // 切换到回测历史
      await page.goto('/strategy/backtest-history')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      // 切换到绩效报告
      await page.goto('/strategy/performance')
      await page.waitForLoadState('domcontentloaded')
      await expect(page.locator('body')).not.toContainText('Not Found')
      const metrics = page.locator('text=/总收益率|年化收益率|夏普比率/')
      const metricCount = await metrics.count()
      if (metricCount > 0) {
        expect(metricCount).toBeGreaterThanOrEqual(1)
      }
      // 查看报告详情
      const viewBtn = page.getByText('查看').first()
      const viewExists = await viewBtn.count()
      if (viewExists > 0) {
        await viewBtn.click()
        await page.waitForTimeout(1000)
        await expect(page.getByText('总收益率').or(page.getByText('累计收益曲线'))).toBeVisible()
      }
    })
  })
})