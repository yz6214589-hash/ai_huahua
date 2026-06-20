# -*- coding: utf-8 -*-
"""
启动QMT网关并执行全量API测试（v2）
"""
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

def start_gateway():
    """启动网关服务"""
    print("正在启动QMT网关...")
    proc = subprocess.Popen(
        [sys.executable, "run_server.py"],
        cwd=GATEWAY_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc

def wait_for_gateway(timeout=20):
    """等待网关就绪"""
    print("等待网关就绪...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{BASE_URL}/health")
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status == 200:
                print("网关已就绪!")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("超时：网关未能在规定时间内启动")
    return False

def api_call(method, path, data=None, query=None, timeout=15):
    """发起API调用，支持query参数"""
    url = f"{BASE_URL}{path}"
    if query:
        # URL编码query参数
        qs_parts = []
        for k, v in query.items():
            qs_parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}")
        url += "?" + "&".join(qs_parts)
    
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        status = resp.status
        resp_body = resp.read().decode("utf-8")
        try:
            resp_json = json.loads(resp_body)
        except:
            resp_json = resp_body
        return status, resp_json, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else "(无响应体)"
        return e.code, err_body, str(e)
    except Exception as e:
        return 0, None, str(e)

def test_all_endpoints():
    """测试所有端点"""
    results = []
    connected = False
    
    # 端点定义
    endpoints = [
        # --- 系统 ---
        (1, "GET", "/health", None, None, "健康检查"),
        
        # --- 交易管理 ---
        (2, "GET", "/api/trading/accounts", None, None, "获取账户列表"),
        
        # 3: 连接交易账户(默认 = 国金模拟)
        (3, "POST", "/api/trading/connect", None, None, "连接交易账户(默认)"),
        
        # 4: 获取交易状态
        (4, "GET", "/api/trading/state", None, None, "获取交易状态"),
        
        # 5: 获取账户资产
        (5, "GET", "/api/trading/asset", None, None, "获取账户资产"),
        
        # 6: 获取持仓列表
        (6, "GET", "/api/trading/positions", None, None, "获取持仓列表"),
        
        # 7: 获取委托订单
        (7, "GET", "/api/trading/orders", None, None, "获取委托订单"),
        
        # 8: 获取成交记录
        (8, "GET", "/api/trading/trades", None, None, "获取成交记录"),
        
        # 9: 获取事件日志
        (9, "GET", "/api/trading/events", None, None, "获取事件日志"),
        
        # 10: 提交买入委托(市价)
        (10, "POST", "/api/trading/buy", {
            "stock_code": "000001.SZ",
            "volume": 100,
            "price": 0.0,
            "strategy_name": "test",
            "remark": "API测试"
        }, None, "提交买入委托(市价)"),
        
        # 11: 提交卖出委托(市价)
        (11, "POST", "/api/trading/sell", {
            "stock_code": "000001.SZ",
            "volume": 100,
            "price": 0.0,
            "strategy_name": "test",
            "remark": "API测试"
        }, None, "提交卖出委托(市价)"),
        
        # 12: 撤销委托
        (12, "POST", "/api/trading/cancel", {"order_id": 999999}, None, "撤销委托(测试)"),
        
        # 13: 撤销所有委托
        (13, "POST", "/api/trading/cancel_all", None, None, "撤销所有委托"),
        
        # --- 历史数据 ---
        (14, "POST", "/api/historical/kline", {
            "stock_code": "000001.SZ",
            "period": "1d",
            "start_time": "20260601",
            "end_time": "20260620"
        }, None, "获取K线数据"),
        
        (15, "POST", "/api/historical/kline_batch", {
            "stock_codes": ["000001.SZ", "000002.SZ"],
            "period": "1d",
            "start_time": "20260601",
            "end_time": "20260620"
        }, None, "批量获取K线数据"),
        
        (16, "GET", "/api/historical/stock_list", None, None, "获取股票列表"),
        
        (17, "POST", "/api/historical/financial_data", {
            "stock_code": "000001.SZ",
            "start_time": "20250101",
            "end_time": "20260620",
            "max_rows": 4
        }, None, "获取财务数据"),
        
        # 18: 断开交易连接
        (18, "POST", "/api/trading/disconnect", None, None, "断开交易连接"),
    ]
    
    for idx, method, path, data, query, desc in endpoints:
        print(f"[{idx:2d}/{len(endpoints)}] {method:4s} {path} - {desc}...", end=" ")
        status, resp, err = api_call(method, path, data, query)
        
        if status == 200:
            print("PASS (200)")
            if idx == 3:  # connect成功
                connected = True
        elif status == 503:
            print(f"FAIL (503 - 未连接)")
        else:
            print(f"FAIL ({status})")
            # 显示详细错误
            if isinstance(resp, dict) and 'detail' in resp:
                detail = str(resp['detail'])[:300]
                print(f"      详情: {detail}")
            elif isinstance(resp, str) and resp != "(无响应体)":
                print(f"      响应: {resp[:300]}")
            if err and err != str(status):
                print(f"      错误: {err[:200]}")
        
        results.append({
            "idx": idx,
            "method": method,
            "path": path,
            "desc": desc,
            "status": status,
            "passed": status == 200,
        })
    
    return results

def main():
    print("=" * 60)
    print("QMT Gateway 全量API测试 v2")
    print("=" * 60)
    
    # 检查网关
    print("\n检查网关状态...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        print("网关已在运行中")
    except:
        print("网关未运行，正在启动...")
        proc = start_gateway()
        time.sleep(2)
        
        if not wait_for_gateway():
            print("网关启动失败!")
            stderr = proc.stderr.read().decode("utf-8", errors="replace")
            print(stderr[:2000])
            return 1
    
    print("\n开始执行全量API测试...\n")
    results = test_all_endpoints()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    
    print(f"\n总计: {len(results)} 个端点")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    
    if failed > 0:
        print("\n失败端点:")
        for r in results:
            if not r["passed"]:
                print(f"  [{r['idx']:2d}] {r['method']:4s} {r['path']} - {r['desc']} => {r['status']}")
    
    print()
    if passed == len(results):
        print("全部端点测试通过! (200)")
        return 0
    else:
        print(f"注意: {failed} 个端点未通过 (需全部200)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
