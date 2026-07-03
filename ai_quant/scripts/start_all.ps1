﻿#==============================================================================
# AI Quant 一键启动脚本 (Windows PowerShell)
#
# 功能: 同时启动后端API、前端应用、AI对话机器人、飞书机器人四个服务
#
# 使用方法:
#   .\start_all.ps1 [选项]
#
# 选项:
#   -Dev           开发模式 (默认，含热重载)
#   -Prod          生产模式
#   -Bg            后台运行模式
#   -Status        查看服务状态
#   -Kill          停止所有服务
#   -Help          显示帮助信息
#==============================================================================

param(
    [switch]$Dev,
    [switch]$Prod,
    [switch]$Bg,
    [switch]$Status,
    [switch]$Kill,
    [switch]$Help
)

# 全局配置
$ScriptDir = "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\scripts"
$ProjectRoot = "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"
$BackendDir = "$ProjectRoot\backend"
$FrontendDir = "$ProjectRoot\web"
$StreamlitDir = "$ProjectRoot\streamlit_chat"
$GatewayDir = "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant_qmt_gateway"
$LogDir = "$ProjectRoot\.ai_quant\logs"
$VenvPython = "$ProjectRoot\venv\Scripts\python.exe"
$VenPython = $VenvPython

# 服务端口配置
$PortGateway = 8001
$PortBackend = 8000
$PortFrontend = 5173
$PortStreamlit = 8501

# URL
$UrlGateway = "http://127.0.0.1:8001"
$UrlBackend = "http://127.0.0.1:8000"
$UrlFrontend = "http://localhost:5173"
$UrlStreamlit = "http://localhost:8501"
$UrlAdmin = "$UrlFrontend/ai-admin"

# 运行模式
$Mode = "dev"

# QMT Gateway 服务配置
$GatewayScript = Join-Path $GatewayDir "run_server.py"
$GatewayPidFile = Join-Path $LogDir "gateway.pid"
$GatewayLog = Join-Path $LogDir "gateway.log"
$GatewayToken = "h4Yx2nKpQ9vL7sT3mR8cW1zJ6uE0aD5gB2fH9jN4qS7tV3yX8kP1rM6wZ0cL2nQ7"

# 飞书机器人配置
$FeishuBotScript = Join-Path $BackendDir "feishu\bot.py"
$FeishuBotPidFile = Join-Path $LogDir "feishu_bot.pid"
$FeishuBotLog = Join-Path $LogDir "feishu_bot.log"

# MySQL 本地数据库配置
$MySQLDir = "C:\mysql"
$MySQLExe = Join-Path $MySQLDir "bin\mysqld.exe"
$MySQLIni = Join-Path $MySQLDir "my.ini"
$MySQLData = "C:\Users\qqq\AppData\Local\Temp\mysql_data"
$MySQLPort = 3306
$MySQLLog = Join-Path $LogDir "mysql.log"

#==============================================================================
# 辅助函数
#==============================================================================

