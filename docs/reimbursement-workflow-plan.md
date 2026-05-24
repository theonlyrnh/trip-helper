# Reimbursement Workflow Implementation Plan

> 目标：在不依赖 PaddleOCR 的前提下，把 Trip Helper 优化为可交付使用的本地差旅/日常发票整理工作台。

## 已完成的版本保护

- 当前仓库：`D:\trip-helper`
- 远程仓库：`https://github.com/theonlyrnh/trip-helper.git`
- 开发分支：`feature/reimbursement-workflow`
- 旧版保护 tag：`v0.3.1-before-reimbursement-workflow`
- 旧版 tag 指向提交：`63fd8fd2c3a92202980d191fb3b47a84cb7e11e5`
- 旧版 tag 已通过 `127.0.0.1:7890` 代理推送到 GitHub。

## 本轮明确不做

- 不测试 PaddleOCR 服务连通性。
- 不要求本机安装 PaddleOCR。
- 不把 OCR 成功作为本轮验收条件。
- 不删除、移动、覆盖 `D:\发票` 原始文件。
- 不提交 `D:\发票` 中的真实发票、`.env`、API Key、token 或隐私数据。

## 样例基准

`D:\发票\标准.txt` 当前是自然语言短句格式，可保守解析：

- 发票号码。
- 总金额。
- 高铁票的出发日期、出发时间、出发站、到达站、车次。

不假设每一行字段都完整；无法自动识别的图片/扫描件只提示需要人工录入或确认。

## 分阶段实施

### 阶段 A：后端核心业务闭环

1. 增加最小 pytest 测试结构，使用构造数据验证汇总规则。
2. 新增 `backend/services/invoice_service.py`：
   - 查询项目票据；
   - 单张更新；
   - 批量更新；
   - 状态映射；
   - 保存后刷新汇总、行程、住宿和异常。
3. 新增 `backend/routers/invoices.py`：
   - `GET /api/trips/{trip_id}/invoices`
   - `PATCH /api/invoices/{invoice_id}`
   - `POST /api/trips/{trip_id}/invoices/bulk-update`
4. 新增或完善异常更新接口：
   - `PATCH /api/issues/{issue_id}`
5. 修改工作台接口，返回票据级报销/人工复核字段。
6. 修改导出接口为浏览器直接下载 `FileResponse`。
7. 完善 Excel，确保导出金额和工作台汇总一致。

### 阶段 B：前端业务闭环

1. 补齐 `frontend/src/api/trips.ts` 类型与 API。
2. 工作台票据表格支持：
   - 多选；
   - 单张报销状态切换；
   - 批量状态切换；
   - 确认金额；
   - 备注；
   - 详情抽屉结构化字段编辑。
3. 异常支持查看关联票据、解决、忽略。
4. 导出区支持 Excel/PDF 直接下载。
5. OCR 不可用时，非 OCR 业务继续可用，界面给出友好提示。

### 阶段 C：样例校验与文档

1. 新增 `scripts/verify_samples.py`：只读 `D:\发票` 和 `标准.txt`，输出保守对比结果。
2. 更新 README：安装、启动、可选 OCR、人工复核、报销状态、导出、版本切换。
3. 改进启动脚本，避免把固定 Python 路径写成唯一依赖。

### 阶段 D：最终验证和推送

1. 后端测试：不测试 PaddleOCR。
2. 前端构建或类型检查。
3. 样例脚本只读验证。
4. 检查 `git status`、`git diff`、`git log`、`git remote -v`。
5. 检查无真实发票、`.env`、API Key、token。
6. 推送 feature 分支，验证通过后更新 main。
7. 创建并推送新版 tag：`v0.4.0-reimbursement-workflow`。
