# Trip Helper 项目阅读与分析报告

> 仓库：<https://github.com/theonlyrnh/trip-helper>  
> 本地路径：`D:/trip-helper`  
> 当前阅读提交：`63fd8fd v0.3.1: 修复机票分类+保险显示+去重`

## 1. 项目定位

Trip Helper 是一个**本地运行的差旅发票智能整理助手**。

它的核心目标是：让用户选择一个包含差旅发票、订单截图、报销凭证的文件夹，系统自动扫描文件、识别文字、分类票据、解析结构化字段、生成出差路线和费用汇总，并提示可能需要人工复核的问题，最后支持导出 Excel / PDF 报销材料。

项目更偏向个人或小团队本地使用，而不是多租户 SaaS 服务。

## 2. 技术栈

### 2.1 后端

后端位于 `backend/`，入口为 `backend/main.py`。

主要技术：

- FastAPI：提供 HTTP API；
- SQLAlchemy：数据库 ORM；
- SQLite：本地数据库；
- PyMuPDF：PDF 原生文本提取、PDF 页面渲染；
- Pillow：图片缩略图生成；
- requests：调用 OCR / 视觉模型接口；
- openpyxl：导出 Excel；
- reportlab：导出 PDF。

后端默认地址：

```text
http://127.0.0.1:8000
```

Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

### 2.2 前端

前端位于 `frontend/`。

主要技术：

- React；
- Vite；
- TypeScript；
- React Router。

主要页面：

- `/workspace`：核心工作台；
- `/trips`：项目列表；
- `/dashboard`：年度统计；
- `/settings`：系统设置。

前端 API 地址目前硬编码为：

```ts
http://127.0.0.1:8000
```

## 3. 项目目录结构概览

```text
trip-helper/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 环境变量配置
│   ├── database.py          # SQLAlchemy / SQLite 初始化
│   ├── enums.py             # 枚举定义
│   ├── models/              # 数据模型
│   ├── routers/             # API 路由
│   ├── services/            # 核心业务逻辑
│   ├── parsers/             # 票据解析器
│   ├── providers/           # OCR 提供方
│   ├── exporters/           # Excel / PDF 导出
│   └── utils/               # 工具函数
├── frontend/
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 通用组件
│   │   ├── api/             # 前端 API 封装
│   │   └── utils/           # 标签、格式化工具
│   └── package.json
├── scripts/                 # 辅助脚本
├── README.md
├── start.bat                # Windows 一键启动
└── .env.example             # 环境变量示例
```

## 4. 核心业务流程

前端工作台 `frontend/src/pages/TripWorkspace.tsx` 中的“一键分析”流程是项目主流程：

```text
选择文件夹 / 创建项目
  ↓
扫描文件
  ↓
预处理 PDF / 图片
  ↓
OCR 识别
  ↓
分类与结构化解析
  ↓
构建出行路线、住宿记录
  ↓
推断出差日期、计算费用
  ↓
检测异常
  ↓
展示工作台 / 年度统计 / 导出报表
```

对应 API：

```text
POST /api/trips/{trip_id}/documents/scan
POST /api/trips/{trip_id}/documents/preprocess
POST /api/trips/{trip_id}/recognize
POST /api/trips/{trip_id}/analyze
GET  /api/trips/{trip_id}/workspace
```

## 5. 后端模块说明

### 5.1 FastAPI 入口

文件：`backend/main.py`

职责：

- 创建 FastAPI 应用；
- 配置 CORS；
- 注册各类 API 路由；
- 启动时初始化数据库表。

已注册路由包括：

- health；
- settings；
- trips；
- documents；
- analysis；
- exports；
- system；
- dashboard。

### 5.2 配置与数据库

文件：

- `backend/config.py`
- `backend/database.py`

默认数据库路径：

```text
data/app.db
```

默认导出路径：

```text
data/exports
```

默认 OCR 配置：