function Write-Log {
    param([string]$Level, [string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Level) {
        "INFO"  { Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor Green }
        "WARN"  { Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor Red }
        "START" { Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor Blue }
        "DONE"  { Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor Green }
        default { Write-Host "[$timestamp] [$Level] $Message" }
    }
}

function Test-Command {
    param([string]$Cmd)
    try { Get-Command $Cmd -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

function Test-Port {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
    return ($null -ne $conn)
}

function Get-PidByPort {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" } | Select-Object -First 1
    if ($conn) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($proc) { return $proc.Id }
        } catch { }
    }
    return $null
}

function Stop-ByPort {
    param([int]$Port)
    $procId = Get-PidByPort -Port $Port
    if ($procId) {
        try { Stop-Process -Id $procId -Force -ErrorAction Stop | Out-Null; return $true }
        catch { return $false }
    }
    return $true
}

#==============================================================================
# 飞书机器人进程管理
#==============================================================================

function Get-FeishuBotPid {
    if (Test-Path $FeishuBotPidFile) {
        $savedId = Get-Content $FeishuBotPidFile -Raw
        if ($savedId) {
            $savedId = $savedId.Trim()
            try {
                $proc = Get-Process -Id ([int]$savedId) -ErrorAction SilentlyContinue
                if ($proc -and $proc.ProcessName -like "*python*") {
                    return [int]$savedId
                }
            } catch { }
        }
    }
    return $null
}

function Start-FeishuBot {
    Write-Log "START" "启动飞书机器人..."

    $oldPid = Get-FeishuBotPid
    if ($oldPid) {
        Write-Log "INFO" "发现旧飞书机器人进程 (PID: $oldPid)，正在停止..."
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 2
    }

    $proc = Start-Process -FilePath $VenPython `
        -ArgumentList "`"$FeishuBotScript`"" `
        -RedirectStandardOutput $FeishuBotLog `
        -RedirectStandardError (Join-Path $LogDir "feishu_bot_err.log") `
        -NoNewWindow `
        -PassThru

    $proc.Id | Out-File -FilePath $FeishuBotPidFile -NoNewline
    Start-Sleep -Seconds 3

    if (-not $proc.HasExited) {
        Write-Log "DONE" "飞书机器人已启动 (PID: $($proc.Id), 日志: $FeishuBotLog)"
        return $true
    } else {
        Write-Log "ERROR" "飞书机器人启动失败，请查看日志: $FeishuBotLog"
        Remove-Item $FeishuBotPidFile -ErrorAction SilentlyContinue
        return $false
    }
}

function Stop-FeishuBot {
    $botPid = Get-FeishuBotPid
    if ($botPid) {
        Write-Log "INFO" "正在停止飞书机器人 (PID: $botPid)..."
        Stop-Process -Id $botPid -Force -ErrorAction SilentlyContinue | Out-Null
        Remove-Item $FeishuBotPidFile -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Write-Log "DONE" "已停止飞书机器人"
        return $true
    }
    Write-Log "INFO" "飞书机器人未运行"
    return $true
}

function Test-FeishuBot {
    return (Get-FeishuBotPid) -ne $null
}

#==============================================================================
# MySQL 本地数据库管理
#==============================================================================

function Test-MySQL {
    return Test-Port $MySQLPort
}

function Get-MySQLPid {
    return Get-PidByPort $MySQLPort
}

function Start-MySQL {
    Write-Log "START" "检测本地 MySQL 数据库..."

    # 如果已经在运行，直接返回
    if (Test-MySQL) {
        $mysqlPid = Get-MySQLPid
        Write-Log "DONE" "MySQL 已在运行 (PID: $mysqlPid, 端口: ${MySQLPort})"
        return $true
    }

    # 检查 mysqld.exe 是否存在
    if (-not (Test-Path $MySQLExe)) {
        Write-Log "WARN" "MySQL 可执行文件未找到: $MySQLExe"
        Write-Log "INFO" "跳过 MySQL 启动，请确保数据库手动运行"
        return $false
    }

    # 检查配置文件
    if (-not (Test-Path $MySQLIni)) {
        Write-Log "WARN" "MySQL 配置文件未找到: $MySQLIni"
    }

    # 从 my.ini 中读取 datadir（如果配置文件存在）
    $DataDir = $MySQLData
    if (Test-Path $MySQLIni) {
        $iniContent = Get-Content $MySQLIni -Encoding UTF8
        foreach ($line in $iniContent) {
            if ($line -match '^datadir\s*=\s*(.+)$') {
                $DataDir = $Matches[1].Trim().Replace('/', '\')
                break
            }
        }
    }

    # 如果 data 目录不存在，自动初始化
    if (-not (Test-Path $DataDir)) {
        Write-Log "INFO" "MySQL data 目录不存在: $DataDir，正在自动初始化..."
        $parentDir = Split-Path -Parent $DataDir
        if (-not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }

        $initArgs = @("--initialize-insecure", "--console")
        if (Test-Path $MySQLIni) {
            $initArgs = @("--defaults-file=`"$MySQLIni`"", "--initialize-insecure", "--console")
        }

        $initProc = Start-Process -FilePath $MySQLExe `
            -ArgumentList $initArgs `
            -NoNewWindow `
            -Wait `
            -PassThru

        if (-not (Test-Path $DataDir)) {
            Write-Log "ERROR" "MySQL 初始化失败，data 目录仍未创建: $DataDir"
            return $false
        }
        Write-Log "DONE" "MySQL 初始化完成"
    }

    Write-Log "INFO" "正在启动 MySQL..."

    $mysqlArgs = @("--console")
    if (Test-Path $MySQLIni) {
        $mysqlArgs = @("--defaults-file=`"$MySQLIni`"", "--console")
    }

    if ($Bg) {
        Start-Process -FilePath $MySQLExe `
            -ArgumentList $mysqlArgs `
            -NoNewWindow `
            -RedirectStandardOutput $MySQLLog `
            -RedirectStandardError (Join-Path $LogDir "mysql_err.log")
    } else {
        Start-Process -FilePath $MySQLExe `
            -ArgumentList $mysqlArgs `
            -NoNewWindow
    }

    # 等待 MySQL 启动（最多 30 秒）
    $waited = 0
    $maxWait = 30
    while (-not (Test-MySQL) -and $waited -lt $maxWait) {
        Start-Sleep -Seconds 2
        $waited += 2
    }

    if (Test-MySQL) {
        $mysqlPid = Get-MySQLPid
        Write-Log "DONE" "MySQL 已启动 (PID: $mysqlPid, 端口: ${MySQLPort})"
        return $true
    } else {
        Write-Log "ERROR" "MySQL 启动超时（已等待 ${maxWait}s），请检查: $MySQLLog"
        return $false
    }
}

function Stop-MySQL {
    if (Test-MySQL) {
        $mysqlPid = Get-MySQLPid
        Write-Log "INFO" "正在停止 MySQL (PID: $mysqlPid)..."
        Stop-ByPort $MySQLPort | Out-Null
        # 确认已停止
        Start-Sleep -Seconds 3
        if (Test-MySQL) {
            Write-Log "WARN" "MySQL 未能正常停止，尝试强制终止..."
            Stop-Process -Id $mysqlPid -Force -ErrorAction SilentlyContinue | Out-Null
        }
        Write-Log "DONE" "MySQL 已停止"
    } else {
        Write-Log "INFO" "MySQL 未运行"
    }
}

#==============================================================================
# QMT Gateway 服务管理
#==============================================================================

function Test-Gateway {
    return Test-Port $PortGateway
}

function Get-GatewayPid {
    if (Test-Path $GatewayPidFile) {
        $savedId = Get-Content $GatewayPidFile -Raw
        if ($savedId) {
            $savedId = $savedId.Trim()
            try {
                $proc = Get-Process -Id ([int]$savedId) -ErrorAction SilentlyContinue
                if ($proc -and $proc.ProcessName -like "*python*") {
                    return [int]$savedId
                }
            } catch { }
        }
    }
    return Get-PidByPort $PortGateway
}

function Start-Gateway {
    Write-Log "START" "启动 QMT Gateway 服务..."

    $oldPid = Get-GatewayPid
    if ($oldPid) {
        Write-Log "WARN" "Gateway 已在运行 (PID: $oldPid)，先停止旧进程..."
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 2
    }

    if (-not (Test-Path $GatewayScript)) {
        Write-Log "ERROR" "Gateway 启动脚本不存在: $GatewayScript"
        return $false
    }

    # 设置 Gateway 环境变量
    $env:QMT_API_TOKEN = $GatewayToken
    $env:QMT_GATEWAY_HOST = "127.0.0.1"
    $env:QMT_GATEWAY_PORT = "$PortGateway"

    $gatewayArgs = @(
        "`"$GatewayScript`""
    )

    $proc = Start-Process -FilePath $VenvPython `
        -ArgumentList $gatewayArgs `
        -WorkingDirectory $GatewayDir `
        -NoNewWindow `
        -PassThru

    $proc.Id | Out-File -FilePath $GatewayPidFile -NoNewline
    Start-Sleep -Seconds 5

    if (-not $proc.HasExited) {
        Write-Log "DONE" "QMT Gateway 已启动 (PID: $($proc.Id), 端口: ${PortGateway}, URL: $UrlGateway)"
        return $true
    } else {
        Write-Log "ERROR" "QMT Gateway 启动失败，请查看日志: $GatewayLog"
        Remove-Item $GatewayPidFile -ErrorAction SilentlyContinue
        return $false
    }
}

