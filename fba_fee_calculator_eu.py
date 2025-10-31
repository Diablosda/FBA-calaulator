"""
FBA费用计算器
根据Excel文件中的实际数据计算FBA配送费用
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import ast
import operator as op
from typing import List, Dict, Optional, Any
import os
import re
import glob

class FBAFeeCalculator_eu:
    """FBA费用计算器类"""
    
    def __init__(self, excel_path: str = '欧洲逻辑.xlsx', fee_table_path: str = '英德逻辑一维表.csv'):
        """初始化计算器"""
        self.excel_path = excel_path
        self.fee_table_path = fee_table_path
        self.dimension_rules = None
        self.fee_table = None
        
        # 单位转换常量
        self.inches_TO_CM = 2.54
        self.CM_TO_inches = 1 / 2.54
        self.pounds_TO_OUNCE = 16
        self.OUNCE_TO_pounds = 1 / 16
        self.KG_TO_pounds = 2.20462
        self.G_TO_pounds = 0.00220462
        
        # 加载Excel数据
        self.load_excel_data()
    
    def _resolve_path(self, path: str) -> str:
        """尝试将相对路径解析为脚本目录下的绝对路径；如果给定路径存在则直接返回"""
        if os.path.isabs(path) and os.path.exists(path):
            return path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(base_dir, path)
        if os.path.exists(cand):
            return cand
        # 搜索相似文件（例如 excel 名称不完全一致）
        name = os.path.splitext(os.path.basename(path))[0]
        patterns = [
            os.path.join(base_dir, f"{name}.*"),
            os.path.join(base_dir, f"*{name}*.*"),
        ]
        for p in patterns:
            found = glob.glob(p)
            if found:
                return found[0]
        # 返回原始（可能不存在），由调用方处理不存在情况
        return cand
    
    def load_excel_data(self):
        """加载Excel数据，带路径回退与容错"""
        try:
            # 解析并尝试读取尺寸分段数据（优先 Excel）
            excel_full = self._resolve_path(self.excel_path)
            if os.path.exists(excel_full):
                try:
                    self.dimension_rules = pd.read_excel(excel_full, sheet_name='尺寸分段')
                    print(f"尺寸分段数据从 {excel_full} 加载成功，形状: {self.dimension_rules.shape}")
                except Exception as e:
                    print(f"从 Excel 读取尺寸分段失败: {e}，尝试将该文件作为 CSV 读取")
                    try:
                        self.dimension_rules = pd.read_csv(excel_full)
                        print(f"尺寸分段数据（CSV）从 {excel_full} 加载成功，形状: {self.dimension_rules.shape}")
                    except Exception as e2:
                        print(f"读取尺寸分段仍然失败: {e2}，将使用空的默认规则")
                        self.dimension_rules = pd.DataFrame()
            else:
                print(f"未找到尺寸分段文件: {excel_full}，将尝试在同目录查找或使用默认规则")
                self.dimension_rules = pd.DataFrame()

            # 读取费用表数据 (CSV文件)，尝试不同编码
            fee_full = self._resolve_path(self.fee_table_path)
            if os.path.exists(fee_full):
                try:
                    self.fee_table = pd.read_csv(fee_full, encoding='GB2312')
                except Exception:
                    try:
                        self.fee_table = pd.read_csv(fee_full, encoding='utf-8')
                    except Exception as e:
                        print(f"读取费用表失败: {e}，将使用空的费用表")
                        self.fee_table = pd.DataFrame()
            else:
                print(f"未找到费用表文件: {fee_full}，将使用空的费用表")
                self.fee_table = pd.DataFrame()
            
            # 重置索引以确保数据完整性
            if isinstance(self.fee_table, pd.DataFrame):
                self.fee_table = self.fee_table.reset_index(drop=True)
            
            print("费用表数据加载完成")
            if isinstance(self.fee_table, pd.DataFrame):
                print(f"费用表数据形状: {self.fee_table.shape}")
                if '商品价格' in self.fee_table.columns:
                    print("\n价格区间:", self.fee_table['商品价格'].unique().tolist())
                if '商品尺寸' in self.fee_table.columns:
                    print("\n商品尺寸:", self.fee_table['商品尺寸'].unique().tolist())
            
            return True
        except Exception as e:
            print(f"加载数据失败: {e}")
            print("将使用默认规则")
            self.dimension_rules = pd.DataFrame()
            self.fee_table = pd.DataFrame()
            return False
    
    def convert_units(self, value: float, from_unit: str, to_unit: str) -> float:
        """单位转换"""
        if from_unit == to_unit:
            return value
            
        # 长度单位转换
        if from_unit == 'centimeters' and to_unit == 'inches':
            return value * self.CM_TO_inches
        elif from_unit == 'inches' and to_unit == 'centimeters':
            return value * self.inches_TO_CM
            
        # 重量单位转换
        elif from_unit == 'grams' and to_unit == 'kilograms':
            return value * self.G_TO_KG
        elif from_unit == 'kilograms' and to_unit == 'grams':
            return value / self.G_TO_KG        
        return value

    def is_special_oversize_europe(self, length: float, width: float, height: float, product_weight: float) -> bool:
        """
        判断是否为欧洲特殊大件
        
        Args:
            length: 最长边 (cm)
            width: 次长边 (cm) 
            height: 最短边 (cm)
            product_weight: 商品重量 (g)
            
        Returns:
            bool: 是否为特殊大件
        """
        # 特殊大件判断条件
        girth = length + 2 * (width + height)  # 围长
        
        conditions = [
            product_weight > 31500,  # 重量 > 31500g
            length > 175,            # 最长边 > 175cm
            girth > 360              # 围长 > 360cm
        ]
        
        return any(conditions)

    def determine_european_size_category(self, length: float, width: float, height: float,
                                       product_weight: float) -> str:
        """
        根据欧洲规则确定商品尺寸分类
        
        Args:
            length: 最长边 (cm)
            width: 次长边 (cm)
            height: 最短边 (cm)
            product_weight: 商品重量 (g)
            
        Returns:
            str: 商品尺寸分类
        """
        # 首先检查是否为特殊大件
        if self.is_special_oversize_europe(length, width, height, product_weight):
            return "特殊大件"
        
        # 计算体积重量
        volume_weight = self.calculate_volume_weight(length, width, height)
        
        # 信封类型 - 只考虑商品重量和尺寸
        envelope_categories = [
            ("轻型信封", 100, 33, 23, 2.5),
            ("标准信封", 460, 33, 23, 2.5),
            ("大号信封", 960, 33, 23, 4),
            ("超大号信封", 960, 33, 23, 6)
        ]
        
        for category, max_weight, max_len, max_width, max_height in envelope_categories:
            if (product_weight <= max_weight and
                length <= max_len and
                width <= max_width and
                height <= max_height):
                return category
        
        # 小包裹 - 需要满足所有条件
        if (length <= 35 and width <= 25 and height <= 12 and
            product_weight <= 3900 and volume_weight <= 2100):
            return "小包裹"
        
        # 标准包裹 - 需要满足所有条件
        if (length <= 45 and width <= 34 and height <= 26 and
            product_weight <= 11900 and volume_weight <= 7960):
            return "标准包裹"
        
        # 小号大件 - 需要满足所有条件
        if (length <= 61 and width <= 46 and height <= 46 and
            product_weight <= 1760 and volume_weight <= 25820):
            return "小号大件"
        
        # 轻型标准大件 - 需要满足所有条件
        if (length <= 101 and width <= 60 and height <= 60 and
            product_weight <= 15000 and volume_weight <= 72720):
            return "轻型标准大件"
        
        # 重型标准大件 - 需要满足所有条件
        if (length <= 101 and width <= 60 and height <= 60 and
            15000 < product_weight <= 23000 and volume_weight <= 72720):
            return "重型标准大件"
        
        # 大号标准大件 - 需要满足所有条件
        if (length <= 120 and width <= 60 and height <= 60 and
            product_weight <= 23000 and volume_weight <= 86400):
            return "大号标准大件"
        
        # 特大号大件 - 只需要满足重量和体积重量条件（尺寸条件为空）
        if (product_weight <= 23000 and volume_weight <= 126000):
            return "特大号大件"
        
        # 超重型大件 - 只需要满足重量和体积重量条件（尺寸条件为空）
        if (product_weight <= 31500 and volume_weight <= 126000):
            return "超重型大件"
        
        # 如果以上都不满足，默认为特殊大件
        return "特殊大件"

    
    def calculate_volume_weight(self, length: float, width: float, height: float) -> float:
        """计算体积重量"""
        # 欧洲体积重量公式：长*宽*高/5000 (单位：厘米，结果：千克)，然后转换为克
        volume_weight_kg = (length * width * height) / 5000
        return volume_weight_kg * 1000  # 转换为克
    
    def determine_european_shipping_weight(self, product_weight: float, volume_weight: float, 
                                        size_category: str) -> float:
        """
        确定欧洲发货重量
        
        Args:
            product_weight: 商品重量 (g)
            volume_weight: 体积重量 (g)
            size_category: 商品尺寸分类
            
        Returns:
            float: 发货重量 (g)
        """
        # 信封和特殊大件只使用商品重量
        if size_category in ["轻型信封", "标准信封", "大号信封", "超大号信封", "特殊大件"]:
            return product_weight
        else:
            # 其他类型取商品重量和体积重量较大值
            return max(product_weight, volume_weight)

    def calculate_european_fee_from_table(self, size_category: str, shipping_weight: float, 
                                        country: str, period: str, 
                                        product_weight: Optional[float] = None,
                                        volume_weight: Optional[float] = None) -> float:
        """
        计算欧洲FBA费用
        
        Args:
            size_category: 商品尺寸分类
            shipping_weight: 发货重量 (g)
            country: 国家 ('英国' 或 '德国')
            period: 时期
            product_weight: 商品实际重量 (g)，用于重量回退
            volume_weight: 体积重量 (g)，用于重量回退
            
        Returns:
            float: FBA费用
        """
        try:
            # 1. 在费用表中查找匹配记录
            mask = (
                (self.fee_table['时期'] == period) &
                (self.fee_table['国家'] == country) &
                (self.fee_table['商品尺寸'] == size_category)
            )
            matching_rows = self.fee_table[mask]
            
            if len(matching_rows) == 0:
                print(f"未找到匹配记录: 时期={period}, 国家={country}, 尺寸={size_category}")
                return 0.0
                
            # 2. 尝试使用shipping_weight计算
            fee = self._find_fee_by_weight(matching_rows, shipping_weight, 
                                        size_category, country, period)
            if fee > 0:
                return fee
                
            # 3. 如果shipping_weight匹配失败，尝试使用其他重量
            if product_weight is not None and product_weight != shipping_weight:
                print(f"尝试使用实际重量: {product_weight}g")
                fee = self._find_fee_by_weight(matching_rows, product_weight,
                                            size_category, country, period)
                if fee > 0:
                    return fee
                    
            if volume_weight is not None and volume_weight != shipping_weight:
                print(f"尝试使用体积重量: {volume_weight}g")
                fee = self._find_fee_by_weight(matching_rows, volume_weight,
                                            size_category, country, period)
                if fee > 0:
                    return fee
            
            print(f"所有重量值都无法匹配: shipping_weight={shipping_weight}g, product_weight={product_weight}g, volume_weight={volume_weight}g")
            return 0.0
            
        except Exception as e:
            print(f"计算费用时出错: {e}")
            return 0.0

    def _find_fee_by_weight(self, matching_rows: pd.DataFrame, weight: float, 
                        size_category: str, country: str, period: str) -> float:
        """
        在匹配的行中根据重量查找费用
        
        Args:
            matching_rows (pd.DataFrame): 匹配的费用表行
            period (str): 时期
            
        Returns:
            float: 费用，如果未找到则返回0
        """
        for _, row in matching_rows.iterrows():
            weight_range = str(row['发货重量'])
            fee = str(row['FBA费用'])
            
            # 检查重量是否在范围内
            if self._check_weight_in_range(weight, weight_range):
                # 调试信息
                print(f"\n计算费用详情:")
                print(f"商品尺寸: {size_category}")
                print(f"使用的重量: {weight}磅 (匹配范围: {weight_range})")
                print(f"国家: {country}")
                print(f"时期: {period}")
                print(f"匹配到的费用规则: {fee}")
                
                # 清理费用字符串（去除$和逗号）
            
                fee_clean = fee.replace('£', '').replace('€', '').replace(',', '')
                
                # 如果是纯数字，直接返回
                if fee_clean.replace('.', '').isdigit():
                    final_fee = float(fee_clean)
                    print(f"固定费用: ${final_fee}")
                    return final_fee
                
                # 如果是公式，需要计算
                try:
                    # 将公式中的"发货重量"替换为实际值
                    formula = fee_clean.replace('发货重量', str(weight))
                    print(f"计算公式: {formula}")
                    
                    # 使用eval计算公式
                    result = eval(formula)
                    final_fee = round(float(result), 2)
                    print(f"计算结果: ${final_fee}")
                    return final_fee
                    
                except Exception as e:
                    print(f"计算公式出错: {e}, 原始公式: {fee}, 处理后公式: {formula}")
                    return 0.0
                    
        return 0.0

    def _check_weight_in_range(self, weight: float, weight_range: str) -> bool:
        """
        检查重量是否在指定范围内 (欧洲版本)
        
        Args:
            weight (float): 发货重量(g)
            weight_range (str): 重量范围字符串，如"<=20g"
            
        Returns:
            bool: 是否在范围内
        """
        try:
            # 移除单位和空格
            clean_range = weight_range.replace('g', '').strip()
            
            # 记录原始范围便于调试
            print(f"检查重量 {weight}g 是否在范围 {clean_range} 内")
            
            # 处理 <= x 格式
            if clean_range.startswith('<='):
                limit = float(clean_range[2:].strip())
                result = weight <= limit
                print(f"小于等于判断: {weight} <= {limit} = {result}")
                return result
                
            # 处理 < x 格式
            if clean_range.startswith('<'):
                limit = float(clean_range[1:].strip())
                result = weight < limit
                print(f"小于判断: {weight} < {limit} = {result}")
                return result
                
            # 处理 >= x 格式
            if clean_range.startswith('>='):
                limit = float(clean_range[2:].strip())
                result = weight >= limit
                print(f"大于等于判断: {weight} >= {limit} = {result}")
                return result
                
            # 处理 > x 格式
            if clean_range.startswith('>'):
                limit = float(clean_range[1:].strip())
                result = weight > limit
                print(f"大于判断: {weight} > {limit} = {result}")
                return result
            
            print(f"无法解析的重量范围格式: {clean_range}")
            return False
            
        except Exception as e:
            print(f"检查重量范围出错: {e}, 范围: {weight_range}")
            return False


    def process_product_dataframe(self, df: pd.DataFrame, periods: List[str]) -> pd.DataFrame:
        """处理包含多个产品信息的DataFrame"""
        result_df = df.copy()
        
        # 添加新列
        result_df['european_size_category'] = ''
        result_df['european_shipping_weight_g'] = 0.0
        result_df['european_country'] = ''
        
        # 为每个时期添加费用列
        for period in periods:
            result_df[f'fba_fee_{period}'] = 0.0
        
        # 遍历处理每行数据
        for idx, row in result_df.iterrows():
            try:
                # 1. 确定国家
                store = str(row['amazon-store']).strip().upper()
                if store == 'GB':
                    country = '英国'
                elif store == 'DE':
                    country = '德国'
                else:
                    print(f"警告: 未知的amazon-store值 '{store}'，跳过处理")
                    continue
                    
                # 2. 单位转换 - 尺寸和重量 (这里应该已经是厘米和克)
                length = float(row['longest-side'])
                width = float(row['median-side'])
                height = float(row['shortest-side'])
                weight = float(row['item-package-weight'])
                
                # 3. 计算体积重量
                volume_weight = self.calculate_volume_weight(length, width, height)
                
                # 4. 确定尺寸分类
                size_category = self.determine_european_size_category(
                    length, width, height, weight
                )
                
                # 5. 确定发货重量
                shipping_weight = self.determine_european_shipping_weight(
                    weight, volume_weight, size_category
                )
                
                # 6. 保存基础信息
                result_df.at[idx, 'european_size_category'] = size_category
                result_df.at[idx, 'european_shipping_weight_g'] = round(shipping_weight, 3)
                result_df.at[idx, 'european_country'] = country
                
                # 7. 计算每个时期的费用
                for period in periods:
                    fee = self.calculate_european_fee_from_table(
                        size_category=size_category,
                        shipping_weight=shipping_weight,
                        country=country,
                        period=period,
                        product_weight=weight,
                        volume_weight=volume_weight
                    )
                    result_df.at[idx, f'fba_fee_{period}'] = round(fee, 2)
                    
            except Exception as e:
                print(f"处理SKU {row.get('fnsku', '未知')} 时出错: {e}")
                continue
                
        return result_df
    
    def process_file(self, file_path: str, periods: List[str] = ["2024Q1", "2024Q2", "2024Q3"]) -> pd.DataFrame:
        """
        从文件读取产品数据并处理
        
        Args:
            file_path (str): 输入文件路径（支持Excel或CSV）
            periods (List[str]): 需要计算的时期列表
            
        Returns:
            pd.DataFrame: 处理后的DataFrame
        """
        try:
            # 尝试读取文件
            if file_path.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except:
                    df = pd.read_csv(file_path, encoding='gbk')
            else:
                df = pd.read_excel(file_path)
            
            # 检查必要的列是否存在
            required_columns = [
                'fnsku', 
                'amazon-store',
                'longest-side',
                'median-side', 
                'shortest-side',
                'unit-of-dimension',
                'item-package-weight',
                'unit-of-weight'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                print(f"警告：缺少必要的列: {', '.join(missing_columns)}")
                return pd.DataFrame()
            
            # 处理数据
            result_df = self.process_product_dataframe(df, periods)
            
            # 添加计算结果统计
            print("\n处理完成！")
            print(f"总处理商品数: {len(result_df)}")           
            
            return result_df
            
        except Exception as e:
            print(f"处理文件出错: {e}")
            return pd.DataFrame()


   
def main():
    """主函数 - 示例用法"""
    calculator = FBAFeeCalculator_eu()

if __name__ == "__main__":
    main()