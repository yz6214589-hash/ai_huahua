"""
QMT Gateway 服务启动脚本

通过 uvicorn 启动 FastAPI 应用服务器。
服务器配置可通过环境变量进行自定义。
"""

import os

import uvicorn


if __name__ == "__main__":
    host = str(os.getenv("QMT_GATEWAY_HOST", "0.0.0.0"))
    port = int(str(os.getenv("QMT_GATEWAY_PORT", "8001")))
    uvicorn.run("app:app", host=host, port=port, reload=False)
