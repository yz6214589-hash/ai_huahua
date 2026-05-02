import pymysql
import os
import time
import re

# ====================== 【可配置参数】 ======================
SQL_FILE = r"G:\夸克\trade_stock_daily.sql"    # SQL文件路径
DB_HOST = "localhost"             # 数据库IP
DB_PORT = 3306                    # 端口
DB_NAME = "huahua_trade"               # 数据库名
DB_TABLE = "trade_stock_daily"           # 表名
DB_USER = "root"                  # 账号
DB_PASS = "root"                # 密码

# 性能参数（不用改）
BATCH_COMMIT = 1000    # 每1000条提交一次
READ_BUFFER = 1024*1024*4  # 4MB分块读取
PROGRESS_WIDTH = 30
PROGRESS_REFRESH_SEC = 0.2
UPSERT_EXCLUDE_FIELDS = set()
# ===========================================================

def connect_db():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=60
    )

def get_table_columns(cursor):
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        ORDER BY ORDINAL_POSITION
        """.strip(),
        (DB_NAME, DB_TABLE),
    )
    return [r[0] for r in cursor.fetchall()]

def make_upsert(sql, fallback_fields=None):
    sql = sql.strip().rstrip(";")
    low = sql.lower()
    if "on duplicate key update" in low:
        return sql + ";"

    if not low.startswith("insert"):
        return None

    m = re.search(r"\bvalues\b", sql, flags=re.IGNORECASE)
    if not m:
        return None

    fields_part = sql[: m.start()].strip()
    values_part = sql[m.end() :].strip()
    fields_part = re.sub(r"^insert\s+ignore\s+into\b", "INSERT INTO", fields_part, flags=re.IGNORECASE)

    l = fields_part.find("(")
    r = fields_part.rfind(")")

    fields = None
    if l != -1 and r != -1 and r > l:
        fields_str = fields_part[l + 1 : r]
        parts = [p.strip() for p in fields_str.split(",")]
        fields = [p.strip("` ") for p in parts if p.strip("` ")]
    else:
        if fallback_fields:
            fields = list(fallback_fields)

    if not fields:
        return None

    update_fields = [f for f in fields if f not in UPSERT_EXCLUDE_FIELDS]
    if not update_fields:
        return None

    update = ", ".join(f"`{f}`=VALUES(`{f}`)" for f in update_fields)
    return f"{fields_part} VALUES {values_part} ON DUPLICATE KEY UPDATE {update};"

def _progress_text(done_bytes, total_bytes, count, start_ts):
    if total_bytes and total_bytes > 0:
        percent = int(done_bytes * 100 / total_bytes)
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        filled = int(PROGRESS_WIDTH * percent / 100)
        bar = "█" * filled + "░" * (PROGRESS_WIDTH - filled)
        sec = time.time() - start_ts
        speed = count / sec if sec > 0 else 0.0
        return f"[{bar}] {percent:3d}% | 已导入 {count:,} 行 | {speed:.1f} 行/秒"

    sec = time.time() - start_ts
    speed = count / sec if sec > 0 else 0.0
    return f"[{'░' * PROGRESS_WIDTH}]  ?% | 已导入 {count:,} 行 | {speed:.1f} 行/秒"

def _print_progress(done_bytes, total_bytes, count, start_ts):
    print(_progress_text(done_bytes, total_bytes, count, start_ts), end="\r", flush=True)

def import_big_sql():
    print("=" * 60)
    print(f"开始导入大SQL：{SQL_FILE}")
    print(f"目标表：{DB_HOST}:{DB_PORT}/{DB_NAME}.{DB_TABLE}")
    print("=" * 60)

    conn = connect_db()
    cursor = conn.cursor()
    start = time.time()
    count = 0
    batch = []

    try:
        fallback_fields = get_table_columns(cursor)
        total_bytes = os.path.getsize(SQL_FILE)
        last_show_ts = 0.0
        last_percent = -1

        with open(SQL_FILE, "rb", buffering=READ_BUFFER) as f:
            for raw_line in f:
                done_bytes = f.tell()
                now = time.monotonic()
                if total_bytes and total_bytes > 0:
                    percent = int(done_bytes * 100 / total_bytes)
                    if percent != last_percent or now - last_show_ts >= PROGRESS_REFRESH_SEC:
                        _print_progress(done_bytes, total_bytes, count, start)
                        last_percent = percent
                        last_show_ts = now
                else:
                    if now - last_show_ts >= PROGRESS_REFRESH_SEC:
                        _print_progress(done_bytes, total_bytes, count, start)
                        last_show_ts = now

                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith("--") or line.startswith("#"):
                    continue

                upsert = make_upsert(line, fallback_fields=fallback_fields)
                if upsert:
                    batch.append(upsert)
                    count += 1

                if len(batch) >= BATCH_COMMIT:
                    for s in batch:
                        cursor.execute(s)
                    conn.commit()
                    batch = []
                    _print_progress(done_bytes, total_bytes, count, start)
                    print()
                    speed = count / (time.time() - start)
                    print(f"已导入 {count:,} 行 | 速度：{speed:.1f} 行/秒")

        # 剩余数据
        if batch:
            for s in batch:
                cursor.execute(s)
            conn.commit()

        _print_progress(total_bytes, total_bytes, count, start)
        print()

        # 完成
        total_sec = time.time() - start
        print("✅ 导入完成！")
        print(f"总行数：{count:,}")
        print(f"耗时：{total_sec:.2f}s")
        print(f"平均速度：{count/total_sec:.1f} 行/秒")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 失败：{str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import_big_sql()