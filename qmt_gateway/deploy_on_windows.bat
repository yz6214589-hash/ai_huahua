@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   QMT Gateway 部署脚本
echo   目标目录: C:\apps\qmt_gateway
echo ============================================
echo.

set "TARGET=C:\apps\qmt_gateway"

if not exist "%TARGET%" (
    echo [错误] 目标目录不存在: %TARGET%
    echo 请确认 QMT Gateway 安装路径
    pause
    exit /b 1
)

echo [步骤1] 停止 QMT Gateway 服务...
tasklist /FI "IMAGENAME eq python.exe" /V 2>nul | findstr /I "run_server" >nul
if %ERRORLEVEL%==0 (
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /V 2^>nul ^| findstr /I "run_server"') do (
        echo   终止进程 PID: %%a
        taskkill /PID %%a /F >nul 2>&1
    )
    echo   服务已停止
) else (
    echo   未检测到运行中的服务
)
echo.

echo [步骤2] 备份旧文件...
set "BACKUP_DIR=%TARGET%\backup\%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "BACKUP_DIR=%BACKUP_DIR: =0%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for %%f in (app.py miniqmt_trader.py run_server.py) do (
    if exist "%TARGET%\%%f" (
        copy "%TARGET%\%%f" "%BACKUP_DIR%\%%f" >nul 2>&1
        echo   已备份: %%f
    )
)
echo   备份目录: %BACKUP_DIR%
echo.

echo [步骤3] 部署新文件...
for %%f in (app.py miniqmt_trader.py run_server.py) do (
    if exist "%%f" (
        copy /Y "%%f" "%TARGET%\%%f" >nul 2>&1
        echo   已部署: %%f
    ) else (
        echo   警告: %%f 不存在，跳过
    )
)
echo.

echo [步骤4] 启动 QMT Gateway 服务...
cd /d "%TARGET%"
start "QMT Gateway" python run_server.py
echo   服务启动中...
echo.

echo 等待 3 秒后检查服务状态...
timeout /t 3 /nobreak >nul

tasklist /FI "IMAGENAME eq python.exe" /V 2>nul | findstr /I "run_server" >nul
if %ERRORLEVEL%==0 (
    echo [成功] QMT Gateway 服务已启动
) else (
    echo [警告] 未检测到运行中的服务，请手动检查
)
echo.

echo ============================================
echo   部署完成
echo   如需回滚，请从备份目录恢复: %BACKUP_DIR%
echo ============================================
pause
