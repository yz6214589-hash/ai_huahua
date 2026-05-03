$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/backend'; python run_server.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/web'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/streamlit_chat'; streamlit run app.py --server.port 8501"
