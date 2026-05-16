#!/usr/bin/env python3
"""
SQLite模拟盘账户表迁移脚本
为risk_management.db创建模拟盘相关表
"""
import sqlite3
import os

DB_PATH = '/Users/apple/Desktop/ai_huahua/ai_quant/backend/risk_management.db'

def create_sim_account_table(conn):
    """创建模拟盘账户表"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sim_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL UNIQUE,
            initial_capital REAL NOT NULL DEFAULT 1000000.00,
            current_capital REAL NOT NULL DEFAULT 1000000.00,
            market_value REAL NOT NULL DEFAULT 0.00,
            total_asset REAL NOT NULL DEFAULT 1000000.00,
            total_pnl REAL NOT NULL DEFAULT 0.00,
            total_pnl_pct REAL NOT NULL DEFAULT 0.00,
            today_pnl REAL NOT NULL DEFAULT 0.00,
            today_pnl_pct REAL NOT NULL DEFAULT 0.00,
            position_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_reset_at DATETIME,
            description TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_account_status ON sim_account(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_account_created_at ON sim_account(created_at)")

    print("  sim_account 表创建成功")


def create_sim_position_table(conn):
    """创建模拟盘持仓表"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sim_position (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            volume INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0.00,
            cur_price REAL NOT NULL DEFAULT 0.00,
            market_value REAL NOT NULL DEFAULT 0.00,
            pnl REAL NOT NULL DEFAULT 0.00,
            pnl_pct REAL NOT NULL DEFAULT 0.00,
            available_volume INTEGER NOT NULL DEFAULT 0,
            frozen_volume INTEGER NOT NULL DEFAULT 0,
            position_type TEXT NOT NULL DEFAULT 'sim',
            buy_date DATE,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, stock_code)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_position_account_stock ON sim_position(account_id, stock_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_position_volume ON sim_position(volume)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_position_type ON sim_position(position_type)")

    print("  sim_position 表创建成功")


def create_sim_trade_table(conn):
    """创建模拟盘交易记录表"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sim_trade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            trade_no TEXT NOT NULL UNIQUE,
            order_no TEXT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            volume INTEGER NOT NULL,
            amount REAL NOT NULL,
            commission REAL NOT NULL DEFAULT 0.00,
            account_type TEXT NOT NULL DEFAULT 'sim',
            status TEXT NOT NULL DEFAULT 'filled',
            trade_time DATETIME NOT NULL,
            order_time DATETIME,
            strategy TEXT,
            remark TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trade_account_time ON sim_trade(account_id, trade_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trade_account_side ON sim_trade(account_id, side)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trade_stock ON sim_trade(stock_code, trade_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trade_type_time ON sim_trade(account_type, trade_time)")

    print("  sim_trade 表创建成功")


def create_sim_position_history_table(conn):
    """创建模拟盘持仓历史表"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sim_position_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            record_date DATE NOT NULL,
            total_asset REAL NOT NULL,
            market_value REAL NOT NULL,
            cash REAL NOT NULL,
            total_pnl REAL NOT NULL,
            total_pnl_pct REAL NOT NULL,
            day_pnl REAL NOT NULL,
            day_pnl_pct REAL NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, record_date)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_history_account_date ON sim_position_history(account_id, record_date)")

    print("  sim_position_history 表创建成功")


def init_default_account(conn):
    """初始化默认模拟盘账户"""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM sim_account")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
            INSERT INTO sim_account (account_name, initial_capital, current_capital, market_value, total_asset, description)
            VALUES ('默认模拟账户', 1000000.00, 1000000.00, 0.00, 1000000.00, '系统默认模拟盘账户，初始资金100万元')
        """)
        print("  默认模拟账户创建成功")
    else:
        print("  跳过默认账户创建（已存在）")


def main():
    """主函数"""
    print("=" * 60)
    print("SQLite模拟盘表迁移")
    print("=" * 60)
    print(f"数据库: {DB_PATH}")
    print()

    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"创建数据库目录: {db_dir}")

    conn = sqlite3.connect(DB_PATH)

    try:
        print("\n1. 创建 sim_account 表...")
        create_sim_account_table(conn)

        print("\n2. 创建 sim_position 表...")
        create_sim_position_table(conn)

        print("\n3. 创建 sim_trade 表...")
        create_sim_trade_table(conn)

        print("\n4. 创建 sim_position_history 表...")
        create_sim_position_history_table(conn)

        print("\n5. 初始化默认账户...")
        init_default_account(conn)

        conn.commit()

        print("\n" + "=" * 60)
        print("验证创建的表:")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sim_%'")
        tables = cursor.fetchall()
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} 条记录")

        print("\n" + "=" * 60)
        print("迁移完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
