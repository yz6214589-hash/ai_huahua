import os, subprocess, time, sys

OUT = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\mysql_start_result.txt"
mysql_dir = r"C:\mysql"

def log(msg):
    with open(OUT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    print(msg)

# 清空日志
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('')

log("=== MySQL启动 ===")
log(f"MySQL dir: {mysql_dir}")

# 检查是否已运行
r = subprocess.run('netstat -ano | findstr ":3306 "', shell=True, capture_output=True, text=True)
if 'LISTENING' in r.stdout:
    log(f"MySQL已在运行: {r.stdout.strip()}")
    sys.exit(0)

# 检查data目录
data_dir = os.path.join(mysql_dir, 'data')
my_ini = os.path.join(mysql_dir, 'my.ini')
mysqld = os.path.join(mysql_dir, 'bin', 'mysqld.exe')

log(f"data_dir存在: {os.path.exists(data_dir)}")
log(f"my.ini存在: {os.path.exists(my_ini)}")
log(f"mysqld存在: {os.path.exists(mysqld)}")

# 初始化
if not os.path.exists(data_dir):
    log("初始化MySQL data目录...")
    os.makedirs(data_dir, exist_ok=True)
    
    r = subprocess.run(
        f'"{mysqld}" --initialize-insecure --console',
        shell=True, capture_output=True, text=True,
        cwd=os.path.join(mysql_dir, 'bin'),
        timeout=60
    )
    log(f"初始化返回码: {r.returncode}")
    if r.stdout:
        log(f"stdout: {r.stdout[-500:]}")
    if r.stderr:
        log(f"stderr: {r.stderr[-500:]}")
    
    if r.returncode != 0:
        log("初始化失败!")
        sys.exit(1)

# 启动
log("启动MySQL...")
if os.path.exists(my_ini):
    cmd = f'"{mysqld}" --defaults-file="{my_ini}"'
else:
    cmd = f'"{mysqld}" --datadir="{data_dir}"'

subprocess.Popen(
    cmd, shell=True,
    cwd=os.path.join(mysql_dir, 'bin'),
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

# 等待
for i in range(20):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":3306 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        log(f"MySQL启动成功 ({i*2}s)")
        log(r.stdout.strip())
        sys.exit(0)
    log(f"  等待 {i+1}/20...")

log("MySQL启动超时!")
sys.exit(1)
