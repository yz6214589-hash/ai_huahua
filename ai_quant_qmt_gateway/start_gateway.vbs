Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\apps\qmt_gateway"
WshShell.Run "cmd /c python run_server.py", 0, False
