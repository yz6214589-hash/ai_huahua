@echo off
chcp 65001 >nul 2>&1
title QMT Gateway 一键部署脚本
echo ============================================
echo   QMT Gateway 一键部署脚本
echo   运行时间: %date% %time%
echo ============================================
echo.

set "TARGET=C:\apps\qmt_gateway"
if not "%1"=="" set "TARGET=%1"

echo [步骤1] 检查部署文件...
set "MISSING=0"
for %%f in (app.py miniqmt_trader.py run_server.py test_qmt_cloud_local.py) do (
    if not exist "%%f" (
        echo   [错误] 缺少文件: %%f
        set "MISSING=1"
    ) else (
        echo   [OK] %%f
    )
)
if "%MISSING%"=="1" (
    echo.
    echo   请确保所有部署文件与本脚本在同一目录
    pause
    exit /b 1
)
echo.

echo [步骤2] 停止 QMT Gateway 服务...
tasklist /FI "WINDOWTITLE eq QMT Gateway" 2>nul | find /I "cmd.exe" >nul 2>&1
if %ERRORLEVEL%==0 (
    taskkill /FI "WINDOWTITLE eq QMT Gateway" /F >nul 2>&1
    echo   已停止 QMT Gateway 窗口进程
) else (
    echo   未发现 QMT Gateway 窗口进程
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1 2>nul
    echo   已终止占用 8001 端口的进程 PID=%%a
)
timeout /t 2 /nobreak >nul
echo.

echo [步骤3] 备份当前文件...
set "BACKUP_DIR=%TARGET%\backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "BACKUP_DIR=%BACKUP_DIR: =0%"
if exist "%TARGET%" (
    mkdir "%BACKUP_DIR%" >nul 2>&1
    for %%f in (app.py miniqmt_trader.py run_server.py) do (
        if exist "%TARGET%\%%f" copy /Y "%TARGET%\%%f" "%BACKUP_DIR%\%%f" >nul 2>&1
        echo   已备份: %%f
    )
    echo   备份目录: %BACKUP_DIR%
) else (
    mkdir "%TARGET%" >nul 2>&1
    echo   目标目录不存在，已创建: %TARGET%
)
echo.

echo [步骤4] 部署新文件...
for %%f in (app.py miniqmt_trader.py run_server.py test_qmt_cloud_local.py) do (
    if exist "%%f" (
        copy /Y "%%f" "%TARGET%\%%f" >nul 2>&1
        echo   已部署: %%f
    ) else (
        echo   警告: %%f 不存在，跳过
    )
)
echo.

echo [步骤5] 启动 QMT Gateway 服务...
cd /d "%TARGET%"
echo   启动命令: python run_server.py
echo   日志文件: %TARGET%\gateway.log
start "QMT Gateway" /MIN cmd /c "python run_server.py > %TARGET%\gateway.log 2>&1"

echo   等待 5 秒后检查服务状态...
timeout /t 5 /nobreak >nul

echo.
echo [步骤6] 验证服务健康检查...
python -c "import urllib.request, sys; resp = urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5); body = resp.read().decode(); print('[成功] 健康检查通过: ' + body) if 'ok' in body else (print('[警告] 响应异常: ' + body), sys.exit(1))" 2>&1

if %ERRORLEVEL%==0 (
    echo.
    echo ============================================
    echo   [成功] QMT Gateway 服务已启动并正常运行
    echo   端口: 8001
    echo   健康检查: http://127.0.0.1:8001/health
    echo ============================================
) else (
    echo.
    echo   [错误] 服务未能正常启动
    echo   请查看日志文件: %TARGET%\gateway.log
    echo.
    echo   常见问题:
    echo     1. 缺失依赖包: pip install fastapi uvicorn pydantic
    echo     2. 端口被占用: netstat -ano ^| findstr :8001
    echo     3. 环境变量未设置: QMT_PATH / ACCOUNT_ID / QMT_API_TOKEN
    echo.
)

echo.
echo [步骤7] 运行接口测试...
echo   执行命令: pytest test_qmt_cloud_local.py -v
echo.
cd /d "%TARGET%"
python -m pytest test_qmt_cloud_local.py -v 2>&1
echo.

echo ============================================
echo   部署完成
echo   如需回滚，请从备份目录恢复: %BACKUP_DIR%
echo ============================================
pause
