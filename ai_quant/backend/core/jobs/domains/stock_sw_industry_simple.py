"""
申万行业分类数据采集任务（简化版）
数据来源：akshare（东方财富/申万指数）
写入表：trade_stock_master

由于akshare的sw_index_third_cons接口存在bug，简化版只采集行业列表，
不包含成分股映射。成分股需要通过东方财富等其他数据源获取。
"""

from __future__ import annotations

from typing import Any
import pymysql
import os
from datetime import datetime

from core.jobs.common import JobStats


_INSERT_INDUSTRY_SQL = """
INSERT INTO trade_stock_master
(stock_code, stock_name, sector_level1, sector_level2, sector_level3, data_source, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
sector_level1=COALESCE(VALUES(sector_level1), sector_level1),
sector_level2=COALESCE(VALUES(sector_level2), sector_level2),
sector_level3=COALESCE(VALUES(sector_level3), sector_level3),
data_source=VALUES(data_source),
updated_at=NOW()
"""


def _fetch_sw_industry_lists() -> tuple[list[dict], int]:
    """
    获取申万行业分类列表

    Returns:
        tuple: (行业信息列表, 总数)
    """
    try:
        import akshare as ak

        industries = []
        total = 0

        # 获取申万一级行业（31个）
        print("获取申万一级行业...")
        df1 = ak.sw_index_first_info()
        for _, row in df1.iterrows():
            code = str(row['行业代码'])
            industries.append({
                'code': code,
                'name': row['行业名称'],
                'level': 1,
                'parent': None,
                'parent_name': None
            })
        print(f"  获取到 {len(df1)} 个一级行业")
        total += len(df1)

        # 获取申万二级行业（131个）
        print("获取申万二级行业...")
        df2 = ak.sw_index_second_info()
        for _, row in df2.iterrows():
            code = str(row['行业代码'])
            industries.append({
                'code': code,
                'name': row['行业名称'],
                'level': 2,
                'parent': None,
                'parent_name': row['上级行业']
            })
        print(f"  获取到 {len(df2)} 个二级行业")
        total += len(df2)

        # 获取申万三级行业（336个）
        print("获取申万三级行业...")
        df3 = ak.sw_index_third_info()
        for _, row in df3.iterrows():
            code = str(row['行业代码'])
            industries.append({
                'code': code,
                'name': row['行业名称'],
                'level': 3,
                'parent': None,
                'parent_name': row['上级行业']
            })
        print(f"  获取到 {len(df3)} 个三级行业")
        total += len(df3)

        return industries, total

    except Exception as e:
        print(f"获取申万行业列表失败: {e}")
        import traceback
        traceback.print_exc()
        return [], 0


def run_sw_industry_collection() -> JobStats:
    """
    运行申万行业分类采集任务

    由于akshare的sw_index_third_cons接口存在bug，
    本函数只采集行业列表信息，不包含成分股映射。

    成分股数据可以通过以下方式获取：
    1. 使用东方财富行业板块接口 stock_sector_spot
    2. 使用Tushare等付费数据源
    3. 使用Wind等机构数据源

    Returns:
        JobStats: 任务执行统计
    """
    print("=" * 60)
    print("申万行业分类采集任务开始")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 获取申万行业列表
    print("\n步骤1: 获取申万行业分类列表")
    industries, total_industries = _fetch_sw_industry_lists()
    print(f"获取到 {total_industries} 个行业分类")

    if total_industries == 0:
        print("未获取到任何行业数据，任务结束")
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="未获取到任何行业数据"
        )

    # 2. 连接数据库
    try:
        conn = pymysql.connect(
            host=os.getenv('WUCAI_SQL_HOST', 'localhost'),
            port=int(os.getenv('WUCAI_SQL_PORT', 3306)),
            user=os.getenv('WUCAI_SQL_USER', 'root'),
            password=os.getenv('WUCAI_SQL_PASSWORD', ''),
            database=os.getenv('WUCAI_SQL_DB', 'wucai_trade'),
            charset='utf8mb4'
        )
        print("\n数据库连接成功")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return JobStats(
            items_processed=total_industries,
            rows_written=0,
            failed_items=["database_connection"],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=f"数据库连接失败: {e}"
        )

    # 3. 保存行业数据
    print("\n步骤2: 保存行业数据到数据库")
    saved_count = 0
    failed_count = 0
    failed_list = []

    try:
        cursor = conn.cursor()

        for industry in industries:
            try:
                # 生成伪股票代码用于存储行业信息
                # 格式: SWL{level}{code}
                pseudo_code = f"SWL{industry['level']}{industry['code']}"

                cursor.execute(_INSERT_INDUSTRY_SQL, (
                    pseudo_code,
                    industry['name'],
                    industry['name'] if industry['level'] == 1 else None,
                    industry['name'] if industry['level'] == 2 else None,
                    industry['name'] if industry['level'] == 3 else None,
                    'akshare_sw'
                ))
                saved_count += 1

            except Exception as e:
                failed_count += 1
                failed_list.append(industry['code'])
                print(f"  保存行业 {industry['name']} 失败: {e}")

        conn.commit()
        cursor.close()

        print(f"\n保存完成:")
        print(f"  成功: {saved_count}")
        print(f"  失败: {failed_count}")

    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("申万行业分类采集任务完成")
    print("=" * 60)

    return JobStats(
        items_processed=total_industries,
        rows_written=saved_count,
        failed_items=failed_list[:100] if len(failed_list) > 100 else failed_list,
        data_source_final="akshare",
        fallback_chain=["akshare"],
        message=f"成功保存 {saved_count}/{total_industries} 个行业分类"
    )


if __name__ == "__main__":
    stats = run_sw_industry_collection()
    print("\n任务统计:")
    print(f"  处理项目数: {stats.items_processed}")
    print(f"  写入行数: {stats.rows_written}")
    print(f"  失败项目: {len(stats.failed_items)}")
    print(f"  数据源: {stats.data_source_final}")
    print(f"  消息: {stats.message}")
