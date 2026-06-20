import subprocess, urllib.request, sys, time, json

# Step 1: 彻底杀掉8001端口
print("Step 1: 杀掉8001端口进程...")
r = subprocess.run("netstat -ano | findstr :8001", shell=True, capture_output=True, text=True)
print(r.stdout)
for line in r.stdout.splitlines():
    parts = line.strip().split()
    if len(parts) >= 5 and "LISTENING" in parts:
        pid = parts[-1]
        print(f"  杀进程 PID={pid}")
        subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True)

time.sleep(2)

# Step 2: 启动新网关
print("\nStep 2: 启动新网关...")
gw_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant_qmt_gateway"
proc = subprocess.Popen(
    [sys.executable, "run_server.py"],
    cwd=gw_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
time.sleep(3)

# Step 3: 测试health
print("\nStep 3: 测试health...")
try:
    req = urllib.request.Request("http://127.0.0.1:8001/health")
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"  Health: {resp.status}")
except Exception as e:
    print(f"  Health失败: {e}")
    stderr = proc.stderr.read().decode("utf-8", errors="replace")
    print(f"  stderr: {stderr[:2000]}")
    sys.exit(1)

# Step 4: 测试完整流程
print("\nStep 4: 全量测试...")
BASE = "http://127.0.0.1:8001"

def call(method, path, data=None, timeout=15):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    h = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.fp else {}, str(e)
    except Exception as e:
        return 0, {}, str(e)

tests = [
    ("GET", "/health", None, "健康检查"),
    ("GET", "/api/trading/accounts", None, "账户列表"),
    ("POST", "/api/trading/connect", None, "连接交易"),
    ("GET", "/api/trading/state", None, "交易状态"),
    ("GET", "/api/trading/asset", None, "账户资产"),
    ("GET", "/api/trading/positions", None, "持仓列表"),
    ("GET", "/api/trading/orders", None, "委托订单"),
    ("GET", "/api/trading/trades", None, "成交记录"),
    ("GET", "/api/trading/events", None, "事件日志"),
    ("POST", "/api/trading/buy", {"stock_code":"000001.SZ","volume":100,"price":0.0,"strategy_name":"test","remark":"API测试"}, "买入委托"),
    ("POST", "/api/trading/sell", {"stock_code":"000001.SZ","volume":100,"price":0.0,"strategy_name":"test","remark":"API测试"}, "卖出委托"),
    ("POST", "/api/trading/cancel", {"order_id": 999999}, "撤销委托"),
    ("POST", "/api/trading/cancel_all", None, "撤销全部"),
    ("POST", "/api/historical/kline", {"stock_code":"000001.SZ","period":"1d","start_time":"20260601","end_time":"20260620"}, "K线数据"),
    ("POST", "/api/historical/kline_batch", {"stock_codes":["000001.SZ","000002.SZ"],"period":"1d","start_time":"20260601","end_time":"20260620"}, "批量K线"),
    ("GET", "/api/historical/stock_list", None, "股票列表"),
    ("POST", "/api/historical/financial_data", {"stock_code":"000001.SZ","start_time":"20250101","end_time":"20260620","max_rows":4}, "财务数据"),
    ("POST", "/api/trading/disconnect", None, "断开连接"),
]

passed = 0
failed = 0
for i, (m, p, d, desc) in enumerate(tests, 1):
    print(f"  [{i:2d}/18] {m:4s} {p}...", end=" ")
    s, r, e = call(m, p, d)
    if s == 200:
        print("PASS")
        passed += 1
    else:
        print(f"FAIL ({s})")
        detail = r.get("detail", "") if isinstance(r, dict) else ""
        if detail:
            print(f"         {detail[:200]}")
        failed += 1

print(f"\n========================================")
print(f"通过: {passed}/18 | 失败: {failed}/18")
print(f"{'全部通过!' if failed == 0 else '有端点未通过'}")
