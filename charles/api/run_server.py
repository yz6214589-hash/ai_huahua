import os
import sys
import uvicorn


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.dont_write_bytecode = True
    reload = bool(int(os.getenv("CHARLES_RELOAD", "0") or "0"))
    uvicorn.run("charles_api.app:app", host="0.0.0.0", port=8000, reload=reload)
