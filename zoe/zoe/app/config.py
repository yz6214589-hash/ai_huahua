from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    port: int

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    presets_path: str
    instances_path: str


def load_settings() -> Settings:
    load_dotenv()

    host = os.getenv("ZOE_HOST", "127.0.0.1")
    port = int(os.getenv("ZOE_PORT", "8010"))

    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME", "wucai_trade")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "root")

    presets_path = os.getenv("PRESETS_PATH", "./zoe/data/strategy_presets.json")
    instances_path = os.getenv("INSTANCES_PATH", "./zoe/data/strategy_instances.json")

    return Settings(
        host=host,
        port=port,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        presets_path=presets_path,
        instances_path=instances_path,
    )