function Stop-Gateway {
    $gwPid = Get-GatewayPid
    if ($gwPid) {
        Write-Log "INFO" "正在停止 QMT Gateway (PID: $gwPid)..."
        Stop-Process -Id $gwPid -Force -ErrorAction SilentlyContinue | Out-Null
        Remove-Item $GatewayPidFile -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Write-Log "DONE" "QMT Gateway 已停止"
        return $true
    }
    Write-Log "INFO" "QMT Gateway 未运行"
    return $true
}

#==============================================================================
# 环境检查
#==============================================================================

function Check-Dependencies {
    Write-Log "INFO" "检查依赖环境..."

    $missing = @()

    # 检查虚拟环境 Python
    if (Test-Path $VenPython) {
        $ver = & $VenPython --version 2>&1
        Write-Log "DONE" "虚拟环境 Python: $ver"
    } else {
        Write-Log "ERROR" "虚拟环境未找到: $VenPython"
        Write-Log "INFO" "请先创建虚拟环境: python -m venv venv"
        return $false
    }

    # 检查 Node.js
    if (Test-Command "node") {
        $ver = node --version 2>&1
        Write-Log "DONE" "Node.js 已安装 (版本: $ver)"
    } else {
        $missing += "Node.js"
    }

    # 检查 npm
    if (Test-Command "cmd.exe") {
        $ver = npm --version 2>&1
        Write-Log "DONE" "npm 已安装 (版本: $ver)"
    } else {
        $missing += "cmd.exe"
    }

    if ($missing.Count -gt 0) {
        Write-Log "ERROR" "缺少以下依赖: $($missing -join ', ')"
        Write-Log "INFO" "请从 https://nodejs.org 安装 Node.js"
        return $false
    }

    Write-Log "DONE" "环境检查完成"
    return $true
}

