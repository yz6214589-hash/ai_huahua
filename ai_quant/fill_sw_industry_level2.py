#!/usr/bin/env python3
"""
补全申万一级、二级行业数据
基于申万行业标准分类和现有数据构建映射关系
"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config
import pymysql
from datetime import datetime

# 申万行业标准映射关系
# 一级行业 -> [二级行业列表]
# 注意：这是简化版本，基于常见的申万行业分类
SW_INDUSTRY_MAPPING = {
    "银行": ["银行"],
    "全国地产": ["房地产开发", "房地产开发Ⅱ"],
    "区域地产": ["房地产开发Ⅱ"],
    "房产服务": ["房地产服务"],
    "软件服务": ["计算机应用", "软件开发", "互联网服务"],
    "运输设备": ["铁路设备", "船舶制造", "航天装备"],
    "电气设备": ["电源设备", "电力设备", "电气设备"],
    "建筑工程": ["建筑装饰", "建筑材料"],
    "其他商业": ["商贸零售", "商业贸易"],
    "玻璃": ["建材", "玻璃陶瓷"],
    "IT设备": ["计算机设备", "通信设备"],
    "元器件": ["电子元件", "半导体"],
    "机械基件": ["通用机械", "专用设备"],
    "专用机械": ["专用设备", "工程机械"],
    "汽车": ["汽车整车", "汽车零部件"],
    "电力设备": ["电力设备", "电源设备", "电池"],
    "医药生物": ["化学制药", "生物制品", "医疗服务", "医疗器械", "医药商业"],
    "化工原料": ["化学制品", "化学原料", "塑料"],
    "半导体": ["半导体", "集成电路"],
    "轻工制造": ["家用轻工", "造纸", "包装印刷"],
    "有色金属": ["贵金属", "金属新材料", "小金属"],
    "传媒": ["游戏", "数字媒体", "出版"],
    "通信": ["通信设备", "通信服务"],
    "环境保护": ["环境治理", "园林工程"],
    "商贸零售": ["百货零售", "多业态零售"],
    "房地产": ["房地产开发", "房地产服务"],
    "社会服务": ["旅游及景区", "酒店餐饮", "教育"],
    "非银金融": ["证券", "保险", "多元金融"],
    "食品": ["食品加工", "食品饮料"],
    "石油": ["油气开采", "石化"],
    "仓储物流": ["物流", "交通运输"],
    "百货": ["百货零售"],
    "超市": ["连锁超市"],
    "多元金融": ["多元金融"],
    "证券": ["证券"],
    "保险": ["保险"],
    "电信运营": ["通信服务"],
    "农业综合": ["农林牧渔"],
    "林业": ["林业"],
    "园区开发": ["园区开发"],
    "公共交通": ["交通运输"],
    "船舶制造": ["船舶制造"],
    "航空运输": ["航空运输"],
    "港口": ["港口"],
    "机场": ["机场"],
    "高速公路": ["高速公路"],
    "路桥": ["路桥", "交通运输"],
    "空运": ["航空运输"],
    "水运": ["港口航运"],
    "旅游服务": ["旅游及景区"],
    "酒店餐饮": ["酒店餐饮"],
    "综合类": ["综合"],
    "其他建材": ["建材"],
    "其他机械": ["通用机械"],
    "其他化工": ["化工"],
    "其他电子": ["电子"],
    "其他服务": ["社会服务"],
    "其他金融": ["非银金融"],
    "其他房地产": ["房地产"],
    "其他商贸": ["商贸零售"],
    "其他医药": ["医药生物"],
    "其他食品": ["食品"],
    "其他汽车": ["汽车"],
    "其他电气": ["电气设备"],
    "其他建筑": ["建筑装饰"],
    "其他通信": ["通信"],
    "其他计算机": ["计算机"],
    "其他传媒": ["传媒"],
    "其他军工": ["国防军工"],
    "其他钢铁": ["钢铁"],
    "其他有色": ["有色金属"],
    "其他家电": ["家用电器"],
    "其他纺织": ["纺织服装"],
    "其他轻工": ["轻工制造"],
    "其他农林牧渔": ["农林牧渔"],
    "其他餐饮旅游": ["社会服务"],
    "其他交运": ["交通运输"],
    "其他公用": ["公用事业"],
    "其他综合": ["综合"],
    "其他": ["其他"],
}

# 对于只在一级行业中出现的行业，我们创建一个简单的映射
# 如果一级行业没有对应的二级行业，我们将一级行业本身作为二级行业
def get_secondary_industry(primary_industry):
    """
    根据一级行业获取二级行业
    """
    if not primary_industry:
        return None
    
    # 查找映射关系
    if primary_industry in SW_INDUSTRY_MAPPING:
        # 返回第一个二级行业（最常见的）
        return SW_INDUSTRY_MAPPING[primary_industry][0]
    
    # 如果没有找到映射，将一级行业本身作为二级行业
    return primary_industry

def fill_sw_industry_level2():
    """
    补全申万二级行业数据
    """
    print("=" * 70)
    print("补全申万一级、二级行业数据")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )
    
    try:
        cursor = conn.cursor()
        
        # 步骤1: 统计当前数据状态
        print("\n步骤1: 统计当前数据状态")
        print("-" * 70)
        cursor.execute('''
            SELECT COUNT(*) as total
            FROM trade_stock_master
            WHERE stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
        ''')
        total = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) as has_l1
            FROM trade_stock_master
            WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
        ''')
        has_l1 = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) as has_l2
            FROM trade_stock_master
            WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
        ''')
        has_l2 = cursor.fetchone()[0]
        
        print(f"总股票数: {total:,}")
        print(f"有一级行业: {has_l1:,} ({has_l1/total*100:.2f}%)")
        print(f"有二级行业: {has_l2:,} ({has_l2/total*100:.2f}%)")
        
        # 步骤2: 获取所有需要补全二级行业的股票
        print("\n步骤2: 获取需要补全二级行业的股票")
        print("-" * 70)
        cursor.execute('''
            SELECT stock_code, stock_name, sector_level1
            FROM trade_stock_master
            WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
              AND (sector_level2 IS NULL OR sector_level2 = "")
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
            ORDER BY stock_code
        ''')
        stocks = cursor.fetchall()
        print(f"需要补全二级行业的股票: {len(stocks):,} 只")
        
        if not stocks:
            print("\n没有需要补全的股票！")
            return
        
        # 步骤3: 补全二级行业数据
        print("\n步骤3: 开始补全二级行业数据")
        print("-" * 70)
        
        update_count = 0
        skip_count = 0
        
        for stock in stocks:
            stock_code, stock_name, sector_level1 = stock
            
            if not sector_level1:
                skip_count += 1
                continue
            
            # 获取对应的二级行业
            sector_level2 = get_secondary_industry(sector_level1)
            
            if sector_level2:
                try:
                    cursor.execute('''
                        UPDATE trade_stock_master
                        SET sector_level2 = %s, updated_at = NOW()
                        WHERE stock_code = %s
                    ''', (sector_level2, stock_code))
                    update_count += 1
                    
                    if update_count % 500 == 0:
                        print(f"已更新 {update_count:,} 只股票...")
                        
                except Exception as e:
                    print(f"更新 {stock_code} 失败: {e}")
                    skip_count += 1
        
        # 提交事务
        conn.commit()
        
        print(f"\n更新完成:")
        print(f"  成功更新: {update_count:,} 只")
        print(f"  跳过: {skip_count:,} 只")
        
        # 步骤4: 验证结果
        print("\n步骤4: 验证补全结果")
        print("-" * 70)
        
        cursor.execute('''
            SELECT COUNT(*) as has_l2_new
            FROM trade_stock_master
            WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
        ''')
        has_l2_new = cursor.fetchone()[0]
        
        print(f"补全后二级行业覆盖: {has_l2_new:,} ({has_l2_new/total*100:.2f}%)")
        
        # 显示一些样本
        cursor.execute('''
            SELECT stock_code, stock_name, sector_level1, sector_level2
            FROM trade_stock_master
            WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
              AND sector_level2 IS NOT NULL AND sector_level2 != ""
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
            ORDER BY stock_code
            LIMIT 20
        ''')
        samples = cursor.fetchall()
        
        print("\n样本数据:")
        for sample in samples:
            print(f"{sample[0]} - {sample[1]}")
            print(f"  一级行业: {sample[2]}")
            print(f"  二级行业: {sample[3]}")
            print()
        
        # 统计二级行业分布
        print("\n二级行业分布 Top 20:")
        cursor.execute('''
            SELECT sector_level2, COUNT(*) as cnt
            FROM trade_stock_master
            WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
              AND stock_code NOT LIKE 'SWL%'
              AND stock_code NOT LIKE '000%'
              AND stock_code NOT LIKE '399%'
              AND stock_code NOT LIKE '880%'
            GROUP BY sector_level2
            ORDER BY cnt DESC
            LIMIT 20
        ''')
        sectors = cursor.fetchall()
        
        for s in sectors:
            print(f"{s[0]:20s} {s[1]:5d}")
        
        print("\n" + "=" * 70)
        print("补全完成！")
        print("=" * 70)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fill_sw_industry_level2()
