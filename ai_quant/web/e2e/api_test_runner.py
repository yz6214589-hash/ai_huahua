#!/usr/bin/env python3
"""AI Quant 系统 API 测试执行脚本"""
import json
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

test_results = []

def test_api(name, method, endpoint, expected_status=200, data=None, params=None):
    """执行API测试"""
    url = f"{BASE_URL}{endpoint}"
    result = {
        "name": name,
        "method": method,
        "url": url,
        "endpoint": endpoint,
        "expected_status": expected_status,
        "passed": False,
        "error": None,
        "response_time_ms": 0
    }

    start_time = datetime.now()

    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            result["error"] = f"Unsupported method: {method}"
            test_results.append(result)
            return result

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed, 2)
        result["actual_status"] = response.status_code

        if response.status_code == expected_status:
            result["passed"] = True
            try:
                result["response"] = response.json()
            except:
                result["response"] = response.text[:200]
        else:
            result["error"] = f"Expected {expected_status}, got {response.status_code}"
            try:
                result["response"] = response.json()
            except:
                result["response"] = response.text[:200]

    except requests.exceptions.Timeout:
        result["error"] = "Request timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection error - service may not be running"
    except Exception as e:
        result["error"] = str(e)

    test_results.append(result)
    return result

def print_result(result):
    """打印测试结果"""
    status = "PASS" if result["passed"] else "FAIL"
    time_ms = result.get("response_time_ms", 0)
    error = result.get("error", "")

    print(f"[{status}] {result['method']} {result['endpoint']} ({time_ms}ms)")
    if error:
        print(f"       Error: {error}")

def main():
    print("=" * 80)
    print("AI Quant 系统 API 测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"API Base URL: {BASE_URL}")
    print("=" * 80)

    # P0 - 核心功能测试
    print("\n--- P0 核心功能测试 ---\n")

    test_api("健康检查", "GET", "/health")
    test_api("健康检查v1", "GET", "/v1/health")
    test_api("系统总览", "GET", "/summary")
    test_api("数据查询-股票日线", "GET", "/data/trade_stock_daily?page=1&page_size=10")
    test_api("数据查询-新闻舆情", "GET", "/data/trade_stock_news?page=1&page_size=10")
    test_api("数据查询-宏观指标", "GET", "/data/trade_macro_indicator?page=1&page_size=10")

    # P1 - 重要功能测试
    print("\n--- P1 重要功能测试 ---\n")

    test_api("自选股列表", "GET", "/watchlist")
    test_api("采集任务运行记录", "GET", "/jobs/runs?limit=10")
    test_api("研报任务列表", "GET", "/reports/tasks?limit=10")
    test_api("舆情运行记录", "GET", "/sentiment/runs?limit=10")
    test_api("执行服务状态", "GET", "/execution/status")
    test_api("风控服务状态", "GET", "/risk/status")
    test_api("AI Agent状态", "GET", "/agent/status")
    test_api("AI Agent工具列表", "GET", "/agent/tools")

    # P2 - 增强功能测试
    print("\n--- P2 增强功能测试 ---\n")

    test_api("晨会控制台状态", "GET", "/console/status")
    test_api("调度配置列表", "GET", "/jobs/schedules")
    test_api("RAG状态", "GET", "/reports/rag/status")

    # POST 测试
    print("\n--- POST 请求测试 ---\n")

    test_api("创建研报任务-无效参数", "POST", "/reports/tasks",
             expected_status=422, data={})

    test_api("风控审批", "POST", "/risk/approve",
             expected_status=200,
             data={"order_id": "test_order_001", "action": "approve", "reason": "测试审批"})

    test_api("创建执行任务", "POST", "/execution/tasks",
             expected_status=200,
             data={"action": "test_action", "symbol": "AAPL", "quantity": 100})

    # 打印结果汇总
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    passed = sum(1 for r in test_results if r["passed"])
    failed = len(test_results) - passed

    print(f"总测试数: {len(test_results)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/len(test_results)*100:.1f}%")

    print("\n--- 失败测试详情 ---\n")
    for result in test_results:
        if not result["passed"]:
            print_result(result)
            if "response" in result and result["response"]:
                resp_str = str(result["response"])[:500]
                print(f"       Response: {resp_str}")

    # 保存结果到JSON
    output_file = "/Users/apple/Desktop/ai_huahua/ai_quant/docs/api_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total": len(test_results),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/len(test_results)*100:.1f}%",
            "results": test_results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n测试结果已保存到: {output_file}")

    return failed

if __name__ == "__main__":
    exit_code = main()
    exit(0 if exit_code == 0 else 1)
