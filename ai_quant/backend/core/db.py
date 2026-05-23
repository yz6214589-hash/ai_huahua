"""
数据库连接和操作模块
提供MySQL数据库的连接管理、配置加载和基础CRUD操作功能
支持从多种环境变量格式读取数据库配置，兼容不同的部署环境
"""

from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Generator

import pymysql


@dataclass(frozen=True)
class MySQLConfig:
    """
    MySQL数据库配置数据类
    
    存储数据库连接所需的所有参数信息
    
    Attributes:
        host: 数据库主机地址
        port: 数据库端口号
        user: 数据库用户名
        password: 数据库密码
        database: 数据库名称
    """
    host: str
    port: int
    user: str
    password: str
    database: str


def _env_int(name: str, default: int) -> int:
    """
    从环境变量读取整数配置
    
    尝试将环境变量值转换为整数，如果转换失败则返回默认值
    
    Args:
        name: 环境变量名称
        default: 默认值
        
    Returns:
        int: 环境变量值或默认值
    """
    raw = os.getenv(name, "")
    try:
        return int(str(raw).strip() or default)
    except Exception:
        return default


def load_mysql_config() -> MySQLConfig:
    """
    加载MySQL数据库配置
    
    支持多种环境变量命名格式：
    - WUCAI_SQL_* (微财内部格式)
    - DB_* (通用格式)
    - MYSQL_* (MySQL标准格式)
    
    Returns:
        MySQLConfig: 数据库配置对象
    """
    # 尝试加载.env文件
    try:
        from dotenv import find_dotenv, load_dotenv

        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(env_path, override=False)
        else:
            load_dotenv()
    except Exception:
        pass

    # 依次尝试多种环境变量格式读取配置
    host = os.getenv("WUCAI_SQL_HOST") or os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "127.0.0.1"
    port = _env_int("WUCAI_SQL_PORT", _env_int("DB_PORT", _env_int("MYSQL_PORT", 3306)))
    user = os.getenv("WUCAI_SQL_USERNAME") or os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root"
    password = os.getenv("WUCAI_SQL_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or ""
    database = os.getenv("WUCAI_SQL_DB") or os.getenv("DB_NAME") or os.getenv("MYSQL_DB") or "huahua_trade"

    return MySQLConfig(
        host=str(host).strip() or "127.0.0.1",
        port=int(port),
        user=str(user).strip() or "root",
        password=str(password),
        database=str(database).strip() or "huahua_trade",
    )


class SimpleConnectionPool:
    _instance: SimpleConnectionPool | None = None
    _lock = threading.Lock()

    def __init__(self, cfg: MySQLConfig, pool_size: int = 5) -> None:
        import pymysql

        self._cfg = cfg
        self._pool: queue.Queue = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = pymysql.connect(
                host=cfg.host,
                port=cfg.port,
                user=cfg.user,
                password=cfg.password,
                database=cfg.database,
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=2,
                read_timeout=3,
                write_timeout=3,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self._pool.put(conn)

    def get_conn(self):
        try:
            conn = self._pool.get(timeout=5)
            try:
                conn.ping(reconnect=True)
            except Exception:
                import pymysql
                conn = pymysql.connect(
                    host=self._cfg.host,
                    port=self._cfg.port,
                    user=self._cfg.user,
                    password=self._cfg.password,
                    database=self._cfg.database,
                    charset="utf8mb4",
                    autocommit=True,
                    connect_timeout=2,
                    read_timeout=3,
                    write_timeout=3,
                    cursorclass=pymysql.cursors.DictCursor,
                )
            return conn
        except queue.Empty:
            import pymysql
            return pymysql.connect(
                host=self._cfg.host,
                port=self._cfg.port,
                user=self._cfg.user,
                password=self._cfg.password,
                database=self._cfg.database,
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=2,
                read_timeout=3,
                write_timeout=3,
                cursorclass=pymysql.cursors.DictCursor,
            )

    def return_conn(self, conn) -> None:
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass

    @classmethod
    def get_pool(cls, cfg: MySQLConfig | None = None, pool_size: int = 5) -> SimpleConnectionPool:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if cfg is None:
                        cfg = load_mysql_config()
                    cls._instance = cls(cfg, pool_size=pool_size)
        return cls._instance


def connect(cfg: MySQLConfig):
    pool = SimpleConnectionPool.get_pool(cfg)
    conn = pool.get_conn()
    return _PooledConnectionWrapper(conn, pool)


class _PooledConnectionWrapper:
    def __init__(self, conn, pool: SimpleConnectionPool) -> None:
        self._conn = conn
        self._pool = pool
        self._closed = False

    def cursor(self):
        return self._conn.cursor()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._pool.return_conn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def query_dict(conn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    """
    执行查询并返回字典列表
    
    使用参数化查询防止SQL注入，返回的每条记录都是字典格式
    
    Args:
        conn: 数据库连接对象
        sql: SQL查询语句
        params: 查询参数元组
        
    Returns:
        list[dict]: 查询结果列表，每项为字典格式
    """
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return list(rows or [])


def execute(conn, sql: str, params: tuple[Any, ...] | None = None) -> int:
    """
    执行单条SQL语句（INSERT/UPDATE/DELETE）
    
    使用参数化查询防止SQL注入
    
    Args:
        conn: 数据库连接对象
        sql: SQL语句
        params: 参数元组
        
    Returns:
        int: 影响的行数
    """
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(getattr(cur, "rowcount", 0) or 0)


def executemany(conn, sql: str, rows: Iterable[tuple[Any, ...]]) -> int:
    """
    批量执行SQL语句
    
    适用于大量数据的INSERT操作，使用excutemany提高执行效率。
    如果MySQL连接超时（OperationalError 2006/2013），会自动执行重连并重试一次。
    
    Args:
        conn: 数据库连接对象
        sql: SQL语句（应包含占位符）
        rows: 参数元组的可迭代对象
        
    Returns:
        int: 影响的行数
    """
    rows_list = list(rows)
    if not rows_list:
        return 0
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows_list)
            return int(getattr(cur, "rowcount", 0) or 0)
    except pymysql.OperationalError as e:
        # 捕获MySQL连接超时错误（2006=服务器已离开, 2013=查询期间丢失连接）
        err_code = getattr(e, "args", (0,))[0] if e.args else 0
        if err_code in (2006, 2013):
            # 延迟导入避免循环引用
            from infra.storage.logging_service import get_logger
            _logger = get_logger("db")
            _logger.warning("executemany MySQL连接超时，执行重连重试",
                           extra={"error_code": err_code, "rows_count": len(rows_list)})
            # 重新连接后重试一次
            new_cfg = load_mysql_config()
            new_conn = connect(new_cfg)
            try:
                with new_conn.cursor() as cur:
                    cur.executemany(sql, rows_list)
                    return int(getattr(cur, "rowcount", 0) or 0)
            finally:
                new_conn.close()
        # 非连接超时错误，继续向上抛出
        raise