```text
PADDLEOCR_API_URL=http://localhost:8118/v1
PADDLEOCR_MODEL=PaddleOCR-VL-1.5-0.9B
```

### 5.3 数据模型

主要模型：

| 模型 | 表名 | 作用 |
|---|---|---|
| `Trip` | `trips` | 一个出差项目或报销项目 |
| `Document` | `documents` | 扫描到的 PDF / 图片文件 |
| `OCRResult` | `ocr_results` | OCR 原始识别结果 |
| `Invoice` | `invoices` | 结构化票据信息 |
| `TravelSegment` | `travel_segments` | 交通行程片段 |
| `LodgingStay` | `lodging_stays` | 住宿记录 |
| `ReviewIssue` | `review_issues` | 异常与复核问题 |
| `AppSetting` | `app_settings` | 系统设置 |
| `Job` | `jobs` | 后台任务记录，当前核心流程中使用较少 |

### 5.4 项目管理

文件：

- `backend/routers/trips.py`
- `backend/services/trip_service.py`

功能：

- 创建项目；
- 查询项目列表；
- 查询最近项目；
- 按文件夹路径查找已有项目；
- 更新项目标题、文件夹、状态、报销状态；
- 删除项目。

创建项目时会尝试从文件夹名称中解析日期，例如：

```text
20260122-20260201
2026-01-22至2026-02-01
2026.01.22-2026.02.01
```

解析结果会写入：

- `folder_date_start`
- `folder_date_end`
- `confirmed_start_date`
- `confirmed_end_date`
- `trip_days`

### 5.5 文件扫描与预处理

文件：

- `backend/services/folder_scanner.py`
- `backend/services/document_service.py`

支持文件类型：

```text
.pdf
.png
.jpg
.jpeg
```

扫描逻辑：

- 递归扫描指定文件夹；
- 计算文件 hash；
- 同一个项目内根据 hash 去重；
- 创建 `Document` 记录。

预处理逻辑：

- PDF：
  - 使用 PyMuPDF 提取原生文本；
  - 渲染第一页为图片；
  - 生成缩略图；
  - 如果原生文本足够长，则标记为 `TEXT_EXTRACTED`。
- 图片：
  - 生成缩略图；
  - 标记为 `PREPROCESSED`。

### 5.6 OCR 识别

文件：

- `backend/services/ocr_service.py`
- `backend/providers/paddleocr_vl_provider.py`
- `backend/providers/qwen3_vl_provider.py`

识别策略是三级：

1. **PyMuPDF**  
   对电子 PDF 直接提取文本。

2. **本地 PaddleOCR-VL**  
   默认调用 `http://localhost:8118/v1/chat/completions`。

3. **远程 Qwen3-VL 兜底**  
   如果配置了远程 API Key，则在本地 OCR 失败时调用远程视觉模型。

识别结果保存到 `ocr_results` 表。

### 5.7 分类与结构化解析

文件：

- `backend/services/classification_service.py`
- `backend/services/extraction_service.py`
- `backend/parsers/`

分类主要是规则驱动，基于关键词和正则表达式。

支持识别和归类的类型包括：

- 高铁 / 火车票；
- 机票；
- 机票订单截图；
- 酒店发票；
- 酒店订单截图；
- 出行保险发票；
- 退票 / 改签费；
- 出租车 / 网约车；
- 餐饮发票；
- 增值税发票；
- 快递物流；
- 办公用品；
- 电子数码；
- 软件服务；
- 通信费；
- 普通日常发票。

解析后生成 `Invoice` 记录。

### 5.8 高铁票坐标级解析

文件：`backend/parsers/train_ticket_coord_parser.py`

这是项目中比较有针对性的逻辑。

其特点：

- 使用 PyMuPDF 的 `page.get_text("words")` 获取文字坐标；
- 根据坐标区分出发站、到达站；
- 区分开票日期和乘车日期；
- 区分票价和退票 / 改签费；
- 避免将起终点反转。

