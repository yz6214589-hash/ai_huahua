import os

import uvicorn


if __name__ == "__main__":
    host = str(os.getenv("QMT_GATEWAY_HOST", "0.0.0.0"))
    port = int(str(os.getenv("QMT_GATEWAY_PORT", "9001")))
    uvicorn.run("app:app", host=host, port=port, reload=False)

