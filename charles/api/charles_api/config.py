import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_db: str
    cors_origins: list[str]
    dashscope_api_key: str
    qwen_model: str
    kimi_api_key: str
    kimi_base_url: str
    kimi_model: str
    job_store_dir: str


def load_settings() -> Settings:
    load_dotenv()
    origins_raw = os.getenv("CHARLES_CORS_ORIGINS", "http://localhost:5173")
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    return Settings(
        mysql_host=os.getenv("WUCAI_SQL_HOST", "localhost"),
        mysql_port=int(os.getenv("WUCAI_SQL_PORT", "3306")),
        mysql_user=os.getenv("WUCAI_SQL_USERNAME", "root"),
        mysql_password=os.getenv("WUCAI_SQL_PASSWORD", ""),
        mysql_db=os.getenv("WUCAI_SQL_DB", "wucai_trade"),
        cors_origins=origins,
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        qwen_model=os.getenv("QWEN_MODEL", "qwen-max"),
        kimi_api_key=os.getenv("KIMI_API_KEY", ""),
        kimi_base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
        kimi_model=os.getenv("KIMI_MODEL", "kimi-latest"),
        job_store_dir=os.getenv("CHARLES_JOB_STORE_DIR", os.path.join(os.getcwd(), ".charles", "job_runs")),
    )

