from __future__ import annotations

import os

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass

FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BOT_LOG_LEVEL: str = os.getenv("FEISHU_BOT_LOG_LEVEL", "INFO")
