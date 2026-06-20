# -*- coding: utf-8 -*-
"""清理并重启网关 + 全量测试"""
import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
import urllib.parse
import os

GATEWAY_DIR = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant_qmt_gateway"
BASE_URL = "http://127.0.0.1:8001"

# Step 1: 杀掉所有占用8001端口的进程
print("Step 1: 清理端口8001...")
result = subprocess.run(
    "for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :8001.*LISTENING') do @taskkill /PID %a /F 2>nul",
    shell=True, capture_output=True, text=True
)
time.sleep(1)

# 确认端口已释放
result = subprocess.run("netstat -ano | findstr :8001", shell=True, capture_output=True, text=True)
if "LISTENING" in result.stdout:
    print("  端口仍被占用!")
else:
    print("  端口已释放")

# 等待一下让QMT清理之前连接的状态
time.sleep(3)

# Step 2: 启动新网关
print("\nStep 2: 启动网关...")
proc = subprocess.Popen(
    [sys.executable, "run_server.py"],
    cwd=GATEWAY_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Step 3: 等待就绪
print("Step 3: 等待网关就绪...")
start = time.time()
while time.time() - start < 20:
    try:
        req = urllib.request.Request(f"{BASE_URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        if resp.status == 200:
            print("  网关已就绪!")
            break
    except:
        pass
    time.sleep(0.5)
else:
    print("  超时!")
    stderr = proc.stderr.read().decode("utf-8", errors="replace")
    print(stderr[:1000])
    sys.exit(1)

# Step 4: 运行全量测试
print("\nStep 4: 全量API测试...\n")

def api_call(method, path, data=None, query=None, timeout=20):
    url = f"{BASE_URL}{path}"
    if query:
        qs_parts = [f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}" for k, v in query.items()]
        url += "?" + "&".join(qs_parts)
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")) if e.fp else {"detail": "no body"}, str(e)
    except Exception as e:
        return 0, None, str(e)

endpoints = [
    (1, "GET", "/health", None, None, "健康检查"),
    (2, "GET", "/api/trading/accounts", None, None, "获取账户列表"),
    (3, "POST", "/api/trading/connect", None, None, "连接交易账户(默认)"),
    (4, "GET", "/api/trading/state", None, None, "获取交易状态"),
    (5, "GET", "/api/trading/asset", None, None, "获取账户资产"),
    (6, "GET", "/api/trading/positions", None, None, "获取持仓列表"),
    (7, "GET", "/api/trading/orders", None, None, "获取委托订单"),
    (8, "GET", "/api/trading/trades", None, None, "获取成交记录"),
    (9, "GET", "/api/trading/events", None, None, "获取事件日志"),
    (10, "POST", "/api/trading/buy", {"stock_code": "000001.SZ", "volume": 100, "price": 0.0, "strategy_name": "test", "remark": "API测试"}, None, "提交买入委托(市价)"),
    (11, "POST", "/api/trading/sell", {"stock_code": "000001.SZ", "volume": 100, "price": 0.0, "strategy_name": "test", "remark": "API测试"}, None, "提交卖出委托(市价)"),
    (12, "POST", "/api/trading/cancel", {"order_id": 999999}, None, "撤销委托(测试)"),
    (13, "POST", "/api/trading/cancel_all", None, None, "撤销所有委托"),
    (14, "POST", "/api/historical/kline", {"stock_code": "000001.SZ", "period": "1d", "start_time": "20260601", "end_time": "20260620"}, None, "获取K线数据"),
    (15, "POST", "/api/historical/kline_batch", {"stock_codes": ["000001.SZ", "000002.SZ"], "period": "1d", "start_time": "20260601", "end_time": "20260620"}, None, "批量获取K线数据"),
    (16, "GET", "/api/historical/stock_list", None, None, "获取股票列表"),
    (17, "POST", "/api/historical/financial_data", {"stock_code": "000001.SZ", "start_time": "20250101", "end_time": "20260620", "max_rows": 4}, None, "获取财务数据"),
    (18, "POST", "/api/trading/disconnect", None, None, "断开交易连接"),
]

results = []
for idx, method, path, data, query, desc in endpoints:
    print(f"[{idx:2d}/{len(endpoints)}] {method:4s} {path} - {desc}...", end=" ")
    status, resp, err = api_call(method, path, data, query)
    
    if status == 200:
        print("PASS (200)")
    elif status == 503:
        print(f"FAIL (503)")
        if isinstance(resp, dict) and 'detail' in resp:
            print(f"      详情: {resp['detail'][:200]}")
    else:
        print(f"FAIL ({status})")
        if isinstance(resp, dict) and 'detail' in resp:
            print(f"      详情: {resp['detail'][:200]}")
        elif err:
            print(f"      错误: {err[:200]}")
    
    results.append({"idx": idx, "method": method, "path": path, "desc": desc, "status": status, "passed": status == 200})

# Summary
print("\n" + "=" * 60)
print("测试结果汇总")
print("=" * 60)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])
print(f"总计: {len(results)} | 通过: {passed} | 失败: {failed}")
if failed > 0:
    print("失败端点:")
    for r in results:
        if not r["passed"]:
            print(f"  [{r['idx']:2d}] {r['method']:4s} {r['path']} - {r['desc']} => {r['status']}")
print()
print("全部通过!" if failed == 0 else f"有 {failed} 个端点未通过")
