import os
import uvicorn


if __name__ == "__main__":
    reload = bool(int(os.getenv("CHARLES_RELOAD", "0") or "0"))
    uvicorn.run("charles_api.app:app", host="0.0.0.0", port=8000, reload=reload)

