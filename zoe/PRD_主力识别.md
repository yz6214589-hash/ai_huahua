# 主力识别（主力行为识别）需求文档 & 交互流程

## 1. 背景与目标

Zoe 作为“数字员工分析师”，当前已具备信号计算、选股、回测、绩效分析等能力。为进一步提升“行为解释能力”，新增“主力识别”功能：用户可以手动选择股票代码/公司，创建主力识别任务，系统基于高频行为特征输出“更像散户 / 更像做市 / 更像拆单执行”的识别结果与解释材料。

参考实现：复用课程脚本 [7-主力行为识别.py](file:///Users/apple/Desktop/ai_huahua/week10/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260418/CASE-%E5%9F%BA%E4%BA%8ERL%E7%9A%84%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5/7-%E4%B8%BB%E5%8A%9B%E8%A1%8C%E4%B8%BA%E8%AF%86%E5%88%AB.py)（TickDataGenerator / extract_features / RandomForestClassifier / 可视化输出）。

本期目标：
- 在 Zoe 控制台新增“主力识别”入口
- 支持手动创建任务（股票代码/公司名）
- 一键运行任务并生成结果：识别标签 + 概率/置信度 + 关键特征解释 + 图表
- 任务可被列表查看、可再次运行、可打开报告/产物

非目标（本期不做）：
- 自动抓取逐笔成交/盘口（真实 tick）数据（若后续接入，再扩展“真实数据模式”）
- 多用户权限体系

## 2. 核心概念

### 2.1 主力识别任务（MainForce Task）

任务用于记录用户选择的目标与运行参数，并保存运行结果产物。

字段建议：
- task_id：字符串（uuid 或自增）
- stock_code：字符串（如 600519.SH）
- company_name：字符串（可选）
- mode：字符串（本期默认 “simulated”）
- params：object（n_samples_per_class、seed、n_ticks、window 等）
- status：pending / running / done / failed
- created_at / updated_at
- result：object（latest run 的摘要）
- artifacts：object（图表路径、报告 URL）

### 2.2 两类输出

1) 任务列表/详情页可直接阅读的摘要：
- 识别结论：散户交易 / RL 做市 / RL 拆单
- 指标摘要：测试集准确率（脚本里 train/test acc）、关键特征 TopN
- 解释：从特征角度给出“为什么更像某类行为”

2) 可下载/可打开的产物：
- 混淆矩阵图
- 特征雷达图
- 特征重要性图
- 典型行为模式图
- （可选）HTML 报告页（复用 Zoe 的 /reports 输出机制）

## 3. 功能范围

### 3.1 创建任务

用户在页面选择：
- 股票代码 stock_code（必填）
- 公司名称 company_name（可选）
- 运行参数（可选，提供默认值）：
  - n_samples_per_class（默认 200）
  - seed（默认 42）
  - n_ticks（默认 300）
  - window（默认 50）

点击「创建任务」后：
- 任务写入本地 JSON 存储（沿用 Zoe 的 presets/instances 方案）
- 返回 task_id 并在列表可见

### 3.2 运行任务

任务运行触发方式：
- 在任务详情页点击「运行」
- 或在任务列表点击「运行」

运行步骤（复用脚本逻辑）：
- 构建模拟数据集（build_dataset）
- 训练随机森林分类器（RandomForestClassifier）
- 输出指标（train_acc/test_acc、classification_report、confusion_matrix）
- 生成图表文件（plot_feature_radar / plot_typical_patterns / plot_confusion_matrix / plot_feature_importance）
- 汇总 result（关键字段）并落盘 artifacts

### 3.3 查看结果

页面展示：
- 最新一次运行状态与时间
- 识别结论（可用 badge）
- test_acc / train_acc
- 关键特征 TopN（重要性）
- 图表预览（图片）+ 下载链接
- 报告链接（若生成 HTML）

### 3.4 删除任务

支持删除任务记录（可选是否连同产物目录一起删除，默认只删任务记录不清产物，避免误删）。

## 4. 页面与交互流程

### 4.1 导航入口

顶部导航新增：主力识别（/mainforce）

### 4.2 交互流程（典型）

1. 用户进入 /mainforce
2. 在“创建任务”卡片中输入 stock_code / company_name（可选）与参数（可选）
3. 点击「创建任务」
4. 任务出现在“任务列表”
5. 点击任务的「运行」
6. 运行完成后，列表展示状态 done，并提供“查看”
7. 进入详情页展示图表与结论；可点击“重新运行”

异常提示：
- stock_code 为空：提示必填
- 训练/绘图失败：任务状态 failed，展示错误信息

## 5. 后端 API（拟定）

### 5.1 任务管理

- GET /api/v1/mainforce/tasks
  - Response：tasks: [{task_id, stock_code, company_name, status, updated_at, result_summary}]

- POST /api/v1/mainforce/tasks
  - Request：{stock_code, company_name?, params?}
  - Response：{task_id}

- GET /api/v1/mainforce/tasks/{task_id}
  - Response：task: {...完整字段...}

- DELETE /api/v1/mainforce/tasks/{task_id}
  - Response：{deleted: task_id}

### 5.2 运行

- POST /api/v1/mainforce/tasks/{task_id}/run
  - Response：
    - status: done/failed
    - result: {label, train_acc, test_acc, feature_importance_top, report_url?, images?}

## 6. 存储结构（建议）

沿用 Zoe 现有 JSON 存储模式：
- tasks 文件：./zoe/data/mainforce_tasks.json
- 产物目录：./zoe/data/mainforce/{task_id}/
  - radar.png
  - patterns.png
  - confusion_matrix.png
  - feature_importance.png
  - （可选）report.html（或写入 Zoe 统一 reports_path）

## 7. 验收标准

- 控制台新增“主力识别”入口并可访问
- 能创建任务、在列表看到任务
- 能运行任务并产出图表文件
- 详情页可展示结论与图表预览/链接
- UTF-8 中文无乱码

