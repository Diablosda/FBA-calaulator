"""
FBA费用计算器
根据Excel文件中的实际数据计算FBA配送费用
支持2024年和2026年不同的尺寸分类规则
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

class FBAFeeCalculator_us:
    """FBA费用计算器类"""
    
    def __init__(self, excel_path: str = '逻辑.xlsx', fee_table_path: str = '逻辑一维表.xlsx'):
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
                    self.fee_table = pd.read_csv(fee_full, encoding='gbk')
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
        elif from_unit == 'grams' and to_unit == 'pounds':
            return value * self.G_TO_pounds
        elif from_unit == 'pounds' and to_unit == 'grams':
            return value / self.G_TO_pounds
            
        return value
    
    def calculate_volume_weight(self, length: float, width: float, height: float) -> float:
        """计算体积重量"""
        return (length * width * height) / 139
    
    def determine_size_category_2024(self, length: float, width: float, height: float, 
                                    product_weight: float) -> str:
        """根据2024年规则确定商品尺寸分类"""
        dimensions = [length, width, height]
        dimensions.sort(reverse=True)
        longest, second_longest, shortest = dimensions
        
        # 计算发货重量(此处不需要特殊规则，直接取较大值)
        volume_weight = self.calculate_volume_weight(length, width, height)
        shipping_weight = max(product_weight, volume_weight)

        # 先判断是否是超大件（满足三个条件之一）
        is_oversize = (
            (longest > 59 and second_longest > 33 and shortest > 33) or  # 尺寸超限
            (longest + 2 * (second_longest + shortest) > 130) or         # 长度加围长超限
            (shipping_weight > 50)                                       # 重量超限
        )

        if is_oversize:
            # 根据重量细分超大件类别
            if shipping_weight > 150:
                return "超大件(>150磅)"
            elif shipping_weight > 70 and shipping_weight <= 150:
                return "超大件((70,150]磅)"
            elif shipping_weight > 50 and shipping_weight <= 70: 
                return "超大件((50,70]磅)"
            else:
                return "超大件((0,50]磅)"
        
        # 不是超大件，判断其他尺寸
        if longest <= 15 and second_longest <= 12 and shortest <= 0.75 and shipping_weight <= 1:
            return "小号标准尺寸"
        elif longest <= 18 and second_longest <= 14 and shortest <= 8 and shipping_weight <= 20:    
            return "大号标准尺寸"
        elif longest <= 59 and second_longest <= 33 and shortest <= 33 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
            return "大号大件"

        # 如果以上都不满足，默认为最小重量段的超大件
        return "超大件((0,50]磅)"
            
        # # 先判断是否为超大件(>150磅)
        # if shipping_weight > 150:
        #     return "超大件(>150磅)"
        # elif 70 < shipping_weight <= 150:
        #     return "超大件((70,150]磅)"
        # elif 50 < shipping_weight <= 70:
        #     return "超大件((50,70]磅)"
        
        # # # 检查是否为特大号商品（超大件的一种特殊情况）
        # # if longest > 96 or (longest + 2 * (second_longest + shortest)) > 130 :
        # #     if shipping_weight <= 50:
        # #         return "超大件((0,50]磅)"
        # #     elif shipping_weight <= 70 and shipping_weight > 50:
        # #         return "超大件((50,70]磅)"
        # #     elif shipping_weight <= 150 and shipping_weight > 70:
        # #         return "超大件((70,150]磅)"
        
        # # 根据尺寸和重量确定分类
        # if longest <= 15 and second_longest <= 12 and shortest <= 0.75 and shipping_weight <= 1:
        #     return "小号标准尺寸"
        # elif longest <= 18 and second_longest <= 14 and shortest <= 8 and shipping_weight <= 20:    
        #     return "大号标准尺寸"
        # elif longest <= 59 and second_longest <= 33 and shortest <= 33 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
        #     return "大号大件"
        # elif shipping_weight <= 50 or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((0,50]磅)"
        # elif (shipping_weight <= 70 and shipping_weight > 50) or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((50,70]磅)"
        # elif (shipping_weight <= 150 and shipping_weight > 70) or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((70,150]磅)"
        # elif shipping_weight > 150 or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件(>150磅)"
    
    def determine_size_category_2026(self, length: float, width: float, height: float, 
                                   product_weight: float) -> str:
        """根据2026年规则确定商品尺寸分类"""
        dimensions = [length, width, height]
        dimensions.sort(reverse=True)
        longest, second_longest, shortest = dimensions

        # 计算发货重量(此处不需要特殊规则，直接取较大值)
        volume_weight = self.calculate_volume_weight(length, width, height)
        shipping_weight = max(product_weight, volume_weight)

        # 先判断是否是超大件（满足三个条件之一）
        is_oversize = (
            (longest > 59 and second_longest > 33 and shortest > 33) or  # 尺寸超限
            (longest + 2 * (second_longest + shortest) > 130) or         # 长度加围长超限
            (shipping_weight > 50)                                       # 重量超限
        )

        if is_oversize:
            # 根据重量细分超大件类别
            if shipping_weight > 150:
                return "超大件(>150磅)"
            elif shipping_weight > 70 and shipping_weight <= 150:
                return "超大件((70,150]磅)"
            elif shipping_weight > 50 and shipping_weight <= 70: 
                return "超大件((50,70]磅)"
            else:
                return "超大件((0,50]磅)"
    
    #     # 先判断是否为超大件(>150磅)
    #     if shipping_weight > 150:
    #         return "超大件(>150磅)"
        
    #    # 检查是否为特大号商品（超大件的一种特殊情况）
    #     if longest > 96 or (longest + 2 * (second_longest + shortest)) > 130 :
    #         if shipping_weight <= 50:
    #             return "超大件((0,50]磅)"
    #         elif shipping_weight <= 70 and shipping_weight > 50:
    #             return "超大件((50,70]磅)"
    #         elif shipping_weight <= 150 and shipping_weight > 70:
    #             return "超大件((70,150]磅)"

        # 不是超大件，判断其他尺寸
        if longest <= 15 and second_longest <= 12 and shortest <= 0.75 and shipping_weight <= 1:
            return "小号标准尺寸"
        elif longest <= 18 and second_longest <= 14 and shortest <= 8 and shipping_weight <= 20:
            return "大号标准尺寸"
        elif longest <= 37 and second_longest <= 28 and shortest <= 20 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
            return "小号大件"
        elif longest <= 59 and second_longest <= 33 and shortest <= 33 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
            return "大号大件"
        
        # 如果以上都不满足，默认为最小重量段的超大件
        return "超大件((0,50]磅)"
        
        # # 根据尺寸和重量确定分类
        # if longest <= 15 and second_longest <= 12 and shortest <= 0.75 and shipping_weight <= 1:
        #     return "小号标准尺寸"
        # elif longest <= 18 and second_longest <= 14 and shortest <= 8 and shipping_weight <= 20:
        #     return "大号标准尺寸"
        # elif longest <= 37 and second_longest <= 28 and shortest <= 20 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
        #     return "小号大件"
        # elif longest <= 59 and second_longest <= 33 and shortest <= 33 and shipping_weight <= 50 and (longest + 2 * (second_longest + shortest)) <= 130:
        #     return "大号大件"
        # elif shipping_weight <= 50 or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((0,50]磅)"
        # elif (shipping_weight <= 70 and shipping_weight > 50) or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((50,70]磅)"
        # elif (shipping_weight <= 150 and shipping_weight > 70) or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件((70,150]磅)"
        # elif shipping_weight > 150 or (longest > 59 and second_longest > 33 and shortest > 33) or (longest + 2 * (second_longest + shortest)) > 130:
        #     return "超大件(>150磅)"
    
    def determine_shipping_weight(self, product_weight: float, volume_weight: float, 
                                size_category: str, year: int) -> float:
        """确定发货重量"""
        if year == 2024:
            # 2024年规则
            if size_category in ["小号标准尺寸", "特殊大件", "超大件(>150磅)"]:
                shipping_weight = product_weight
            else:
                shipping_weight = max(product_weight, volume_weight)
        elif year == 2026:
            # 2026年规则
            if size_category in ["小号标准尺寸", "超大件(>150磅)"]:
                shipping_weight = product_weight
            else:
                shipping_weight = max(product_weight, volume_weight)
        return shipping_weight


    def calculate_fee_from_table(self, size_category: str, shipping_weight: float, 
                       price: float, period: str, product_weight: float, volume_weight: float) -> float:
        """
        根据费用表计算指定时期的FBA费用
        
        Args:
            size_category (str): 商品尺寸分类
            shipping_weight (float): 发货重量(磅)
            price (float): 商品价格($)
            period (str): 时期
            product_weight (float): 商品重量(磅)
            volume_weight (float): 体积重量(磅)
            
        Returns:
            float: FBA费用($)
        """
        try:
            # 1. 确定价格区间
            if price < 10:
                price_range = "<10"
            elif 10 <= price <= 50:
                price_range = "[10,50]"
            else:
                price_range = ">50"
                
            # 2. 在费用表中查找匹配记录
            mask = (
                (self.fee_table['时期'] == period) &
                (self.fee_table['商品价格'] == price_range) &
                (self.fee_table['商品尺寸'] == size_category)
            )
            matching_rows = self.fee_table[mask]
            
            if len(matching_rows) == 0:
                print(f"未找到匹配记录: 时期={period}, 价格={price_range}, 尺寸={size_category}")
                return 0.0
                
            # 3. 首先尝试使用给定的发货重量
            fee = self._find_fee_by_weight(matching_rows, shipping_weight, size_category, price_range, period)
            if fee > 0:
                return fee
                
            # 4. 如果发货重量无法匹配，尝试使用商品重量
            if product_weight != shipping_weight:
                print(f"发货重量{shipping_weight}磅无法匹配，尝试使用商品重量{product_weight}磅")
                fee = self._find_fee_by_weight(matching_rows, product_weight, size_category, price_range, period)
                if fee > 0:
                    return fee
                    
            # 5. 如果商品重量也无法匹配，尝试使用体积重量
            if volume_weight != shipping_weight and volume_weight != product_weight:
                print(f"商品重量{product_weight}磅也无法匹配，尝试使用体积重量{volume_weight}磅")
                fee = self._find_fee_by_weight(matching_rows, volume_weight, size_category, price_range, period)
                if fee > 0:
                    return fee
                    
            # 6. 如果所有重量都无法匹配，返回0
            print(f"所有重量都无法匹配: 发货重量={shipping_weight}磅, 商品重量={product_weight}磅, 体积重量={volume_weight}磅")
            return 0.0
            
        except Exception as e:
            print(f"计算费用时出错: {e}")
            return 0.0

    def _find_fee_by_weight(self, matching_rows: pd.DataFrame, weight: float, 
                        size_category: str, price_range: str, period: str) -> float:
        """
        在匹配的行中根据重量查找费用
        
        Args:
            matching_rows (pd.DataFrame): 匹配的费用表行
            weight (float): 重量(磅)
            size_category (str): 商品尺寸分类
            price_range (str): 价格区间
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
                print(f"价格区间: {price_range}")
                print(f"时期: {period}")
                print(f"匹配到的费用规则: {fee}")
                
                # 清理费用字符串（去除$和逗号）
                fee_clean = fee.replace('$', '').replace(',', '')
                
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
        检查重量是否在指定范围内
        
        Args:
            weight (float): 发货重量(磅)
            weight_range (str): 重量范围字符串，如"(3,20]磅"
            
        Returns:
            bool: 是否在范围内
        """
        try:
            # 移除单位和空格
            clean_range = weight_range.replace('磅', '').strip()
            
            # 处理区间格式 (a,b]
            m = re.match(r'^\(?\s*([0-9\.]+)\s*,\s*([0-9\.]+)\s*\]$', clean_range)
            if m:
                low = float(m.group(1))
                high = float(m.group(2))
                return low < weight <= high

            # 处理带括号但不同格式的情况
            if '(' in clean_range and ']' in clean_range:
                nums = re.sub(r'[()\[\]]', '', clean_range).split(',')
                if len(nums) == 2:
                    low = float(nums[0])
                    high = float(nums[1])
                    return low < weight <= high
                
            # 处理 <=x 或 <x 或 >=x 或 >x
            if clean_range.startswith('<='):
                limit = float(clean_range[2:])
                return weight <= limit
            if clean_range.startswith('<'):
                limit = float(clean_range[1:])
                return weight < limit
            if clean_range.startswith('>='):
                limit = float(clean_range[2:])
                return weight >= limit
            if clean_range.startswith('>'):
                limit = float(clean_range[1:])
                return weight > limit
                
            return False
            
        except Exception as e:
            print(f"检查重量范围出错: {e}, 范围: {weight_range}")
            return False

    def calculate_removal_fee(self, size_category: str, shipping_weight: float) -> float:
        """
        计算移除费用
        
        Args:
            size_category (str): 商品尺寸分类
            shipping_weight (float): 发货重量(磅)
            
        Returns:
            float: 移除费用($)
        """
        try:
            # 判断是否为标准尺寸商品
            is_standard = size_category in ["小号标准尺寸", "大号标准尺寸"]
            
            if is_standard:
                # 标准尺寸商品的费用计算
                if 0 < shipping_weight <= 0.5:
                    return 0.84
                elif 0.5 < shipping_weight <= 1:
                    return 1.53
                elif 1 < shipping_weight <= 2:
                    return 2.27
                elif shipping_weight > 2:
                    return round(2.89 + (shipping_weight - 2) * 1.06, 2)
            else:
                # 大件商品的费用计算
                if 0 < shipping_weight <= 1:
                    return 3.12
                elif 1 < shipping_weight <= 2:
                    return 4.30
                elif 2 < shipping_weight <= 4:
                    return 6.36
                elif 4 < shipping_weight <= 10:
                    return 10.04
                elif shipping_weight > 10:
                    return round(14.32 + (shipping_weight - 10) * 1.06, 2)
            
            return 0.0  # 如果重量<=0，返回0
            
        except Exception as e:
            print(f"计算移除费用时出错: {e}")
            return 0.0


    def calculate_multichannel_fee(self, size_category: str, shipping_weight: float, 
                             shipping_type: str = "标准",
                             product_weight: Optional[float] = None,
                             volume_weight: Optional[float] = None) -> float:
        """
        计算多渠道配送费，支持重量回退
        
        Args:
            size_category (str): 商品尺寸分类
            shipping_weight (float): 发货重量(磅)
            shipping_type (str): 配送方式，"标准"或"加急"
            product_weight (float, optional): 商品实际重量，用于重量回退
            volume_weight (float, optional): 体积重量，用于重量回退
            
        Returns:
            float: 多渠道配送费($)
        """
        def try_calculate_with_weight(weight: float) -> Tuple[float, bool]:
            """使用指定重量尝试计算费用"""
            for _, row in matching_rows.iterrows():
                weight_range = str(row['发货重量'])
                fee = str(row['多渠道配送费'])
                
                # 检查重量是否在范围内
                if self._check_weight_in_range(weight, weight_range):
                    # 清理费用字符串
                    fee_clean = fee.replace('$', '').replace(',', '')
                    
                    # 如果是纯数字，直接返回
                    if fee_clean.replace('.', '').isdigit():
                        return float(fee_clean), True
                    
                    # 如果是公式，需要计算
                    try:
                        formula = fee_clean.replace('发货重量', str(weight))
                        result = eval(formula)
                        return round(float(result), 2), True
                    except Exception as e:
                        print(f"计算公式出错: {e}, 公式: {fee}")
                        return 0.0, False
            
            return 0.0, False

        try:
            # 1. 读取多渠道费用表
            multichannel_fee_path = self._resolve_path("多渠道逻辑一维表.csv")
            if not os.path.exists(multichannel_fee_path):
                print(f"未找到多渠道费用表: {multichannel_fee_path}")
                return 0.0
                
            try:
                multichannel_table = pd.read_csv(multichannel_fee_path, encoding='gbk')
            except:
                try:
                    multichannel_table = pd.read_csv(multichannel_fee_path, encoding='utf-8')
                except Exception as e:
                    print(f"读取多渠道费用表失败: {e}")
                    return 0.0
            
            # 2. 查找匹配记录
            mask = (
                (multichannel_table['配送方式'] == shipping_type) &
                (multichannel_table['商品尺寸'] == size_category)
            )
            matching_rows = multichannel_table[mask]
            
            if len(matching_rows) == 0:
                print(f"未找到匹配记录: 配送方式={shipping_type}, 尺寸={size_category}")
                return 0.0
            
            # 3. 尝试使用shipping_weight计算
            fee, success = try_calculate_with_weight(shipping_weight)
            if success:
                return fee
                
            print(f"\n首选发货重量 {shipping_weight}磅 匹配失败，尝试其他重量...")
            
            # 4. 如果shipping_weight匹配失败，尝试使用其他重量
            if product_weight is not None and product_weight != shipping_weight:
                print(f"尝试使用实际重量: {product_weight}磅")
                fee, success = try_calculate_with_weight(product_weight)
                if success:
                    return fee
                    
            if volume_weight is not None and volume_weight != shipping_weight:
                print(f"尝试使用体积重量: {volume_weight}磅")
                fee, success = try_calculate_with_weight(volume_weight)
                if success:
                    return fee
            
            print(f"所有重量值都无法匹配: shipping_weight={shipping_weight}, product_weight={product_weight}, volume_weight={volume_weight}")
            return 0.0
            
        except Exception as e:
            print(f"计算多渠道配送费时出错: {e}")
            return 0.0


    def process_product_dataframe(self, df: pd.DataFrame, periods: List[str] = ["2024Q1", "2024Q2", "2024Q3"]) -> pd.DataFrame:
        """
        处理包含多个产品信息的DataFrame，计算2024和2026年的尺寸分类及多个时期的FBA费用
        
        Args:
            df (pd.DataFrame): 包含产品信息的DataFrame
            periods (List[str]): 需要计算的时期列表，默认计算三个季度
            
        Returns:
            pd.DataFrame: 添加了两年尺寸分类和多时期FBA费用的DataFrame副本
        """
        # 创建DataFrame副本，避免修改原始数据
        result_df = df.copy()
        
        # 添加新列用于存储计算结果
        result_df['size_category_2024'] = ''
        result_df['shipping_weight_2024'] = 0.0
        result_df['size_category_2026'] = ''
        result_df['shipping_weight_2026'] = 0.0
        result_df['removal_fee_2026'] = 0.0
        result_df['multichannel_fee_standard'] = 0.0
        result_df['multichannel_fee_express'] = 0.0
        
        # 为每个时期添加FBA费用列
        for period in periods:
            result_df[f'fba_fee_{period}_2024'] = 0.0
            result_df[f'fba_fee_{period}_2026'] = 0.0
        
        # 遍历每行数据进行处理
        for idx, row in result_df.iterrows():
            try:
                # 1. 单位转换 - 尺寸
                length = float(row['longest-side'])
                width = float(row['median-side'])
                height = float(row['shortest-side'])
                
                if str(row['unit-of-dimension']).lower() == 'centimeters':
                    length = self.convert_units(length, 'centimeters', 'inches')
                    width = self.convert_units(width, 'centimeters', 'inches')
                    height = self.convert_units(height, 'centimeters', 'inches')
                
                # 2. 单位转换 - 重量
                weight = float(row['item-package-weight'])
                if str(row['unit-of-weight']).lower() in ['grams', 'g']:
                    weight = self.convert_units(weight, 'grams', 'pounds')
                elif str(row['unit-of-weight']).lower() in ['kilograms', 'kg']:
                    weight = self.convert_units(weight * 1000, 'grams', 'pounds')
                
                # 3. 计算体积重量
                volume_weight = self.calculate_volume_weight(length, width, height)
                
                # 4. 计算2024年的尺寸分类和发货重量
                size_category_2024 = self.determine_size_category_2024(length, width, height, weight)
                shipping_weight_2024 = self.determine_shipping_weight(weight, volume_weight, size_category_2024, 2024)
                
                # 5. 计算2026年的尺寸分类和发货重量
                size_category_2026 = self.determine_size_category_2026(length, width, height, weight)
                shipping_weight_2026 = self.determine_shipping_weight(weight, volume_weight, size_category_2026, 2026)
                
                # 6. 保存尺寸分类和发货重量
                result_df.at[idx, 'size_category_2024'] = size_category_2024
                result_df.at[idx, 'shipping_weight_2024'] = round(shipping_weight_2024, 3)
                result_df.at[idx, 'size_category_2026'] = size_category_2026
                result_df.at[idx, 'shipping_weight_2026'] = round(shipping_weight_2026, 3)
                # 6.1 计算移除费用
                removal_fee_2026 = self.calculate_removal_fee(size_category_2026, shipping_weight_2026)
                result_df.at[idx, 'removal_fee_2026'] = round(removal_fee_2026, 2)
                # 6.2 计算多渠道配送费 (使用2026年的尺寸分类和发货重量)
                multichannel_fee_standard = self.calculate_multichannel_fee(
                    size_category_2026, 
                    shipping_weight_2026,
                    "标准",
                    product_weight=weight,      # 添加实际重量
                    volume_weight=volume_weight # 添加体积重量
                )
                multichannel_fee_express = self.calculate_multichannel_fee(
                    size_category_2026, 
                    shipping_weight_2026,
                    "加急",
                    product_weight=weight,      # 添加实际重量
                    volume_weight=volume_weight # 添加体积重量
                )
                result_df.at[idx, 'multichannel_fee_standard'] = round(multichannel_fee_standard, 2)
                result_df.at[idx, 'multichannel_fee_express'] = round(multichannel_fee_express, 2)
                
                # 7. 计算每个时期的FBA费用（2024和2026年规则）
                price = float(row['sales-price']) if 'sales-price' in row else 0.0
                for period in periods:
                    # 2024年规则的费用
                    fba_fee_2024 = self.calculate_fee_from_table(
                        size_category_2024, shipping_weight_2024, price, period, weight, volume_weight
                    )
                    result_df.at[idx, f'fba_fee_{period}_2024'] = round(fba_fee_2024, 2)
                    
                    # 2026年规则的费用
                    fba_fee_2026 = self.calculate_fee_from_table(
                        size_category_2026, shipping_weight_2026, price, period, weight, volume_weight
                    )
                    result_df.at[idx, f'fba_fee_{period}_2026'] = round(fba_fee_2026, 2)
                
            except Exception as e:
                print(f"处理FNSKU {row.get('fnsku', '未知')} 时出错: {e}")
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
                'sales-price',
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
            
            # 显示2024和2026年尺寸分类统计
            print("\n2024年尺寸分类统计:")
            print(result_df['size_category_2024'].value_counts())
            
            print("\n2026年尺寸分类统计:")
            print(result_df['size_category_2026'].value_counts())
            
            # 显示各时期FBA费用平均值
            print("\nFBA费用平均值统计:")
            for period in periods:
                print(f"\n{period}时期:")
                print(f"2024年规则: ${result_df[f'fba_fee_{period}_2024'].mean():.2f}")
                print(f"2026年规则: ${result_df[f'fba_fee_{period}_2026'].mean():.2f}")
            
            return result_df
            
        except Exception as e:
            print(f"处理文件出错: {e}")
            return pd.DataFrame()


   
def main():
    """主函数 - 示例用法"""
    calculator_us = FBAFeeCalculator_us()

if __name__ == "__main__":
    main()