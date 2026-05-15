---
name: web-search-universal
description: "通用联网搜索技能，基于 Tavily SDK，支持同步/异步两套接口。输入查询字符串列表，输出结构化 JSON（含标题、摘要、URL、发布时间）。当 Tavily API Key 未配置时自动降级至 DuckDuckGo，并记录告警日志。适用于 Deepseek + 联网搜索等 Agent 场景。"
keywords: 联网, 搜索, Tavily, DuckDuckGo, 通用搜索, 实时, 降级, 异步, RAG
---

# web-search-universal 技能指南

## 概述

`web-search-universal` 是一款通用联网搜索技能，基于 Tavily 官方 Python SDK（MIT License）实现，支持同步、异步两套接口。当 Tavily API Key 未配置或请求失败时，自动降级至 DuckDuckGo HTML 接口，并记录告警日志，确保 Agent 流程不中断。

## License 合规说明

- **tavily-python**: [MIT License](https://github.com/tavily-ai/tavily-python)，由 Tavily AI 官方维护
- **DuckDuckGo HTML API**: 无需 API Key，公开可用，用于非商业降级场景属合理使用

## 适用场景

- Deepseek + 联网搜索模式下的实时信息获取
- Agent 工作流中需要最新网页数据的研报生成
- 量化投研中获取最新市场新闻、行业动态、政策信息
- 需要并发批量搜索的多任务 Agent 场景
- RAG 流程中补充最新外部知识

## 可用脚本

| 脚本 | 功能 | 参数 |
|------|------|------|
| `scripts/search.py` | 同步/异步联网搜索 | `--query`(必填), `--topic`(general/news/finance), `--max-results`(默认5), `--no-cache`, `--async`, `--api-key`, `--output` |

## 安装依赖

```bash
pip install tavily-python
```

> tavily-python 依赖: `requests`, `tiktoken>=0.5.1`, `httpx`（均已随主项目安装）

## 工作流程

1. 接收用户查询字符串
2. 检查 `TAVILY_API_KEY` 环境变量（如未配置，记录告警并降级）
3. 优先调用 Tavily API `POST /search`
4. 请求失败或 Key 缺失时，自动切换 DuckDuckGo HTML 接口
5. 结果写入本地 JSON 缓存（TTL = 1 小时），供后续请求复用
6. 返回标准结构化 JSON

## 结构化输出格式

```json
{
  "query": "贵州茅台最新股价",
  "topic": "stock",
  "results": [
    {
      "title": "贵州茅台(600519)实时行情",
      "url": "https://finance.example.com/600519",
      "content": "最新股价: ¥1850.00, 涨幅: +1.2%...",
      "published_date": "2026-05-13",
      "source": "Tavily"
    }
  ],
  "used_fallback": false,
  "fallback_reason": null,
  "error": null,
  "cached": false,
  "search_time_ms": 312
}
```

## 示例对话

**用户**: "Deepseek 模式下帮我生成宁德时代的最新研报"

Agent 步骤:
1. 调用 `web-search-universal/scripts/search.py --query "宁德时代 最新动态 业绩" --topic finance --max-results 5`
2. 获取搜索结果 JSON
3. 将结果作为上下文传给 Deepseek 模型
4. 生成研报

**用户**: "查一下最近有哪些半导体利好政策"

Agent 步骤:
1. 调用 `python scripts/search.py --query "半导体行业 最新政策 利好 2026" --topic news --max-results 5`
2. 返回政策相关新闻列表

## 异步接口使用

```python
import asyncio
from search import async_search

async def main():
    results = await async_search(
        query="AI 算力芯片最新进展",
        topic="news",
        max_results=5,
        use_cache=True,
    )
    print(results)

asyncio.run(main())
```

## 批量搜索

```python
from search import batch_search

results = batch_search(
    queries=[
        "宁德时代 业绩 2026",
        "比亚迪 最新销量",
        "光伏行业 政策",
    ],
    topic="finance",
    max_results=3,
)
```

## 与 web-search-qwen 的区别

| 维度 | web-search-qwen | web-search-universal |
|------|----------------|---------------------|
| 底层引擎 | 通义千问 `enable_search` | Tavily API + DuckDuckGo 降级 |
| 搜索深度 | LLM 摘要 | 原始网页摘要 + AI 摘要答案 |
| API Key | `DASHSCOPE_API_KEY` | `TAVILY_API_KEY`（可选，降级后无需） |
| 适用模型 | 通义千问系列 | 任意 LLM（Deepseek/Claude/GPT 等） |
| 响应格式 | 自由文本 | 结构化 JSON |
| 降级机制 | 无 | DuckDuckGo HTML 自动降级 |
| 异步接口 | 无 | 支持并发异步搜索 |

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 始终显示 DuckDuckGo 降级 | 未设置 `TAVILY_API_KEY` | 访问 https://app.tavily.com 注册并设置环境变量 |
| `tavily-python` 未安装 | 依赖未安装 | `pip install tavily-python` |
| 异步接口报错 | `aiohttp` 未安装 | `pip install aiohttp`（已随 httpx 安装） |
| 搜索结果为空 | 查询词无相关内容 | 尝试调整 topic 或扩大 max_results |
| 缓存过期 | TTL = 1 小时 | 使用 `--no-cache` 强制刷新 |
