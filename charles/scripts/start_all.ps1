$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $Root
$WebDir = Join-Path $Root "web"

Write-Host ("Root: " + $Root)

$backendCmd = @(
  "cd `"$Root`""
  "if (Test-Path `"$Root\.venv\Scripts\Activate.ps1`") { . `"$Root\.venv\Scripts\Activate.ps1`" } elseif (Test-Path `"$RepoRoot\.venv\Scripts\Activate.ps1`") { . `"$RepoRoot\.venv\Scripts\Activate.ps1`" }"
  "python api/run_server.py"
) -join "; "

$frontendCmd = @(
  "cd `"$WebDir`""
  "if (-not (Test-Path `"$WebDir\node_modules`")) { npm install }"
  "npm run dev"
) -join "; "

Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCmd)
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd)

Write-Host "Started backend + frontend."
