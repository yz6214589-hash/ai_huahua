import os

import uvicorn


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    reload = bool(int(os.getenv("KIRS_RELOAD", "0") or "0"))
    uvicorn.run("kris_api.app:app", host="0.0.0.0", port=8011, reload=reload)
