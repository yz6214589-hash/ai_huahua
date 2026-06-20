# MySQL cleanup and restart script
$ErrorActionPreference = "Continue"

# 1. Kill any existing mysqld
Get-Process -Name mysqld -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2. Clean all attempts
Write-Host "Cleaning data dirs..."
$dirs = @(
    "C:\mysql\data",
    "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\.mysql_data",
    "$env:TEMP\mysql_data"
)
foreach ($d in $dirs) {
    if (Test-Path $d) {
        try { Remove-Item -Path $d -Recurse -Force -ErrorAction Stop; Write-Host "  Removed: $d" }
        catch { Write-Host "  Failed: $d - $_"}
    }
}

# 3. Create fresh data dir in temp
$dataDir = "$env:TEMP\mysql_data"
$tmpDir = "$env:TEMP\mysql_tmp"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
Write-Host "Created: $dataDir"

# 4. Write my.ini
$dataDirUnix = $dataDir -replace '\\', '/'
$tmpDirUnix = $tmpDir -replace '\\', '/'
$ini = @"
[mysqld]
basedir=C:/mysql
datadir=$dataDirUnix
tmpdir=$tmpDirUnix
port=3306
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default_authentication_plugin=mysql_native_password
max_allowed_packet=256M
skip-log-bin
"@
$ini | Set-Content -Path "C:\mysql\my.ini" -Encoding ASCII
Write-Host "my.ini written"

# 5. Initialize
Write-Host "Initializing MySQL..."
& "C:\mysql\bin\mysqld.exe" --defaults-file="C:\mysql\my.ini" --initialize-insecure --console 2>&1
Write-Host "Initialize exit: $LASTEXITCODE"

# 6. Start
Write-Host "Starting MySQL..."
& "C:\mysql\bin\mysqld.exe" --defaults-file="C:\mysql\my.ini" --console 2>&1