#==============================================================================
# 端口检查
#==============================================================================

function Check-Ports {
    Write-Log "INFO" "检查端口占用情况..."
    $allFree = $true

    $ports = @{
        "QMT Gateway:${PortGateway}" = $PortGateway
        "后端:${PortBackend}" = $PortBackend
        "前端:${PortFrontend}" = $PortFrontend
        "Streamlit:${PortStreamlit}" = $PortStreamlit
    }

    foreach ($name in $ports.Keys) {
        $port = $ports[$name]
        if (Test-Port $port) {
            $occPid = Get-PidByPort $port
            Write-Log "WARN" "${name} 端口已被占用 (PID: $occPid)"
            $allFree = $false
        } else {
            Write-Log "DONE" "${name} 端口可用"
        }
    }

    return $allFree
}

function Stop-AllServices {
    Write-Log "INFO" "停止所有服务..."
    Stop-FeishuBot
    Stop-Gateway
    foreach ($port in @($PortBackend, $PortFrontend, $PortStreamlit)) {
        if (Stop-ByPort $port) {
            Write-Log "DONE" "已停止端口 $port"
        }
    }
    Start-Sleep -Seconds 1
}

#==============================================================================
# 服务启动函数
#==============================================================================

function Start-Backend {
    Write-Log "START" "启动后端API服务..."

    $env:PYTHONPATH = $ProjectRoot  # 设为项目根目录，确保 backend 包能被正确导入

    $uvicornArgs = @(
        "-m", "uvicorn", "backend.app:app",
        "--host", "127.0.0.1",
        "--port", $PortBackend
    )

    if ($Mode -eq "dev") {
        $uvicornArgs += "--reload"
    }

    if ($Bg) {
        $proc = Start-Process -FilePath $VenPython `
            -ArgumentList $uvicornArgs `
            -WorkingDirectory $ProjectRoot `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput (Join-Path $LogDir "backend.log") `
            -RedirectStandardError (Join-Path $LogDir "backend_err.log")
    } else {
        $proc = Start-Process -FilePath $VenPython `
            -ArgumentList $uvicornArgs `
            -WorkingDirectory $ProjectRoot `
            -NoNewWindow `
            -PassThru
    }

    # 等待后端启动（最多 30 秒）
    $waited = 0
    $maxWait = 30
    while (-not (Test-Port $PortBackend) -and $waited -lt $maxWait -and (-not $proc.HasExited)) {
        Start-Sleep -Seconds 1
        $waited++
    }

    if (Test-Port $PortBackend) {
        $actualPid = Get-PidByPort $PortBackend
        Write-Log "DONE" "后端API已启动 (PID: $actualPid, URL: $UrlBackend)"
        return $true
    } else {
        Write-Log "ERROR" "后端API启动失败"
        return $false
    }
}

