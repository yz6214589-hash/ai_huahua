# ai_quant 一键启动脚本 (Windows PowerShell)
# 用法: 右键 -> 使用 PowerShell 运行, 或 cd 到脚本目录后 .\start_all.ps1
# 或者直接双击（会闪一下窗口，建议右键用 PowerShell 运行）

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Quant 量化系统启动脚本 (Windows)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "后端端口: 8000"
Write-Host "前端端口: 5173"
Write-Host "Streamlit 端口: 8501"
Write-Host "============================================" -ForegroundColor Cyan

# 检查 Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Host "[错误] 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $($PythonCmd.Source)" -ForegroundColor Green

# 检查虚拟环境
$VenvPython = Join-Path $RootDir "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[错误] 虚拟环境不存在: $VenvPython" -ForegroundColor Red
    Write-Host "请先运行: python -m venv venv" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] 虚拟环境: $VenvPython" -ForegroundColor Green

# 检查 Node.js
$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $NodeCmd) {
    Write-Host "[错误] 未找到 Node.js，请先安装" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Node.js: $($NodeCmd.Source)" -ForegroundColor Green

# 检查后端依赖
Write-Host ""
Write-Host "[1/3] 检查后端依赖 ..." -ForegroundColor Yellow
$ReqsFile = Join-Path $RootDir "backend\requirements.txt"
if (Test-Path $ReqsFile) {
    & $VenvPython -m pip install -r $ReqsFile -q 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[提示] 依赖安装有警告，继续启动 ..." -ForegroundColor Yellow
    }
}

# 检查前端依赖
Write-Host "[2/3] 检查前端依赖 ..." -ForegroundColor Yellow
$WebDir = Join-Path $RootDir "web"
$NodeModules = Join-Path $WebDir "node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "  安装前端依赖中 ..." -ForegroundColor Yellow
    Push-Location $WebDir
    npm install
    Pop-Location
}

# 启动后端
Write-Host "[3/3] 启动后端 ..." -ForegroundColor Yellow
Write-Host "--------------------------------------------" -ForegroundColor DarkGray
Write-Host "后端地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Swagger 文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "--------------------------------------------" -ForegroundColor DarkGray

$BackendJob = Start-Job -ScriptBlock {
    param($RootDir, $VenvPython)
    Set-Location $RootDir
    & "$VenvPython" backend\run_server.py
} -ArgumentList $RootDir, $VenvPython

Start-Sleep 2

# 启动前端
Write-Host ""
Write-Host "--------------------------------------------" -ForegroundColor DarkGray
Write-Host "前端地址: http://localhost:5173" -ForegroundColor Cyan
Write-Host "--------------------------------------------" -ForegroundColor DarkGray

$FrontendJob = Start-Job -ScriptBlock {
    param($WebDir)
    Set-Location $WebDir
    npm run dev
} -ArgumentList $WebDir

# 启动 Streamlit
$StreamlitExe = Join-Path $RootDir "venv\Scripts\streamlit.exe"
if (Test-Path $StreamlitExe) {
    Write-Host ""
    Write-Host "--------------------------------------------" -ForegroundColor DarkGray
    Write-Host "Streamlit 地址: http://localhost:8501" -ForegroundColor Cyan
    Write-Host "--------------------------------------------" -ForegroundColor DarkGray

    $StreamlitJob = Start-Job -ScriptBlock {
        param($RootDir, $StreamlitExe)
        Set-Location $RootDir
        & "$StreamlitExe" run streamlit_chat\app.py --server.port 8501
    } -ArgumentList $RootDir, $StreamlitExe
} else {
    Write-Host ""
    Write-Host "[提示] Streamlit 未安装，跳过。如需启用: venv\Scripts\pip install streamlit" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " 所有服务已启动!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "后端 Swagger: http://localhost:8000/docs" -ForegroundColor White
Write-Host "前端:         http://localhost:5173" -ForegroundColor White
Write-Host "Streamlit:     http://localhost:8501" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示: 关闭此窗口不会停止后台服务。" -ForegroundColor Yellow
Write-Host "停止服务方法: Stop-Job -Job $BackendJob,$FrontendJob,$StreamlitJob; Remove-Job -Job *" -ForegroundColor Yellow
Write-Host ""

# 保持脚本运行以便查看输出
try {
    Receive-Job -Job $BackendJob,$FrontendJob,$StreamlitJob -ErrorAction SilentlyContinue
} finally {
    Write-Host ""
    Write-Host "后台服务仍在运行。如需停止，请运行: Stop-Job -Job *; Remove-Job -Job *" -ForegroundColor Yellow
}
