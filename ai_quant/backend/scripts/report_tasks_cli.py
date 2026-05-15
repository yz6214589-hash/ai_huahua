#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报任务 CLI 查询工具

用法:
    # 查询最近 10 条任务
    python report_tasks_cli.py --limit 10

    # 按状态筛选
    python report_tasks_cli.py --status success --limit 20

    # 按模型筛选（模糊匹配）
    python report_tasks_cli.py --model deepseek --limit 20

    # 按时间范围筛选
    python report_tasks_cli.py --start 2026-01-01 --end 2026-05-14

    # 组合筛选
    python report_tasks_cli.py --status success --model qwen --limit 50

    # 下载研报
    python report_tasks_cli.py --download <task_id>

    # 列出最近 3 天的成功任务
    python report_tasks_cli.py --status success --days 3

环境变量:
    WUCAI_SQL_HOST / DB_HOST / MYSQL_HOST
    WUCAI_SQL_PORT / DB_PORT / MYSQL_PORT
    WUCAI_SQL_USERNAME / DB_USER / MYSQL_USER
    WUCAI_SQL_PASSWORD / DB_PASSWORD / MYSQL_PASSWORD
    WUCAI_SQL_DB / DB_NAME / MYSQL_DB
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("[错误] 需要安装 pymysql: pip install pymysql", file=sys.stderr)
    sys.exit(1)


def _load_dotenv() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv
        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(env_path, override=False)
        else:
            load_dotenv()
    except Exception:
        pass


def _mysql_config() -> dict:
    _load_dotenv()
    return {
        "host": os.getenv("WUCAI_SQL_HOST") or os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "127.0.0.1",
        "port": int(os.getenv("WUCAI_SQL_PORT") or os.getenv("DB_PORT") or os.getenv("MYSQL_PORT") or "3306"),
        "user": os.getenv("WUCAI_SQL_USERNAME") or os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root",
        "password": os.getenv("WUCAI_SQL_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or "",
        "database": os.getenv("WUCAI_SQL_DB") or os.getenv("DB_NAME") or os.getenv("MYSQL_DB") or "huahua_trade",
        "charset": "utf8mb4",
    }


def _ensure_table(conn) -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS report_tasks (
        id VARCHAR(64) PRIMARY KEY,
        created_at DATETIME NOT NULL,
        status VARCHAR(20) NOT NULL,
        report_path TEXT,
        model VARCHAR(50),
        use_rag BOOLEAN DEFAULT FALSE,
        use_web BOOLEAN DEFAULT FALSE,
        finish_time DATETIME,
        updated_at DATETIME NOT NULL,
        stock_codes TEXT,
        stock_names TEXT,
        mode VARCHAR(32),
        error_message TEXT,
        INDEX idx_status (status),
        INDEX idx_created_at (created_at),
        INDEX idx_model (model)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _query_tasks(
    status: str | None = None,
    model: str | None = None,
    created_start: str | None = None,
    created_end: str | None = None,
    limit: int = 50,
) -> list[dict]:
    cfg = _mysql_config()
    try:
        conn = pymysql.connect(**cfg)
    except Exception as e:
        print(f"[错误] 无法连接 MySQL: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        _ensure_table(conn)
        conditions: list[str] = []
        params: list = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if model:
            conditions.append("model LIKE %s")
            params.append(f"%{model}%")
        if created_start:
            conditions.append("created_at >= %s")
            params.append(created_start)
        if created_end:
            conditions.append("created_at <= %s")
            params.append(created_end)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, created_at, status, report_path, model,
                   use_rag, use_web, finish_time, updated_at,
                   stock_codes, stock_names, mode, error_message
            FROM report_tasks
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(min(limit, 500))

        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

        for row in rows:
            for key in ("use_rag", "use_web"):
                if key in row and row[key] is not None:
                    row[key] = bool(row[key])
        return rows
    finally:
        conn.close()


def _format_row(row: dict) -> str:
    status_icon = {"success": "[OK]", "failed": "[FAIL]", "running": "[RUN]", "waiting": "[WAIT]"}
    icon = status_icon.get(row.get("status", ""), "[???]")
    use_rag = "RAG" if row.get("use_rag") else "---"
    use_web = "WEB" if row.get("use_web") else "---"
    stocks = row.get("stock_codes", "")
    try:
        stocks_list = json.loads(stocks) if stocks else []
        stocks_str = ", ".join(stocks_list[:3])
        if len(stocks_list) > 3:
            stocks_str += f" (+{len(stocks_list) - 3})"
    except Exception:
        stocks_str = stocks[:40] if stocks else ""

    finish = row.get("finish_time")
    finish_str = ""
    if finish:
        if hasattr(finish, "strftime"):
            finish_str = finish.strftime("%m-%d %H:%M")
        else:
            finish_str = str(finish)[:16]

    return (
        f"  {icon} [{row['id'][:12]}...] "
        f"{row.get('model', ''):12s} {use_rag}/{use_web} "
        f"{stocks_str} "
        f"| 完成: {finish_str}"
    )


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="研报任务 CLI 查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--status", dest="status", help="按状态精确过滤（success/failed/running/waiting）")
    parser.add_argument("--model", dest="model", help="按模型模糊过滤（如 deepseek / qwen）")
    parser.add_argument("--start", dest="created_start", help="创建时间起点（YYYY-MM-DD）")
    parser.add_argument("--end", dest="created_end", help="创建时间终点（YYYY-MM-DD）")
    parser.add_argument("--days", dest="days", type=int, help="最近 N 天内的任务（覆盖 --start）")
    parser.add_argument("--limit", dest="limit", type=int, default=50, help="最大返回条数（默认 50）")
    parser.add_argument("--download", dest="download", help="下载指定 task_id 的研报文件")
    parser.add_argument("--json", dest="json_output", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--count", dest="count", action="store_true", help="只输出计数")

    args = parser.parse_args()

    if args.download:
        _load_dotenv()
        task_id = args.download
        cfg = _mysql_config()
        try:
            conn = pymysql.connect(**cfg)
        except Exception as e:
            print(f"[错误] 无法连接 MySQL: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            _ensure_table(conn)
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT report_path, stock_codes FROM report_tasks WHERE id=%s",
                    (task_id,),
                )
                row = cur.fetchone()
            if not row:
                print(f"[错误] 未找到任务: {task_id}", file=sys.stderr)
                sys.exit(1)
            path = row.get("report_path")
            if not path:
                print("[错误] 该任务没有关联的报告文件", file=sys.stderr)
                sys.exit(1)
            p = Path(path)
            if not p.exists():
                print(f"[错误] 文件不存在: {path}", file=sys.stderr)
                sys.exit(1)
            content = p.read_text(encoding="utf-8")
            print(content)
        finally:
            conn.close()
        return

    created_start = args.created_start
    if args.days:
        created_start = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    rows = _query_tasks(
        status=args.status,
        model=args.model,
        created_start=created_start,
        created_end=args.created_end,
        limit=args.limit,
    )

    if args.count:
        print(len(rows))
        return

    if args.json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return

    if not rows:
        print("[无记录]")
        return

    print(f"共 {len(rows)} 条记录:")
    print("-" * 120)
    for row in rows:
        print(_format_row(row))
    print("-" * 120)
    print(f"总计: {len(rows)} 条 | 成功: {sum(1 for r in rows if r.get('status') == 'success')} | "
          f"失败: {sum(1 for r in rows if r.get('status') == 'failed')}")


if __name__ == "__main__":
    _main()
