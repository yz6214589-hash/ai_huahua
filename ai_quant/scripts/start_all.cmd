@echo off
set ROOT=%~dp0..

start "AI_QUANT_BACKEND" cmd /k "cd /d %ROOT%\backend && python run_server.py"
start "AI_QUANT_WEB" cmd /k "cd /d %ROOT%\web && npm run dev"
start "AI_QUANT_STREAMLIT" cmd /k "cd /d %ROOT%\streamlit_chat && streamlit run app.py --server.port 8501"