function Start-Frontend {
    Write-Log "START" "启动前端应用..."

    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Log "INFO" "正在安装前端依赖..."
        Push-Location $FrontendDir
        npm install 2>&1 | Out-Null
        Pop-Location
    }

    if ($Bg) {
        $proc = Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c", "npm", "run", "dev" `
            -WorkingDirectory $FrontendDir `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput (Join-Path $LogDir "frontend.log") `
            -RedirectStandardError (Join-Path $LogDir "frontend_err.log")
    } else {
        $proc = Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c", "npm", "run", "dev" `
            -WorkingDirectory $FrontendDir `
            -NoNewWindow `
            -PassThru
    }

    # 等待前端启动（最多 60 秒，Vite 启动可能较慢）
    $waited = 0
    $maxWait = 60
    while (-not (Test-Port $PortFrontend) -and $waited -lt $maxWait -and (-not $proc.HasExited)) {
        Start-Sleep -Seconds 1
        $waited++
    }

    if (Test-Port $PortFrontend) {
        $actualPid = Get-PidByPort $PortFrontend
        Write-Log "DONE" "前端已启动 (PID: $actualPid, URL: $UrlFrontend)"
        return $true
    } else {
        Write-Log "ERROR" "前端启动失败"
        return $false
    }
}

function Start-Streamlit {
    Write-Log "START" "启动AI对话机器人..."

    $appFile = Join-Path $StreamlitDir "app.py"
    if (-not (Test-Path $appFile)) {
        Write-Log "ERROR" "Streamlit 应用文件不存在: $appFile"
        return $false
    }

    $streamlitArgs = @(
        "-m", "streamlit", "run", "streamlit_chat/app.py",
        "--server.port", $PortStreamlit,
        "--server.headless", "true"
    )

    if ($Bg) {
        $proc = Start-Process -FilePath $VenPython `
            -ArgumentList $streamlitArgs `
            -NoNewWindow `
            -PassThru `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput (Join-Path $LogDir "streamlit.log") `
            -RedirectStandardError (Join-Path $LogDir "streamlit_err.log")
    } else {
        $proc = Start-Process -FilePath $VenPython `
            -ArgumentList $streamlitArgs `
            -NoNewWindow `
            -PassThru `
            -WorkingDirectory $ProjectRoot
    }

    Start-Sleep -Seconds 8

    if (Test-Port $PortStreamlit) {
        $actualPid = Get-PidByPort $PortStreamlit
        Write-Log "DONE" "AI对话机器人已启动 (PID: $actualPid, URL: $UrlStreamlit)"
        return $true
    } else {
        Write-Log "ERROR" "AI对话机器人启动失败"
        return $false
    }
}

#==============================================================================
# 服务管理
#==============================================================================

function Show-Status {
    Write-Host ""
    Write-Host "=============================================="
    Write-Host "       AI Quant 服务状态"
    Write-Host "=============================================="
    Write-Host ""

    $items = @(
        @{Name="QMT Gateway 服务:${PortGateway}"; Port=$PortGateway; Url=$UrlGateway},
        @{Name="FastAPI 后端服务:${PortBackend}"; Port=$PortBackend; Url=$UrlBackend},
        @{Name="React 前端(含管理后台):${PortFrontend}"; Port=$PortFrontend; Url=$UrlAdmin},
        @{Name="Streamlit AI对话:${PortStreamlit}"; Port=$PortStreamlit; Url=$UrlStreamlit}
    )

    foreach ($item in $items) {
        $label = "{0,-24}" -f $item.Name
        if (Test-Port $item.Port) {
            $svcPid = Get-PidByPort $item.Port
            Write-Host "${label} " -NoNewline
            Write-Host "● 运行中" -ForegroundColor Green -NoNewline
            Write-Host " (PID: $svcPid)"
            Write-Host "  $($item.Url)" -ForegroundColor Cyan
        } else {
            Write-Host "${label} " -NoNewline
            Write-Host "○ 已停止" -ForegroundColor Red
        }
        Write-Host ""
    }

    # MySQL 数据库
    $mysqlLabel = "{0,-24}" -f "MySQL 数据库:${MySQLPort}"
    if (Test-MySQL) {
        $mysqlPid = Get-MySQLPid
        Write-Host "${mysqlLabel} " -NoNewline
        Write-Host "● 运行中" -ForegroundColor Green -NoNewline
        Write-Host " (PID: $mysqlPid, 127.0.0.1)"
    } else {
        Write-Host "${mysqlLabel} " -NoNewline
        Write-Host "○ 已停止" -ForegroundColor Red
    }
    Write-Host ""

    # 飞书机器人
    $feishuLabel = "{0,-24}" -f "飞书机器人(WebSocket)"
    if (Test-FeishuBot) {
        $botPid = Get-FeishuBotPid
        Write-Host "${feishuLabel} " -NoNewline
        Write-Host "● 运行中" -ForegroundColor Green -NoNewline
        Write-Host " (PID: $botPid)"
    } else {
        Write-Host "${feishuLabel} " -NoNewline
        Write-Host "○ 已停止" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "=============================================="
}

function Cleanup {
    Write-Log "INFO" "正在清理..."
    Stop-FeishuBot
    Stop-Gateway
    foreach ($port in @($PortBackend, $PortFrontend, $PortStreamlit)) {
        Stop-ByPort $port 2>$null
    }
    # 清理 PID 文件
    Remove-Item $FeishuBotPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $GatewayPidFile -Force -ErrorAction SilentlyContinue
    # 停止 MySQL（由脚本启动的则停止）
    if (Test-MySQL) {
        $confirmMySQL = Read-Host "是否同时停止 MySQL 数据库? (y/N)"
        if ($confirmMySQL -match "^[Yy]") {
            Stop-MySQL
        }
    }
    Write-Log "DONE" "清理完成"
}

#==============================================================================
# 显示函数
#==============================================================================

function Show-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "║              AI Quant 智能量化投资系统                        ║" -ForegroundColor Green
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Help {
    Write-Host @"

AI Quant 一键启动脚本 (Windows PowerShell)

用法:
    .\start_all.ps1 [选项]

选项:
    -Dev        开发模式 (默认，含热重载)
    -Prod       生产模式
    -Bg         后台运行模式（日志输出到文件）
    -Status     查看服务状态
    -Kill       停止所有服务
    -Help       显示此帮助信息

示例:
    .\start_all.ps1              # 开发模式启动
    .\start_all.ps1 -Dev         # 开发模式启动
    .\start_all.ps1 -Prod -Bg    # 生产模式后台运行
    .\start_all.ps1 -Status      # 查看服务状态
    .\start_all.ps1 -Kill        # 停止所有服务

服务说明:
    本地 MySQL:       127.0.0.1:3306 (自动检测和启动)
    QMT Gateway:       $UrlGateway  (本地 MiniQMT 交易网关)
    后端API:            $UrlBackend  (FastAPI)
    前端(含管理后台):    $UrlFrontend   (React + Vite)
                      $UrlAdmin（管理后台）
    AI对话机器人:        $UrlStreamlit  (Streamlit)
    飞书机器人:          (WebSocket 长连接，无 HTTP 端口)

启动顺序:
    MySQL -> Gateway -> 后端 -> 前端 -> Streamlit -> 飞书机器人

日志位置:
    $LogDir\

"@ -ForegroundColor Cyan
}

#==============================================================================
# 主函数
#==============================================================================

function Main {
    # 处理特殊命令
    if ($Help) { Show-Help; return }
    if ($Status) { Show-Status; return }
    if ($Kill) { Show-Banner; Cleanup; return }

    # 设置运行模式
    if ($Prod) { $script:Mode = "prod" }

    # 创建日志目录
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    # 显示横幅
    Show-Banner

    # 环境检查
    if (-not (Check-Dependencies)) {
        Write-Log "ERROR" "环境检查失败，无法启动服务"
        exit 1
    }

    Write-Host ""

    # 端口检查
    if (-not (Check-Ports)) {
        Write-Host ""
        $confirm = Read-Host "是否停止现有服务并继续? (y/N)"
        if ($confirm -match "^[Yy]") {
            Stop-AllServices
        } else {
            Write-Log "INFO" "用户取消启动"
            return
        }
    }

    Write-Host ""
    Write-Log "INFO" "模式: ${Mode}, 后台运行: $Bg"
    Write-Log "INFO" "开始启动服务..."
    Write-Host ""

    # 按顺序启动服务
    $failed = @()

    # 1. 先启动 MySQL（如果未运行）
    Write-Log "INFO" "--- 数据库层 ---"
    if (-not (Start-MySQL))  { $failed += "mysql" }

    Write-Host ""
    Write-Log "INFO" "--- 交易网关层 ---"
    if (-not (Start-Gateway))  { $failed += "gateway" }

    Write-Host ""
    Write-Log "INFO" "--- 应用服务层 ---"

    if (-not (Start-Backend))  { $failed += "backend" }
    if (-not (Start-Frontend)) { $failed += "frontend" }
    if (-not (Start-Streamlit)) { $failed += "streamlit" }
    if (-not (Start-FeishuBot)) { $failed += "feishu_bot" }

    # 结果报告
    Write-Host ""
    Write-Host "=============================================="
    Write-Host "       启动结果"
    Write-Host "=============================================="
    Write-Host ""

    if ($failed.Count -eq 0) {
        Write-Log "DONE" "所有服务启动成功!"
        Write-Host ""
        Write-Host "访问链接:" -ForegroundColor Green
        Write-Host "  QMT Gateway:        $UrlGateway" -ForegroundColor Cyan
        Write-Host "  后端API:            $UrlBackend" -ForegroundColor Cyan
        Write-Host "  前端(含管理后台):    $UrlFrontend  (管理后台: $UrlAdmin)" -ForegroundColor Cyan
        Write-Host "  AI对话机器人:        $UrlStreamlit" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "服务说明:" -ForegroundColor Yellow
        Write-Host "  飞书机器人作为独立进程运行（WebSocket 长连接），无 HTTP 端口"
        Write-Host "  管理后台已集成在前端应用内，通过 $UrlAdmin 访问" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "按任意键停止所有服务..." -ForegroundColor Yellow
        Write-Host "=============================================="
        Write-Host ""

        if (-not $Bg) {
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            Cleanup
        }
    } else {
        Write-Log "ERROR" "以下服务启动失败: $($failed -join ', ')"
        Write-Log "INFO" "未成功后端的日志路径: $LogDir"
        Write-Host ""
        $confirm = Read-Host "是否停止已启动的服务? (y/N)"
        if ($confirm -match "^[Yy]") {
            Cleanup
        }
        exit 1
    }
}

# 运行主函数
Main





