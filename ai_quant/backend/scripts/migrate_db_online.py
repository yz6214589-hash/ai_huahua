#!/usr/bin/env python3
"""
MySQL 在线迁移脚本：从腾讯云直接复制结构和数据到本地 MySQL
无需导出大 SQL 文件，直接表级在线复制
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymysql
from dotenv import load_dotenv, find_dotenv

# 加载 .env（此时已经修改为本地配置，所以这里硬编码云端配置）
CLOUD_HOST = "bj-cdb-6zjqetya.sql.tencentcdb.com"
CLOUD_PORT = 25341
CLOUD_USER = "root"
CLOUD_PASSWORD = "huahua1688"
CLOUD_DB = "huahua_trade"

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 3306
LOCAL_USER = "root"
LOCAL_PASSWORD = "huahua1688"
LOCAL_DB = "huahua_trade"

BATCH_SIZE = 5000


def cloud_connect():
    print(f"[云端] 连接: {CLOUD_HOST}:{CLOUD_PORT}")
    return pymysql.connect(
        host=CLOUD_HOST, port=CLOUD_PORT,
        user=CLOUD_USER, password=CLOUD_PASSWORD,
        database=CLOUD_DB, charset="utf8mb4",
        connect_timeout=30, read_timeout=600, write_timeout=600,
    )


def local_connect():
    print(f"[本地] 连接: {LOCAL_HOST}:{LOCAL_PORT}")
    return pymysql.connect(
        host=LOCAL_HOST, port=LOCAL_PORT,
        user=LOCAL_USER, password=LOCAL_PASSWORD,
        charset="utf8mb4",
        connect_timeout=10,
    )


def get_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables


def get_create_table(conn, table):
    cursor = conn.cursor()
    cursor.execute(f"SHOW CREATE TABLE `{table}`")
    row = cursor.fetchone()
    cursor.close()
    return row[1] if row else ""


def get_row_count(conn, table):
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def migrate_table(cloud_conn, local_conn, table):
    """迁移单个表：结构 + 数据"""
    t_start = time.time()
    
    # 1. 获取建表语句
    create_sql = get_create_table(cloud_conn, table)
    if not create_sql:
        print(f"  [跳过] {table}: 无法获取建表语句")
        return
    
    # 2. 在本地创建表
    local_cursor = local_conn.cursor()
    local_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
    local_cursor.execute(create_sql)
    local_conn.commit()
    local_cursor.close()
    
    # 3. 获取列信息
    cloud_cursor = cloud_conn.cursor()
    cloud_cursor.execute(f"SELECT * FROM `{table}` LIMIT 0")
    columns = [desc[0] for desc in cloud_cursor.description]
    col_names = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"
    cloud_cursor.close()
    
    # 4. 获取行数
    row_count = get_row_count(cloud_conn, table)
    
    if row_count == 0:
        elapsed = time.time() - t_start
        print(f"  [完成] {table}: 0 行 (空表) → {elapsed:.1f}s")
        return
    
    # 5. 流式复制数据
    cloud_cursor = cloud_conn.cursor(pymysql.cursors.SSCursor)
    cloud_cursor.execute(f"SELECT * FROM `{table}`")
    
    local_cursor = local_conn.cursor()
    batch = []
    total = 0
    last_report = time.time()
    
    while True:
        row = cloud_cursor.fetchone()
        if row is None:
            break
        
        batch.append(row)
        
        if len(batch) >= BATCH_SIZE:
            local_cursor.executemany(insert_sql, batch)
            local_conn.commit()
            total += len(batch)
            batch = []
            
            # 每 5 秒报告进度
            if time.time() - last_report > 5:
                pct = total / row_count * 100
                elapsed = time.time() - t_start
                print(f"  [进度] {table}: {total}/{row_count} ({pct:.1f}%) → {elapsed:.1f}s")
                last_report = time.time()
    
    # 写入剩余批次
    if batch:
        local_cursor.executemany(insert_sql, batch)
        local_conn.commit()
        total += len(batch)
    
    cloud_cursor.close()
    local_cursor.close()
    
    elapsed = time.time() - t_start
    print(f"  [完成] {table}: {total} 行 → {elapsed:.1f}s")


def main():
    print("=" * 60)
    print("MySQL 在线迁移: 腾讯云 → 本地")
    print("=" * 60)
    
    # 连接云端
    print("\n1. 连接数据库...")
    try:
        cloud_conn = cloud_connect()
    except Exception as e:
        print(f"[错误] 无法连接云端数据库: {e}")
        print("请确保网络可访问腾讯云 CDB")
        return 1
    
    try:
        local_conn = local_connect()
    except Exception as e:
        print(f"[错误] 无法连接本地 MySQL: {e}")
        print("请确保:")
        print("  1. 本地 MySQL Server 已安装并启动")
        print("  2. 端口 3306 未被占用")
        print("  3. root 密码为 huahua1688")
        return 1
    
    try:
        # 创建本地数据库
        print("\n2. 创建本地数据库...")
        local_cursor = local_conn.cursor()
        local_cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{LOCAL_DB}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        local_cursor.close()
        local_conn.select_db(LOCAL_DB)
        print(f"   数据库 {LOCAL_DB} 就绪")
        
        # 获取表列表
        print("\n3. 获取表列表...")
        tables = get_tables(cloud_conn)
        print(f"   共 {len(tables)} 个表")
        
        # 按依赖关系排序（先迁移无外键的表）
        tables_sorted = sorted(tables)
        
        # 禁用外键检查以加速导入
        local_cursor = local_conn.cursor()
        local_cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        local_cursor.close()
        
        # 迁移每个表
        print(f"\n4. 开始迁移 ({len(tables_sorted)} 个表)...")
        total_start = time.time()
        success = 0
        failed = []
        
        for i, table in enumerate(tables_sorted, 1):
            print(f"\n[{i}/{len(tables_sorted)}] {table}")
            try:
                migrate_table(cloud_conn, local_conn, table)
                success += 1
            except Exception as e:
                print(f"  [失败] {table}: {e}")
                failed.append((table, str(e)))
        
        # 恢复外键检查
        local_cursor = local_conn.cursor()
        local_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        local_cursor.close()
        
        total_elapsed = time.time() - total_start
        
        # 输出报告
        print("\n" + "=" * 60)
        print("迁移报告")
        print("=" * 60)
        print(f"  成功: {success} 个表")
        if failed:
            print(f"  失败: {len(failed)} 个表")
            for tbl, err in failed:
                print(f"    - {tbl}: {err}")
        print(f"  总耗时: {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")
        print("\n迁移完成!")
        
    finally:
        cloud_conn.close()
        local_conn.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