这一部分明显是为了解决普通 OCR 文本顺序混乱导致的高铁票解析错误。

### 5.9 出行路线、住宿记录和日期推断

文件：

- `backend/services/travel_builder.py`
- `backend/services/lodging_builder.py`
- `backend/services/trip_inference.py`

交通票据生成：

```text
TravelSegment
```

酒店发票生成：

```text
LodgingStay
```

出差日期推断优先级：

1. 城际交通日期；
2. 住宿入住 / 离店日期；
3. 文件夹名称中的日期；
4. 发票业务日期；
5. 发票开票日期。

路线文本由交通片段生成，例如：

```text
南京 → 北京 → 太原
```

### 5.10 费用汇总

文件：`backend/services/expense_summary.py`

费用会按类别汇总：

- 城际交通；
- 市内交通；
- 住宿；
- 餐饮；
- 退票 / 改签费；
- 出行保险；
- 其他。

金额优先级：

```text
confirmed_amount > total_amount > 0
```

差旅补助计算：

```text
allowance_amount = trip_days * daily_allowance
```

默认日补助：

```text
180.00
```

如果项目类型是 `DAILY`，则不计算差旅补助。

### 5.11 异常检测

文件：`backend/services/issue_detector.py`

当前已检测的问题包括：

- 识别置信度低；
- 缺少金额；
- 金额异常，例如疑似把发票代码识别成金额；
- 购买方名称与配置公司不一致；
- 日期超出出差范围；
- 交通票据缺少出行日期；
- 无法推断出差日期；
- 住宿晚数不足；
- 住宿晚数超过出差晚数；
- 平台代开发票是否缺少订单截图佐证。

异常保存到 `review_issues` 表，并在工作台中展示。

### 5.12 导出

文件：

- `backend/exporters/excel_exporter.py`
- `backend/exporters/pdf_report_exporter.py`
- `backend/routers/exports.py`

支持导出：

- Excel；
- PDF。

Excel 包含 5 个 sheet：

1. Trip Summary；
2. Invoice Details；
3. Travel Segments；
4. Lodging Details；
5. Review Issues。

## 6. 前端功能说明

### 6.1 工作台

文件：`frontend/src/pages/TripWorkspace.tsx`

这是项目核心页面。

主要能力：

- 选择或切换项目；
- 选择本地文件夹；
- 创建项目；
- 一键分析；
- 分步执行扫描、预处理、OCR、分析；
- 展示项目状态；
- 展示文件数、识别数、异常数、金额合计；
- 展示费用概览；
- 展示路线时间线；
- 展示文件列表；
- 按类型筛选文件；
- 查看异常；
- 查看单个文件详情；
- 修改项目类型；
- 修改报销状态。

### 6.2 项目列表

文件：`frontend/src/pages/Trips.tsx`

功能：

- 展示所有项目；
- 按报销状态过滤；
- 点击项目进入工作台。

### 6.3 年度统计

文件：`frontend/src/pages/DashboardPage.tsx`

统计内容：

- 年度项目数；
- 出差总天数；
- 票据总金额；
- 补助总额；
- 含补助总计；
- 已报销金额；
- 未报销金额；
- 月度趋势；
- 费用分类；
- 城市排行；
- 最近项目。

### 6.4 设置页

文件：`frontend/src/pages/Settings.tsx`

可配置：

- 默认公司名称；
- 税号；
- 默认出差人；
- 默认发票根目录；
- 日补助；
- 住宿限额；
- 是否要求返程票；
- 是否要求住宿发票；
- OCR Provider 配置。

## 7. 启动方式

安装后端依赖：

```bash
pip install -r backend/requirements.txt
```

安装前端依赖：

```bash
cd frontend
npm install
```

启动后端：

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

启动前端：

```bash
cd frontend
npm run dev
```

Windows 下也可以使用：

```text
start.bat
```

但需要注意 `start.bat` 中 Python 路径是硬编码的：

