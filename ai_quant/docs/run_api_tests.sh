#!/bin/bash
# AI Quant 系统 API 测试脚本

echo "=========================================="
echo "AI Quant 系统 API 测试"
echo "=========================================="
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "API Base URL: http://localhost:8000/api/v1"
echo "=========================================="

BASE_URL="http://localhost:8000/api/v1"

# 测试函数
test_api() {
    local name=$1
    local method=$2
    local endpoint=$3
    local expected_status=$4
    local data=$5

    url="${BASE_URL}${endpoint}"

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null)
        status=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null)
        status=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
    fi

    if [ "$status" = "$expected_status" ]; then
        echo "[PASS] $method $endpoint (期望:$expected_status, 实际:$status)"
        return 0
    else
        echo "[FAIL] $method $endpoint (期望:$expected_status, 实际:$status)"
        echo "       响应: ${body:0:200}"
        return 1
    fi
}

passed=0
failed=0

# P0 核心功能测试
echo ""
echo "--- P0 核心功能测试 ---"
echo ""

test_api "健康检查" "GET" "/health" "200" && ((passed++)) || ((failed++))
test_api "健康检查v1" "GET" "/v1/health" "200" && ((passed++)) || ((failed++))
test_api "系统总览" "GET" "/summary" "200" && ((passed++)) || ((failed++))
test_api "数据查询-股票日线" "GET" "/data/trade_stock_daily?page=1&page_size=10" "200" && ((passed++)) || ((failed++))
test_api "数据查询-新闻舆情" "GET" "/data/trade_stock_news?page=1&page_size=10" "200" && ((passed++)) || ((failed++))
test_api "数据查询-宏观指标" "GET" "/data/trade_macro_indicator?page=1&page_size=10" "200" && ((passed++)) || ((failed++))

# P1 重要功能测试
echo ""
echo "--- P1 重要功能测试 ---"
echo ""

test_api "自选股列表" "GET" "/watchlist" "200" && ((passed++)) || ((failed++))
test_api "采集任务运行记录" "GET" "/jobs/runs?limit=10" "200" && ((passed++)) || ((failed++))
test_api "研报任务列表" "GET" "/reports/tasks?limit=10" "200" && ((passed++)) || ((failed++))
test_api "舆情运行记录" "GET" "/sentiment/runs?limit=10" "200" && ((passed++)) || ((failed++))
test_api "执行服务状态" "GET" "/execution/status" "200" && ((passed++)) || ((failed++))
test_api "风控服务状态" "GET" "/risk/status" "200" && ((passed++)) || ((failed++))
test_api "AI Agent状态" "GET" "/agent/status" "200" && ((passed++)) || ((failed++))
test_api "AI Agent工具列表" "GET" "/agent/tools" "200" && ((passed++)) || ((failed++))

# P2 增强功能测试
echo ""
echo "--- P2 增强功能测试 ---"
echo ""

test_api "晨会控制台状态" "GET" "/console/status" "200" && ((passed++)) || ((failed++))
test_api "调度配置列表" "GET" "/jobs/schedules" "200" && ((passed++)) || ((failed++))
test_api "RAG状态" "GET" "/reports/rag/status" "200" && ((passed++)) || ((failed++))

# POST 测试
echo ""
echo "--- POST 请求测试 ---"
echo ""

test_api "创建研报任务-无效参数" "POST" "/reports/tasks" "422" '{}'
test_api "风控审批" "POST" "/risk/approve" "200" '{"order_id":"test_order_001","action":"approve","reason":"测试审批"}'
test_api "创建执行任务" "POST" "/execution/tasks" "200" '{"action":"test_action","symbol":"AAPL","quantity":100}'

# 汇总
echo ""
echo "=========================================="
echo "测试结果汇总"
echo "=========================================="
total=$((passed + failed))
echo "总测试数: $total"
echo "通过: $passed"
echo "失败: $failed"
if [ $total -gt 0 ]; then
    rate=$((passed * 100 / total))
    echo "通过率: ${rate}%"
fi
echo "=========================================="

exit $failed
