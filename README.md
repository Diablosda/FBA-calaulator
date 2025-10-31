# FBA费用计算器

这是一个根据Excel文件中的实际数据计算Amazon FBA配送费用的Python工具，支持美国和欧洲市场的不同尺寸分类规则。

## 文件说明

- `fba_fee_calculator_us.py` - 美国市场FBA费用计算器
- `fba_fee_calculator_eu.py` - 欧洲市场FBA费用计算器
- `fba_calculator_example.ipynb` - Jupyter notebook使用示例
- `逻辑.xlsx` - 包含美国尺寸分段数据的Excel文件
- `逻辑一维表.csv` - 包含美国费用表数据的CSV文件
- `欧洲逻辑.xlsx` - 包含欧洲尺寸分段数据的Excel文件
- `英德逻辑一维表.csv` - 包含英国和德国费用表数据的CSV文件

## 功能特性

- ✅ 支持从Excel文件直接读取数据
- ✅ 从Excel文件读取尺寸分段数据
- ✅ 从CSV文件读取费用表数据
- ✅ 自动加载Excel数据到计算器中
- ✅ 支持根据实际Excel数据结构进行费用计算
- ✅ 支持多种单位转换（英寸/厘米，磅/克/千克）
- ✅ 自动计算体积重量
- ✅ 根据不同年份规则进行商品尺寸分类
- ✅ 计算多个时间段的配送费用
- ✅ 支持单个商品和批量计算
- ✅ 支持DataFrame批量处理
- ✅ 支持美国和欧洲市场不同规则

## 使用方法

### 1. 在Jupyter Notebook中使用

```python
# 导入计算器
from fba_fee_calculator_us import FBAFeeCalculator_us
from fba_fee_calculator_eu import FBAFeeCalculator_eu

# 创建计算器实例（会自动加载Excel数据）
calculator_us = FBAFeeCalculator_us(
    excel_path='逻辑.xlsx', 
    fee_table_path='逻辑一维表.csv'
)

calculator_eu = FBAFeeCalculator_eu(
    excel_path='欧洲逻辑.xlsx', 
    fee_table_path='英德逻辑一维表.csv'
)
```

### 2. 批量处理DataFrame数据

```python
# 定义要计算的时期
periods = [
    "2025年01月15日至2025年10月14日",
    "2025年10月15日至2026年01月14日",
    "自2026年01月15日起"
]

# 处理美国产品数据文件
result_df_us = calculator_us.process_file(
    file_path='products_us.xlsx',
    periods=periods
)

# 处理欧洲产品数据文件
result_df_eu = calculator_eu.process_file(
    file_path='products_eu.xlsx',
    periods=periods
)

print("处理结果:")
print(result_df_us)
```

### 3. 输入数据格式要求

DataFrame需要包含以下列：

美国市场:

| 列名 | 说明 | 示例 |
|------|------|------|
| `fnsku` | 商品编码 | FNSKU001 |
| `sales-price` | 商品价格 | 25.0 |
| `longest-side` | 最长边 | 10 |
| `median-side` | 次长边 | 8 |
| `shortest-side` | 最短边 | 2 |
| `unit-of-dimension` | 长度单位 | inches/centimeters |
| `item-package-weight` | 商品重量 | 1.5 |
| `unit-of-weight` | 重量单位 | pounds/grams/kilograms |

欧洲市场:

| 列名 | 说明 | 示例 |
|------|------|------|
| `fnsku` | 商品编码 | FNSKU001 |
| `amazon-store` | Amazon店铺国家 | GB/DE |
| `sales-price` | 商品价格 | 25.0 |
| `longest-side` | 最长边 | 10 |
| `median-side` | 次长边 | 8 |
| `shortest-side` | 最短边 | 2 |
| `unit-of-dimension` | 长度单位 | centimeters |
| `item-package-weight` | 商品重量 | 1500 |
| `unit-of-weight` | 重量单位 | grams |

## 输出结果说明

### 美国市场输出列:

| 列名 | 说明 |
|------|------|
| `size_category_2024` | 2024年规则尺寸分类 |
| `shipping_weight_2024` | 2024年规则发货重量(磅) |
| `size_category_2026` | 2026年规则尺寸分类 |
| `shipping_weight_2026` | 2026年规则发货重量(磅) |
| `removal_fee_2026` | 2026年移除费用($) |
| `multichannel_fee_standard` | 标准多渠道配送费($) |
| `multichannel_fee_express` | 加急多渠道配送费($) |
| `fba_fee_{period}_2024` | 指定时期2024年规则FBA费用($) |
| `fba_fee_{period}_2026` | 指定时期2026年规则FBA费用($) |

### 欧洲市场输出列:

| 列名 | 说明 |
|------|------|
| `european_size_category` | 欧洲尺寸分类 |
| `european_shipping_weight_g` | 欧洲发货重量(克) |
| `european_country` | 国家(英国/德国) |
| `fba_fee_{period}` | 指定时期FBA费用(£或€) |

## 核心功能

### 1. 自动数据加载
- 计算器初始化时自动加载Excel数据
- 支持显示加载的数据内容
- 如果Excel文件加载失败，会使用默认规则

### 2. 单位转换
美国市场:
- 长度：英寸 ↔ 厘米
- 重量：磅 ↔ 克 ↔ 千克

欧洲市场:
- 长度：厘米
- 重量：克

### 3. 体积重量计算
美国: 体积重量 = (长 × 宽 × 高) ÷ 139 (单位: 英寸, 磅)
欧洲: 体积重量 = (长 × 宽 × 高) ÷ 5000 × 1000 (单位: 厘米, 克)

### 4. 尺寸分类规则

美国市场:
- 2024年规则: 小号标准尺寸、大号标准尺寸、大号大件、超大件(不同重量段)
- 2026年规则: 小号标准尺寸、大号标准尺寸、小号大件、大号大件、超大件(不同重量段)

欧洲市场:
- 信封类: 轻型信封、标准信封、大号信封、超大号信封
- 包裹类: 小包裹、标准包裹
- 大件类: 小号大件、轻型标准大件、重型标准大件、大号标准大件、特大号大件、超重型大件、特殊大件

### 5. 发货重量选择规则

美国市场:
- 2024年规则：小号标准尺寸、特殊大件、超大件(>150磅)使用商品重量，其他使用商品重量和体积重量中的较大值
- 2026年规则：小号标准尺寸、超大件(>150磅)使用商品重量，其他使用商品重量和体积重量中的较大值

欧洲市场:
- 信封类和特殊大件使用商品重量，其他使用商品重量和体积重量中的较大值

### 6. 费用计算
支持计算多个时期的配送费用，根据商品尺寸分类、发货重量和商品价格在费用表中查找对应费用。

## 注意事项

1. **Excel文件路径**：确保Excel和CSV文件在正确的位置
2. **数据格式**：文件必须包含指定的列
3. **费率更新**：如果费用表结构发生变化，需要相应更新计算器代码
4. **单位转换**：输入数据会自动转换为系统所需单位进行计算

## 故障排除

如果遇到Excel文件加载问题：

1. 检查文件路径是否正确
2. 确认Excel文件包含必需的sheet
3. 检查文件是否被其他程序占用
4. 如果加载失败，计算器会使用空表继续工作

## 下一步开发

1. 添加更多的尺寸分类规则
2. 支持更多的单位转换
3. 添加数据验证和错误处理
4. 支持其他货币形式
