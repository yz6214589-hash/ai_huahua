$ErrorActionPreference = "Stop"
$RepoRoot = "/Users/apple/Desktop/ai_huahua"

function Ensure-PythonVenv {
    param([string]$VenvDir, [string]$ReqsFile, [string]$ProjectName)
    if (-not (Test-Path "$VenvDir/venv/bin/activate")) {
        Write-Host "[$ProjectName] Creating Python venv..."
        python3 -m venv "$VenvDir/venv"
        & "$VenvDir/venv/bin/pip" install -q --upgrade pip
        if (Test-Path $ReqsFile) {
            & "$VenvDir/venv/bin/pip" install -q -r $ReqsFile
        }
        Write-Host "[$ProjectName] venv ready."
    } else {
        Write-Host "[$ProjectName] venv already exists."
    }
}

function Ensure-NpmDeps {
    param([string]$NpmDir, [string]$ProjectName)
    if (-not (Test-Path "$NpmDir/node_modules")) {
        Write-Host "[$ProjectName] Installing npm deps..."
        npm install --prefix $NpmDir
        Write-Host "[$ProjectName] npm deps ready."
    } else {
        Write-Host "[$ProjectName] node_modules already exist."
    }
}

Write-Host "=== 1/5 Ethan ==="
Ensure-PythonVenv -VenvDir "$RepoRoot/ethan/backend" -ReqsFile "$RepoRoot/ethan/backend/requirements.txt" -ProjectName "Ethan-Backend"
Ensure-NpmDeps -NpmDir "$RepoRoot/ethan/frontend" -ProjectName "Ethan-Frontend"
Write-Host "[Ethan] Starting backend on 8001..."
cd "$RepoRoot/ethan/backend"
. "$RepoRoot/ethan/backend/venv/bin/activate"
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/ethan/backend' && . 'venv/bin/activate' && python -m uvicorn ethan_api.app:app --host 127.0.0.1 --port 8001" -WorkingDirectory "$RepoRoot/ethan/backend"
Write-Host "[Ethan] Starting frontend on 5178..."
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/ethan/frontend' && npm run dev -- --host 127.0.0.1 --port 5178" -WorkingDirectory "$RepoRoot/ethan/frontend"

Write-Host ""
Write-Host "=== 2/5 Kris ==="
Ensure-PythonVenv -VenvDir "$RepoRoot/kris/api" -ReqsFile "" -ProjectName "Kris-Backend"
Ensure-NpmDeps -NpmDir "$RepoRoot/kris/web" -ProjectName "Kris-Frontend"
Write-Host "[Kris] Starting backend on 8011..."
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/kris/api' && . '../api/venv/bin/activate' && python run_server.py" -WorkingDirectory "$RepoRoot/kris/api"
Write-Host "[Kris] Starting frontend on 5173..."
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/kris/web' && npm run dev -- --host 127.0.0.1" -WorkingDirectory "$RepoRoot/kris/web"

Write-Host ""
Write-Host "=== 3/5 CEO ==="
Ensure-PythonVenv -VenvDir "$RepoRoot/ceo" -ReqsFile "$RepoRoot/ceo/requirements.txt" -ProjectName "CEO"
Write-Host "[CEO] Starting on 7865..."
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/ceo' && . 'venv/bin/activate' && python app.py" -WorkingDirectory "$RepoRoot/ceo"

Write-Host ""
Write-Host "=== 4/5 Charles ==="
Ensure-NpmDeps -NpmDir "$RepoRoot/charles/web" -ProjectName "Charles-Frontend"
Write-Host "[Charles] Starting via start_all.ps1..."
& "$RepoRoot/charles/scripts/start_all.ps1"

Write-Host ""
Write-Host "=== 5/5 Zoe ==="
Ensure-PythonVenv -VenvDir "$RepoRoot/zoe" -ReqsFile "$RepoRoot/zoe/requirements.txt" -ProjectName "Zoe"
Write-Host "[Zoe] Starting on 8010..."
Start-Process -FilePath bash -ArgumentList "-c", "cd '$RepoRoot/zoe' && . 'venv/bin/activate' && python -m zoe.app.main" -WorkingDirectory "$RepoRoot/zoe"

Write-Host ""
Write-Host "=== All projects started! ==="
Write-Host "Ethan  : http://127.0.0.1:5178 (frontend) | http://127.0.0.1:8001 (api)"
Write-Host "Kris   : http://127.0.0.1:5173 (frontend) | http://127.0.0.1:8011 (api)"
Write-Host "CEO    : http://127.0.0.1:7865"
Write-Host "Charles: http://127.0.0.1:5173 (frontend) | http://127.0.0.1:8000 (api)"
Write-Host "Zoe    : http://127.0.0.1:8010"
