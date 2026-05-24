# Trip Helper - 本地差旅/日常发票整理工作台

Trip Helper 是一个本地运行的差旅/日常发票整理工具。它可以扫描本地发票文件夹，整理票据，支持人工复核、选择本次报销范围、维护已报销/暂不报销/待确认状态，并导出可下载的 Excel/PDF 材料。

> 当前版本重点是“可交付的本地报销整理闭环”。PaddleOCR 是可选增强能力；没有安装 PaddleOCR 时，仍可使用电子 PDF 文本提取、人工录入/修正、报销选择、汇总和导出。

## 核心能力

- 📂 选择本地发票文件夹，扫描 PDF/图片文件。
- 🧾 票据级报销状态管理：
  - 本次报销；
  - 已报销；
  - 暂不报销；
  - 待确认。
- ✅ 用户可以自由选择哪些票据计入本次报销。
- 🧮 汇总只统计 `THIS_TRIP + include_in_summary=true` 的票据。
- 💰 `confirmed_amount` 优先于自动识别金额参与汇总和导出。
- 🚫 订单截图、酒店预订截图、辅助凭证默认不重复计入金额。
- ✍️ 支持人工修正金额、日期、车次/航班号、费用类别、住宿信息等结构化字段。
- ⚠️ 异常支持查看关联票据、标记已解决、标记忽略。
- 📥 Excel/PDF 支持浏览器直接下载；Excel 是主交付物，明细中区分本次报销、已报销、暂不报销、待确认和辅助凭证。
- 🤖 OCR 可选：电子 PDF 可通过 PyMuPDF 提取文本；图片/扫描件在无 OCR 环境时可人工录入。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：React + Vite + TypeScript
- PDF：PyMuPDF（电子 PDF 文本提取、PDF 页面渲染）
- 导出：openpyxl + reportlab
- OCR：本地 PaddleOCR-VL / 远程 Qwen3-VL 均为可选能力，不是运行工作台的强依赖

## 环境要求

- Python 3.11+ 或 3.12+
- Node.js 18+
- npm

本仓库不强制某个固定 Python 安装路径。Windows 下一键脚本会按顺序尝试：

1. `PYTHON` 环境变量；
2. `python` 命令；
3. `py` 启动器。

如果你的机器上使用 conda/uv/其他虚拟环境，也可以直接用对应环境中的 Python 启动后端。

## 安装依赖

### 后端

```bash
pip install -r backend/requirements.txt
```

如果本机没有系统级 `python`，也可以用 `uv` 临时运行或创建环境，例如：

```bash
uv run --python 3.11 --with-requirements backend/requirements.txt python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
```

## 启动方式

### Windows 一键启动

双击：

```text
start.bat
```

或分别启动：

```text
start_backend.bat
start_frontend.bat
```

### 手动启动

后端：

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
cd frontend
npm run dev
```

浏览器打开：

```text
http://localhost:5173/workspace
```

## 使用流程

1. 打开工作台。
2. 点击“选择文件夹”，选择你本地的发票目录。
3. 点击“一键分析”，或在“高级”中分步执行：
   - 扫描；
   - 预处理；
   - OCR（可选）；
   - 分析。
4. 在“全部票据池”中逐张或批量设置报销状态：
   - 本次报销；
   - 已报销；
   - 暂不报销；
   - 待确认。
5. 点击“编辑”打开详情抽屉，人工修正：
   - 发票类型；
   - 费用类别；
   - 发票号码；
   - 发票日期/业务日期；
   - 销售方/购买方；
   - 识别金额/确认金额；
   - 车次/航班号、出发地、到达地、出发时间；
   - 酒店名称、入住/离店日期、住宿晚数；
   - 备注。
6. 在“异常处理”中查看关联票据，按需标记“已解决”或“忽略”。
7. 点击“导出 Excel”或“导出 PDF”。如存在未处理错误/警告，前端会提示是否继续导出。

## 无 PaddleOCR 时如何使用

本轮不要求安装 PaddleOCR。没有 PaddleOCR 时：

- 电子 PDF 如果包含原生文本，仍可通过 PyMuPDF 提取文本并进入解析流程；
- 图片票据或扫描 PDF 可能无法自动识别；
- 这些票据仍可在工作台中人工录入金额、日期、车次、费用类别等字段；
- 人工确认后的 `confirmed_amount` 会参与汇总和 Excel 导出；
- OCR 不可用不会阻塞票据管理、人工修正、报销选择、汇总和导出。

如以后需要启用 OCR，可复制 `.env.example` 为 `.env` 并配置：

```text
PADDLEOCR_API_URL=http://localhost:8118/v1
PADDLEOCR_MODEL=PaddleOCR-VL-1.5-0.9B
```

也可以配置远程视觉模型作为兜底，但请不要把 API Key 提交到仓库。

## 样例校验脚本

仓库提供只读校验脚本：

```bash
uv run --python 3.11 scripts/verify_samples.py --sample-dir "D:\发票"
```

脚本行为：

- 只读取样例目录和 `标准.txt`；
- 不删除、不移动、不覆盖原始发票文件；
- 不调用 PaddleOCR；
- 保守解析 `标准.txt` 中的发票号、金额、车次、日期、出发地/到达地；
- 对无法自动识别的图片/扫描件提示需要人工录入/确认。

> 注意：不要把本地真实发票目录（例如 `D:\发票`）复制进仓库，也不要提交真实发票、`.env`、API Key、token 或隐私数据。

## 测试与构建

后端核心测试（不测试 PaddleOCR）：

```bash
uv run --python 3.11 --with pytest --with fastapi --with "uvicorn[standard]" --with sqlalchemy --with pydantic --with python-dotenv --with requests --with pymupdf --with pillow --with openpyxl --with reportlab --with python-multipart --with httpx pytest tests -q --basetemp .pytest-tmp
```

前端构建：

```bash
cd frontend
npm run build
```

## 版本选择

GitHub 仓库：

```text
https://github.com/theonlyrnh/trip-helper
```

克隆最新版：

```bash
git clone https://github.com/theonlyrnh/trip-helper.git
cd trip-helper
```

切换优化前旧版：

```bash
git checkout v0.3.1-before-reimbursement-workflow
```

切换本次优化稳定版：

```bash
git checkout v0.4.0-reimbursement-workflow
```

## 项目结构

```text
trip-helper/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── models/              # 数据模型
│   ├── routers/             # API 路由
│   ├── services/            # 业务逻辑
│   ├── parsers/             # 发票解析器
│   ├── providers/           # OCR Provider（可选）
│   └── exporters/           # Excel/PDF 导出
├── frontend/
│   └── src/
│       ├── pages/           # 页面组件
│       ├── components/      # 通用组件
│       ├── api/             # API 客户端
│       └── utils/           # 标签与格式化
├── scripts/
│   └── verify_samples.py    # 只读样例校验脚本
├── tests/                   # 后端核心业务测试
├── README.md
└── start.bat                # Windows 一键启动
```
