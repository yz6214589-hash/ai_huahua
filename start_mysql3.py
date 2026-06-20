import subprocess, time, os

mysql_dir = r"C:\mysql"
mysqld = os.path.join(mysql_dir, "bin", "mysqld.exe")
my_ini = os.path.join(mysql_dir, "my.ini")

# 检查是否已运行
r = subprocess.run('netstat -ano | findstr ":3306 "', shell=True, capture_output=True, text=True)
if 'LISTENING' in r.stdout:
    print(f"MySQL已在运行!")
    print(r.stdout.strip())
    exit(0)

# 检查数据目录是否存在且有内容
datadir = r"C:\Users\qqq\AppData\Local\Temp\mysql_data"
print(f"数据目录: {datadir}")
print(f"  存在: {os.path.exists(datadir)}")
if os.path.exists(datadir):
    items = os.listdir(datadir)
    print(f"  文件数: {len(items)}")
    for i in items[:10]:
        print(f"    {i}")

# 直接启动
print(f"\n启动MySQL (mysqld: {mysqld})...")
cmd = f'start "" "{mysqld}" --defaults-file="{my_ini}" --console'
print(f"命令: {cmd}")

subprocess.Popen(cmd, shell=True, cwd=os.path.join(mysql_dir, "bin"))

# 等待
for i in range(15):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":3306 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"\nMySQL启动成功!")
        print(r.stdout.strip())
        exit(0)
    print(f"  等待 {i+1}/15...")

print("\n启动超时!")
exit(1)
