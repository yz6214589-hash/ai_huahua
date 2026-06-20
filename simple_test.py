import subprocess, urllib.request, json

with open("d:/BaiduNetdiskDownload/ai_huahua/ai_huahua/test_output.txt", "w") as f:
    try:
        req = urllib.request.Request("http://127.0.0.1:8001/health")
        resp = urllib.request.urlopen(req, timeout=5)
        f.write("health=" + str(resp.status) + "\n")
    except Exception as e:
        f.write("health_err=" + str(e) + "\n")
    
    try:
        data = json.dumps({}).encode()
        req = urllib.request.Request("http://127.0.0.1:8001/api/trading/connect", data=data, headers={"Content-Type": "application/json"}, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        f.write("connect=" + str(resp.status) + "\n")
        f.write("connect_body=" + resp.read().decode() + "\n")
    except urllib.error.HTTPError as e:
        f.write("connect_http=" + str(e.code) + "\n")
        f.write("connect_detail=" + e.read().decode() + "\n")
    except Exception as e:
        f.write("connect_err=" + str(e) + "\n")
    
    f.write("done\n")
