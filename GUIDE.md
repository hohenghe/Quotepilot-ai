# QuotePilot AI 使用指南

AI 驱动的国际贸易销售助手，帮助外贸团队分析客户询盘、匹配产品、生成报价邮件。

---

## 快速启动

```powershell
cd "F:\QuotePilot AI\frontend"
npm run dev
```

浏览器打开 `http://localhost:3000`，无需后端或数据库，数据自动保存在浏览器中。

> 可选：如需启动完整后端和 PostgreSQL 数据库，运行 `docker-compose up -d` 后再启动 `backend/` 服务。

---

## 功能概览

| 页面 | 路由 | 功能 |
|---|---|---|
| 仪表盘 | `/` | 产品数量、询盘、报价统计数据 |
| 产品目录 | `/products` | 上传产品文件，管理产品库 |
| 询盘分析 | `/inquiry` | 粘贴客户询盘，AI 提取信息并匹配产品 |
| 报价生成 | `/quote` | 查看历史询盘，生成专业报价邮件 |

---

## 语言切换

侧边栏底部有语言切换器，支持 5 种语言：
- English（英文）
- 简体中文
- 繁體中文
- Español（西班牙语）
- Français（法语）

选择后自动保存，刷新不丢失。

---

## CSV 文件上传指南

### 上传步骤

1. 进入 **产品目录** 页面（`/products`）
2. 点击右上角 **上传文件** 按钮
3. 选择 CSV 文件（也支持 PDF / Excel / Word）
4. 系统自动解析并导入产品

### CSV 格式要求

- 编码：**UTF-8**
- 第一行为表头，从第二行开始每行一个产品
- 用逗号分隔，字段中如含逗号请用双引号包裹
- 无需包含价格列（价格字段可选）

### 表头列说明

| 列名 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `name` | 是 | 产品名称 | LED Panel Light 60x60cm |
| `sku` | 否 | SKU 编号 | LED-PL6060-EU |
| `category` | 否 | 产品分类（英文，下划线分隔） | led_lighting |
| `description` | 否 | 产品描述，含性能参数和适用场景 | Die-cast aluminum housing, IP66 waterproof. 100W, 10000lm, 6500K. Suitable for building facades. |
| `technical_specs` | 否 | 技术参数（逗号分隔的键值对） | Power: 40W, Voltage: 220-240V, CRI>80 |
| `certifications` | 否 | 产品认证（逗号分隔） | CE, RoHS, EMC |
| `moq` | 否 | 最小起订量（纯数字） | 100 |
| `pricing` | 否 | 价格信息（自由文本，可包含成本价、零售价、阶梯批发价等） | Cost: $8.50, Retail: $15.00, Wholesale 100+: $10.00, Wholesale 500+: $7.50 |
| `lead_time_days` | 否 | 交货期天数（纯数字） | 25 |

> 列名不区分大小写，`_` `-` 和空格均可识别。

### CSV 示例

