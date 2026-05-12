# AI量化投资系统 - 完整Bug列表

**项目名称**: AI量化投资系统  
**测试日期**: 2025-05-10  

---

## Bug提交清单

---

### BUG-001: 系统名称有误

**反馈编号**: 1  
**模块**:  所有前端
**问题类型**: 体验优化

严重程度**:   次要
**前置条件**: 打开网页http://localhost:5173/

**操作步骤**:

查看窗口标题

**实际结果**:  charles 控制台
**期望结果**: 招财猫-花花

**截图**:  ![image-20260510150445897](/Users/apple/Library/Application Support/typora-user-images/image-20260510150445897.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `backend/tests/test_bugfix_regressions.py::test_jobs_run_alias_exists` / `web/src/pages/__tests__/Chat.test.tsx`

---

### BUG-002: 采集任务-无法采集数据

**反馈编号**:2  
**模块**:  采集任务
**问题类型**: 功能缺陷  
**严重程度**:   严重
**前置条件**: 进入到采集模块

**操作步骤**:

1. 选择任一一种数据（行情信息、财务季报、新闻事件），点击运行

**实际结果**:  页面提示：not found，打开浏览器控制台发现报错“client.ts:13  POST http://localhost:5173/api/jobs/run 404 (Not Found)”
**期望结果**: 开始数据采集，运行完毕数据采集成功

**截图**:  ![image-20260510150534702](/Users/apple/Library/Application Support/typora-user-images/image-20260510150534702.png)![image-20260510150616637](/Users/apple/Library/Application Support/typora-user-images/image-20260510150616637.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `backend/tests/test_bugfix_regressions.py::test_jobs_run_alias_exists`

---

### BUG-003: 晨会简报模块 - MySQL错误暴露

**反馈编号**: 3  
**模块**: 晨会简报  
**问题类型**: 功能缺陷  
**严重程度**: 严重  
**前置条件**: 系统正常运行，数据库连接已配置  
**操作步骤**:

1. 进入晨会简报模块
2. 点击"生成简报"按钮
3. 查看生成结果

**实际结果**: 页面显示MySQL错误信息，暴露"表不存在"的数据库错误  
**期望结果**: 应显示友好的错误提示信息，不应暴露数据库内部错误  
**截图**: `bug11_briefing_db_error.png`  ![bug11_briefing_db_error](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/bug11_briefing_db_error.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `backend/tests/test_bugfix_regressions.py::test_console_morning_error_is_sanitized`

---

### BUG-004: AI对话模块 - JSON未格式化

**反馈编号**: 4  
**模块**: AI对话  
**问题类型**: 功能缺陷  
**严重程度**: 主要  
**前置条件**: 已进入AI对话页面  
**操作步骤**:

1. 进入AI对话模块
2. 向AI机器人提问
3. 查看AI回复内容

**实际结果**: AI回复显示原始JSON结构数据，用户难以阅读  
**期望结果**: AI回复应格式化为友好的文本展示，隐藏原始JSON结构  
**截图**: `bug15_ai_500_error.png`  ![bug15_ai_500_error](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/bug15_ai_500_error.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `web/src/pages/__tests__/Chat.test.tsx::Chat 对对象结果显示友好文本`

---

### BUG-005: 采集任务模块 - 路由404错误

**反馈编号**: 5  
**模块**: 采集任务  
**问题类型**: 功能缺陷  
**严重程度**: 主要  
**前置条件**: 已进入采集任务页面  
**操作步骤**:

1. 进入采集任务模块
2. 点击某个功能按钮或链接
3. 观察页面跳转

**实际结果**: 页面显示404错误，路由不存在（如/tasks、/briefing、/ai）  
**期望结果**: 页面应正确跳转到目标页面或显示合理提示（正确路由应为/jobs、/morning、/chat）  
**截图**: `bug02_tasks_404.png`  ![bug02_tasks_404](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/bug02_tasks_404.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `web/src/App.tsx` 路由兼容 + 页面联调

---

### BUG-006: 采集任务模块 - 任务历史Not Found

**反馈编号**: 6  
**模块**: 采集任务  
**问题类型**: 功能缺陷  
**严重程度**: 主要  
**前置条件**: 已创建并执行过采集任务  
**操作步骤**:

1. 进入采集任务模块
2. 找到已有任务
3. 点击"查看历史"按钮

**实际结果**: 页面显示"Not Found"错误  
**期望结果**: 应显示任务执行历史记录或合理的空状态提示  
**截图**: `bug03_task_view_click_notfound.![bug03_task_view_click_notfound](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/bug03_task_view_click_notfound.png)png`  
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `web/src/pages/Jobs.tsx` 历史记录联调 + `backend/tests/test_bugfix_regressions.py`

---

### BUG-007: 舆情监控模块 - 扫描自选股失败

**反馈编号**: 7  
**模块**: 舆情监控  
**问题类型**: 功能缺陷  
**严重程度**: 主要  
**前置条件**: 已设置自选股列表  
**操作步骤**:

1. 进入舆情监控模块
2. 点击"立即扫描自选股"按钮
3. 等待扫描结果

**实际结果**: 扫描失败，未返回任何结果或显示错误  
**期望结果**: 应成功扫描自选股舆情信息并展示结果  
**截图**: `14_sentiment_scan.png`  ![14_sentiment_scan](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/14_sentiment_scan.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `backend/tests/test_bugfix_regressions.py::test_sentiment_routes_exist_and_run`

---

### BUG-008: 采集任务模块 - cron格式解析异常

**反馈编号**: 8  
**模块**: 采集任务  
**问题类型**: 体验优化  
**严重程度**: 优化  
**前置条件**: 创建定时采集任务  
**操作步骤**:

1. 进入采集任务模块
2. 创建新任务，设置定时执行
3. 输入cron表达式（如"每天 0*:*/10"）

**实际结果**: cron格式解析异常，未给出明确的格式提示  
**期望结果**: 应提供cron格式说明或可视化cron配置界面，给出明确的错误提示  
**截图**: `bug04_cron_format.png`  ![bug04_cron_format](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/bug04_cron_format.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `web/src/pages/Jobs.tsx` cron 提示联调

---

### BUG-009: 执行监控模块 - 表单验证缺失

**反馈编号**: 9  
**模块**: 执行监控  
**问题类型**: 功能缺陷  
**严重程度**: 次要  
**前置条件**: 已进入执行监控页面，系统正常运行  
**操作步骤**:

1. 进入执行监控页面
2. 点击"新建策略"或"创建任务"按钮
3. 在股票代码输入框中不填写任何内容，保持为空
4. 点击"提交"或"确认"按钮

**实际结果**: 表单允许提交，未对空的股票代码字段进行验证提示  
**期望结果**: 股票代码为必填字段，提交时应触发前端校验，显示错误提示如"请输入股票代码"  
**截图**: `18_execution_empty_submit.png`  ![18_execution_empty_submit](/Users/apple/WorkBuddy/2026-05-10-task-2/screenshots/18_execution_empty_submit.png)
**复现概率**: 必现  
**状态**: 已关闭  
**修复版本**: v1.0.1  
**修复人**: AI编码助手  
**修复日期**: 2026-05-10  
**测试用例链接**: `web/src/pages/__tests__/Execution.test.tsx::Execution 股票代码为空时阻止提交`
