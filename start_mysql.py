# -*- coding: utf-8 -*-
"""检查和启动MySQL"""
import os
import subprocess
import time

mysql_dir = r"C:\mysql"
mysql_exe = os.path.join(mysql_dir, "bin", "mysqld.exe")
mysql_ini = os.path.join(mysql_dir, "my.ini")
mysql_data = os.path.join(mysql_dir, "data")

print("=== MySQL 环境检查 ===")
print(f"MySQL目录: {mysql_dir} (存在: {os.path.exists(mysql_dir)})")
print(f"mysqld.exe: {mysql_exe} (存在: {os.path.exists(mysql_exe)})")
print(f"my.ini: {mysql_ini} (存在: {os.path.exists(mysql_ini)})")
print(f"data目录: {mysql_data} (存在: {os.path.exists(mysql_data)})")

# 检查端口3306
result = subprocess.run("netstat -ano | findstr :3306", shell=True, capture_output=True, text=True)
if "LISTENING" in result.stdout:
    print("\nMySQL 已在运行中!")
    print(result.stdout)
    exit(0)

# 1. 如果data目录不存在，初始化
if not os.path.exists(mysql_data):
    print("\n=== 初始化MySQL data目录 ===")
    print(f"创建目录: {mysql_data}")
    os.makedirs(mysql_data, exist_ok=True)
    
    cmd = f'"{mysql_exe}" --initialize-insecure --console'
    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.path.join(mysql_dir, "bin"))
    print(f"返回码: {result.returncode}")
    print(f"stdout: {result.stdout[-500:]}")
    if result.stderr:
        print(f"stderr: {result.stderr[-500:]}")
    
    if result.returncode != 0:
        print("初始化失败!")
        exit(1)

# 2. 启动MySQL
print("\n=== 启动MySQL ===")
data_dir = os.path.join(mysql_dir, "data")

if os.path.exists(mysql_ini):
    cmd = f'start "" "{mysql_exe}" --defaults-file="{mysql_ini}" --console'
else:
    cmd = f'start "" "{mysql_exe}" --datadir="{data_dir}" --console'

print(f"执行: {cmd}")
subprocess.Popen(cmd, shell=True, cwd=os.path.join(mysql_dir, "bin"))

# 3. 等待启动
print("等待MySQL启动...")
for i in range(15):
    time.sleep(2)
    result = subprocess.run("netstat -ano | findstr :3306", shell=True, capture_output=True, text=True)
    if "LISTENING" in result.stdout:
        print(f"\nMySQL 已成功启动!")
        print(result.stdout.strip())
        exit(0)
    print(f"  等待中... ({i+1}/15)")

print("\nMySQL 启动超时，请检查日志")