```csv
name,sku,category,description,technical_specs,certifications,moq,pricing,lead_time_days
LED Panel Light 60x60cm,LED-PL6060-EU,led_lighting,"High-quality LED panel light 40W 600x600mm. Energy efficient with long lifespan suitable for office and commercial spaces.","Power: 40W, Voltage: 220-240V, Luminous Flux: 4000lm, CRI>80, Size: 595x595mm","CE, RoHS, EMC",100,"Cost: $8.50, Retail: $15.00, Wholesale 100+: $12.00, Wholesale 500+: $10.50",25
LED High Bay Light 150W,LED-HB150-EU,led_lighting,"Industrial grade LED high bay light 150W IP65 waterproof. Ideal for warehouses and factories.","Power: 150W, Voltage: 85-265V, Luminous Flux: 18000lm, Color Temperature: 5000K, IP65","CE, RoHS, IP65",50,"Cost: $32.00, Retail: $52.00, Wholesale 50+: $45.00, Wholesale 200+: $38.00",30
LED Strip Light 5050 RGB,LED-ST5050-RGB,led_lighting,"Flexible LED strip light 5050 SMD RGB 60LEDs/m with remote control. Perfect for decorative lighting.","LED Type: 5050 SMD, 60 LEDs/m, Voltage: DC12V, Power: 14.4W/m, RGB, Length: 5m/roll","CE, RoHS",200,"Cost: $2.50, Retail: $4.50, Wholesale 500+: $3.50, Wholesale 1000+: $2.80",15
LED Flood Light 100W,LED-FL100-EU,led_lighting,"Outdoor LED floodlight 100W IP66 waterproof die-cast aluminum housing. Suitable for building facades and parking lots.","Power: 100W, Voltage: 220-240V, Luminous Flux: 10000lm, Color Temperature: 6500K, IP66","CE, RoHS, IP66, TUV",50,"Cost: $19.00, Retail: $32.00, Wholesale 50+: $28.00, Wholesale 100+: $24.00",20
LED Tube Light T8 120cm,LED-T8-120-EU,led_lighting,"T8 LED tube light 18W 120cm direct replacement for fluorescent tubes. Flicker-free driver.","Power: 18W, Voltage: 220-240V, Luminous Flux: 1800lm, Color Temperature: 4000K/6500K, Length: 1200mm","CE, RoHS, EMC",500,"Cost: $1.20, Retail: $3.00, Wholesale 1000+: $2.20, Wholesale 5000+: $1.80",15
```

---

## 询盘分析使用流程

1. 进入 **询盘分析** 页面（`/inquiry`）
2. 粘贴客户的询盘内容（英文），或点击 **加载示例** 体验
3. 点击 **分析询盘**，AI 自动提取：
   - 产品类别、数量、目标价格
   - 技术参数、认证要求
   - 交货地点
   - 待确认的缺失信息
4. 系统自动匹配产品目录中最合适的产品，显示匹配度
5. 点击 **生成报价邮件** 产出专业报价邮件
6. 点击 **复制** 将邮件内容复制到剪贴板

---

## 生成 CSV 的 AI 提示词

如需让其他 AI 生成产品 CSV 文件，使用以下提示词：

```
为 QuotePilot AI 外贸销售助手生成产品 CSV 文件。

CSV 文件要求：
- 第一行为表头，从第二行开始每行一个产品
- 用逗号分隔，字段中如含逗号请用双引号包裹
- 编码 UTF-8
- 价格浓缩在一列中，description 中不要包含价格信息

表头列（带*为必填）：

| 列名 | 说明 | 示例 |
|---|---|---|
| name* | 产品名称 | LED Panel Light 60x60cm |
| sku | SKU 编号 | LED-PL6060-EU |
| category | 产品分类（英文，下划线分隔） | led_lighting / electronics |
| description* | 产品描述，需包含性能参数（材质、功率、尺寸、适用场景等，2-4 句话）。不要包含价格 | Die-cast aluminum housing, IP66 waterproof. 100W, 10000lm. Suitable for building facades. |
| technical_specs | 技术参数（逗号分隔的键值对） | Power: 40W, Voltage: 220-240V, CRI>80 |
| certifications | 产品认证（逗号分隔） | CE, RoHS, EMC |
| moq | 最小起订量（纯数字） | 100 |
| pricing | 价格信息（自由文本，可包含成本价、零售价、不同数量的批发价等，数据需真实随机） | Cost: $8.50, Retail: $15.00, Wholesale 100+: $12.00, Wholesale 500+: $10.50 |
| lead_time_days | 交货期天数（纯数字） | 25 |

注意：
- 列名不区分大小写
- description 必须包含具体性能数据和适用场景，但不要在 description 中写价格
- 所有价格信息统一放在 pricing 列中，以自由文本形式呈现
- pricing 列需包含真实随机的价格数据，至少包含 2 种价格类型（如成本价+零售价，或不同阶梯批发价）

请生成 10 个产品的 CSV 文件，输出完整的 CSV 内容。
```