```bat
D:\ProgramData\anaconda3\envs\fapiao\python.exe
```

不同机器上可能需要修改。

## 8. 项目优点

1. **业务目标清晰**  
   围绕“差旅发票整理、识别、汇总、导出”展开，场景明确。

2. **完整链路已打通**  
   从文件夹扫描、OCR、分类解析、费用汇总、异常检测，到前端展示和导出，已经形成闭环。

3. **对高铁票做了针对性优化**  
   坐标级解析能解决普通 OCR 文本顺序混乱的问题，对实际发票处理很有价值。

4. **支持正式发票和辅助凭证区分**  
   代码中通过 `document_role`、`include_in_summary` 区分正式发票、订单截图、辅助凭证，避免订单截图重复计入汇总。

5. **本地优先设计**  
   SQLite、本地文件夹、tkinter 选择目录、本地 OCR 服务，都符合个人本地工具定位。

6. **前端工作台信息比较集中**  
   工作台同时展示项目、费用、路线、文件、异常，适合人工复核。

## 9. 不足与建议

### 9.1 配置来源不统一

**问题：**  
设置页会把 OCR 配置保存到数据库 `app_settings`，但 `OCRService` 实际读取的是 `.env` 中的 `config.settings`。

这会导致用户在前端设置页修改 OCR 地址、远程 API Key 后，实际识别逻辑可能仍然使用旧的环境变量。

**建议：**

- 明确配置优先级：数据库设置优先，环境变量作为默认值；
- `OCRService` 初始化时从 `SettingsService` 或统一配置服务读取最新配置；
- 前端设置页保存后提示是否需要重启服务，或者后端支持运行时生效。

### 9.2 OCR / 分析流程是同步请求

**问题：**  
虽然项目中有 `Job` 模型，但当前“一键分析”本质上是前端依次发起同步 HTTP 请求。文件数量较多、OCR 服务较慢或远程模型响应慢时，前端等待时间会很长，体验不稳定。

**建议：**

- 将扫描、预处理、OCR、分析改造成后台任务；
- 使用 `jobs` 表记录任务进度；
- 提供任务查询接口，例如 `GET /api/jobs/{job_id}`；
- 前端通过轮询或 WebSocket 展示进度；
- 支持失败重试和中断恢复。

### 9.3 前端 API 地址硬编码

**问题：**  
前端 API 地址写死为：

```ts
http://127.0.0.1:8000
```

如果后端端口变化、部署方式变化或通过局域网访问，会比较不方便。

**建议：**

- 使用 Vite 环境变量，例如 `VITE_API_BASE_URL`；
- 默认值保留 `http://127.0.0.1:8000`；
- 前端所有 API 模块共用一个统一 client，避免重复定义 `request()`。

### 9.4 导出接口没有直接下载文件

**问题：**  
导出接口目前返回 JSON，其中包含服务器本地文件路径。对于用户来说，前端无法直接下载或打开这个路径。

**建议：**

- 导出接口直接返回 `FileResponse`；
- 或提供下载接口：`GET /api/trips/{trip_id}/export/files/{filename}`；
- 前端导出后自动触发浏览器下载。

### 9.5 部分解析规则存在硬编码

**问题：**  
例如机票订单截图解析中，`X月X日` 被硬编码为 2026 年：

```py
year = 2026
```

这会导致其他年份的数据解析错误。

**建议：**

- 优先从项目日期、文件夹日期、发票日期中推断年份；
- 如果无法推断，则标记为低置信度并加入异常；
- 不要在解析器中写死具体年份。

### 9.6 规则解析可维护性会逐渐变差

**问题：**  
当前分类和解析大量依赖关键词、正则表达式和特殊分支。随着票据类型增多，代码会越来越难维护。

**建议：**

- 为每种票据类型建立独立 parser，并统一 parser 输出协议；
- 将关键词规则外置到配置文件，例如 YAML / JSON；
- 增加规则优先级和命中解释，方便调试；
- 为真实 OCR 样例建立回归测试集。

