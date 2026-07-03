@echo off
cd /d "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"
set FEISHU_APP_ID=cli_a967436bf9789cdb
set FEISHU_APP_SECRET=9bDNPJlteIY9TDD6hOCDKenNY8kxxqf6
"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\venv\Scripts\python.exe" "d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend\feishu\bot.py" > ".ai_quant\logs\feishu_bot.log" 2> ".ai_quant\logs\feishu_bot_err.log"
