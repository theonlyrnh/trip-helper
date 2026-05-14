# Trip Helper - 差旅发票智能整理助手

本地运行的差旅发票自动识别、分类、统计与报销材料生成工具。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **前端**: React + Vite + TypeScript
- **OCR**: 本地 PaddleOCR-VL / 远程 Qwen3-VL 兜底
- **PDF**: PyMuPDF（坐标级文字提取）

## 快速启动

### 环境要求

- Python 3.12（conda 环境）
- Node.js 18+

### 安装

```bash
# 后端依赖
pip install -r backend/requirements.txt

# 前端依赖
cd frontend && npm install
```

### 启动

双击 `start.bat`（Windows），或分别启动：

```bash
# 后端 (port 8000)
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 前端 (port 5173)
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173/workspace`

### 配置

复制 `.env.example` 为 `.env`，按需修改：

- `PADDLEOCR_API_URL`：本地 PaddleOCR 服务地址
- `REMOTE_API_BASE_URL`：远程 VL 模型地址（可选兜底）

## 功能

- 📂 选择发票文件夹，自动扫描 PDF/图片
- 🤖 三级识别策略：PyMuPDF 文本提取 → PaddleOCR → Qwen3 兜底
- 🚄 高铁票坐标级解析（开票日期 ≠ 乘车日期，起终点不反转）
- ✈️ 机票/酒店/增值税发票分类解析
- 🗺 路线时间线（按日期+时间排序）
- 💰 费用分类汇总（城际交通/住宿/餐饮/退改签费/补助）
- ⚠️ 异常检测（金额异常/日期越界/缺日期/低置信度）
- 📊 年度统计看板
- 📋 项目列表（报销状态管理）
- 📥 导出 Excel / PDF

## 项目结构

```
trip-helper/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── models/              # 数据模型
│   ├── routers/             # API 路由
│   ├── services/            # 业务逻辑
│   ├── parsers/             # 发票解析器
│   └── providers/           # OCR 供应商
├── frontend/
│   └── src/
│       ├── pages/           # 页面组件
│       ├── components/      # 通用组件
│       ├── api/             # API 客户端
│       └── utils/           # 工具函数
├── scripts/                 # 辅助脚本
└── start.bat                # 一键启动
```