### 9.7 缺少自动化测试

**问题：**  
目前未看到系统性的测试代码。对于 OCR 文本解析类项目，缺少测试会导致后续修改容易引入回归。

**建议：**

重点补充以下测试：

- 文件夹日期解析测试；
- 发票分类测试；
- 高铁票文本解析测试；
- 高铁票坐标解析测试；
- 机票 / 酒店 / VAT 发票解析测试；
- 费用汇总测试；
- 异常检测测试；
- 导出结果结构测试。

### 9.8 缺少数据库迁移机制

**问题：**  
当前使用 `Base.metadata.create_all()` 初始化表，但没有 Alembic 等迁移工具。后续模型字段变更后，本地已有数据库可能无法自动升级。

**建议：**

- 引入 Alembic；
- 为每次模型变更生成迁移脚本；
- 启动时检查数据库版本；
- 对个人本地工具，也可以提供“一键备份并升级数据库”的脚本。

### 9.9 删除项目可能不删除本地缓存文件

**问题：**  
删除 Trip 会删除数据库记录，但预处理生成的缓存图片、缩略图、导出文件可能仍留在 `data/cache`、`data/thumbnails`、`data/exports`。

**建议：**

- 删除项目时清理相关缓存；
- 或提供“清理缓存”功能；
- 缓存文件名最好包含 trip_id / document_id，便于定位和清理。

### 9.10 PDF 报告中文支持可能不足

**问题：**  
`reportlab` 默认字体通常不支持中文。当前 PDF 报告以英文为主，如果后续需要输出中文字段、中文路线、中文公司名，可能出现乱码或缺字。

**建议：**

- 注册中文字体，例如思源黑体、微软雅黑；
- PDF 模板中统一使用支持中文的字体；
- 增加中文 PDF 导出测试。

### 9.11 错误处理和用户提示还可以加强

**问题：**  
一些后端服务中 `except Exception` 后直接返回空结果或失败状态，错误上下文有限。前端也多处简单 `catch(() => {})`。

**建议：**

- 后端记录结构化日志；
- API 返回可读错误码和建议；
- 前端显示更明确的失败原因；
- 对 OCR 服务不可用、PDF 渲染失败、文件路径无权限等情况给出明确提示。

### 9.12 本地路径和跨平台兼容性需加强

**问题：**  
项目定位是本地工具，但当前启动脚本和文件选择逻辑更偏 Windows 桌面环境。

**建议：**

- 提供 Windows / macOS / Linux 分别的启动说明；
- 避免启动脚本硬编码 Python 路径；
- 提供 `.env` 或配置文件设置 Python / 服务路径；
- 对 tkinter 不可用的环境提供手动输入文件夹路径的替代方案。

## 10. 建议优先级

### P0：优先修复

1. 统一配置来源，让设置页真正影响 OCR 服务；
2. 去除年份硬编码；
3. 增加关键解析器的单元测试；
4. 优化导出下载体验。

### P1：近期增强

1. 将 OCR / 分析改为后台任务；
2. 前端 API 地址改为环境变量；
3. 增强错误提示和日志；
4. 增加缓存清理机制。

### P2：长期优化

1. 引入数据库迁移；
2. 规则配置外置；
3. 增强 PDF 中文报告；
4. 建立真实 OCR 样例回归测试集；
5. 支持更完整的票据编辑、人工校正和复核闭环。

## 11. 总结

Trip Helper 已经具备一个可用的本地差旅发票整理工具雏形，核心流程完整，尤其是高铁票坐标级解析、平台订单截图与正式发票区分、费用分类汇总和异常检测这些功能，体现出对真实报销场景的理解。

当前项目最值得继续投入的方向不是增加更多页面，而是提升稳定性和可维护性：统一配置、后台任务化、补充测试、完善导出下载、去除硬编码，并逐步把规则解析体系整理成更容易扩展和回归验证的结构。
