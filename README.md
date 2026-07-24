# 多模型路由聊天系统

这是一个本地单用户的多模型聊天系统。当前项目已实现迭代1～5：会话与消息、联网搜索快照、MIRT 路由与成本审计、回答版本与分支、分支级备忘录、会话角色和角色模板。

## 当前能力

- 三模型自动路由、自动降级和单次手动指定。
- 搜索、上下文、路由、生成任务和模型尝试均保存不可变快照。
- 回答重新生成、历史版本预览和安全激活。
- 编辑历史消息时创建新分支，原消息和原分支保持不变。
- 左侧会话删除仅在当前浏览器隐藏，二次确认后写入 `localStorage`，不删除后端数据。
- 分支级备忘录分为“用户保护区”和“系统摘要区”。
- 默认第 10 个完整轮次总结前 5 轮，之后每 5 轮增量更新一次。
- 备忘录版本不可变，支持历史查看、恢复和分支继承。
- 会话角色包含人格、背景、专业领域、性格特征、表达风格和回答约束。
- 角色修改仅影响当前活动分支的后续消息，新分支继承分叉位置实际使用的角色。
- 支持创建角色模板和显式停用当前分支角色。

360 搜索仍按当前项目约定保存明确的失败快照后继续生成；正式搜索 Provider 尚未接入。`MODEL_C` 保留配置槽，是否启用由 `backend/config/models.yaml` 决定。

## 环境要求

- Python 3.11+
- Node.js 20+
- pnpm

## 后端配置

模型、展示名称、价格、Tokenizer 和接口地址统一配置在：

```text
backend/config/models.yaml
```

后端环境变量位于 `backend/.env`：

| 配置 | 默认/示例 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/chat.db` | SQLite 数据库 |
| `CORS_ORIGINS` | `http://localhost:5173` | 前端地址 |
| `MOCK_PROVIDER_ENABLED` | `false` | 本地 Mock 开关，生产环境禁止开启 |
| `MEMORY_N` | `10` | 首次备忘录更新所需完整轮数 |
| `MEMORY_K` | `5` | 保留的最近原始完整轮数 |
| `MEMORY_M` | `5` | 后续增量更新间隔 |
| `MEMORY_MODEL_ID` | `MODEL_A` | 固定执行摘要和冲突检测的模型 |

模型接口使用 `/v1/completions`，不会发送 `Authorization`。备忘录固定使用 `MEMORY_MODEL_ID`，不经过路由；暂时性错误只使用同一模型重试一次。

## 启动后端

在 PowerShell 中执行：

```powershell
cd D:\codex\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --env-file .env
```

后端默认地址：`http://localhost:8000`
OpenAPI：`http://localhost:8000/docs`

如果原数据库停留在迭代3，只需执行：

```powershell
cd D:\codex\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

迁移 `0004_memory` 和 `0005_roles` 只增加表、索引和可空外键，不重写已有消息、回答或分支内容。

## 启动前端

另开一个 PowerShell：

```powershell
cd D:\codex\frontend
pnpm install
pnpm dev
```

前端默认地址：`http://localhost:5173`。Vite 会把 `/api` 转发到本地后端。

聊天顶部的“备忘录”和“角色”入口使用独立右侧抽屉；分支切换器位于单独工具栏，不与连接状态合并。

## 自动化验证

后端：

```powershell
cd D:\codex\backend
.\.venv\Scripts\python.exe -m pytest
```

前端组件测试和生产构建：

```powershell
cd D:\codex\frontend
pnpm test
pnpm build
```

首次运行浏览器端到端测试需要安装 Chromium：

```powershell
cd D:\codex\frontend
pnpm exec playwright install chromium
pnpm test:e2e
```

Playwright 使用隔离的测试 SQLite 和 Mock Provider，不访问真实模型、路由资产或搜索服务。

## 主要 API

### 会话、消息和分支

- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{id}/messages`
- `POST /api/v1/conversations/{id}/messages`
- `POST /api/v1/messages/{id}/regenerations`
- `GET /api/v1/messages/{id}/answers`
- `POST /api/v1/messages/{id}/answers/{answer_id}/activate`
- `PATCH /api/v1/messages/{id}`
- `GET /api/v1/conversations/{id}/branches`
- `POST /api/v1/conversations/{id}/branches/{branch_id}/activate`

### 备忘录

- `GET /api/v1/branches/{id}/memory`
- `GET /api/v1/branches/{id}/memory/versions`
- `PUT /api/v1/branches/{id}/memory`
- `POST /api/v1/branches/{id}/memory/versions/{version_id}/restore`

### 角色

- `GET /api/v1/conversations/{id}/role`
- `PUT /api/v1/conversations/{id}/role`
- `POST /api/v1/conversations/{id}/role/deactivate`
- `GET /api/v1/role-templates`
- `POST /api/v1/role-templates`

## 目录说明

- `docs/LLD.md`：已同步迭代1～5的详细设计基线。
- `docs/iteration3-plan.md`：迭代3实现文档。
- `docs/iteration4-plan.md`：分支备忘录实现文档。
- `docs/iteration5-plan.md`：角色与端到端测试实现文档。
- `backend/app`：FastAPI、SQLAlchemy、Service、Repository 和 Provider。
- `backend/alembic`：数据库迁移，当前最新版本为 `0005_roles`。
- `backend/resources/router`：MIRT、BERT、Embedding 和模型映射资产。
- `backend/resources/tokenizers`：模型 Tokenizer。
- `backend/tests`：后端单元和 API 测试。
- `frontend/src`：React 页面、API 客户端、Hooks、组件和 Vitest 测试。
- `frontend/e2e`：Playwright 浏览器端到端测试。

## 变更日志

### 2026-07-24

- **迭代4：**新增不可变分支备忘录、自动增量摘要、保护区编辑、冲突提示、版本恢复和分支继承。
- **迭代4：**新增 `0004_memory` 迁移和 4 个备忘录 API。
- **迭代5：**新增不可变角色版本、角色停用、角色模板和分叉点角色继承。
- **迭代5：**新增 `0005_roles` 迁移和 5 个角色 API。
- **前端：**新增备忘录与角色右侧抽屉，保持分支工具栏和连接状态独立。
- **兼容修复：**读取历史回答时过滤模型续写的 `User:/System:` 后续轮次，仅清理展示和上下文，不改写数据库原文。
- **备忘录修复：**内部摘要使用固定模型对应的指令模板，每次只处理一个5轮批次，并拒绝异常超长摘要。
- **测试：**新增备忘录、角色组件/API测试和 Playwright 核心流程。
- **文档：**新增 `docs/iteration4-plan.md`、`docs/iteration5-plan.md`，并将确认后的设计同步到 `docs/LLD.md`。

### 2026-07-23

- **迭代3：**新增原模型、自动路由、临时指定模型三种重新生成方式。
- **迭代3：**新增回答历史版本按需加载、预览和安全激活。
- **迭代3：**新增历史用户消息编辑、不可变分支创建、分支列表与切换。
- **迭代3：**新增 `0003_answer_branching` 迁移及 6 个 API 端点。
- **迭代3：**后端 39 项测试、前端 17 项测试全部通过，生产构建和迁移升降级通过。
- **Prompt 修复：**回归 `User:/Assistant:` 格式，HTTP 请求仅含 `prompt`、`max_tokens`、`temperature`、`stop`，使用 `stop: ["\nUser:"]` 防止模型自我循环输出。
- **新增：**`DELETE /api/v1/conversations/{id}` 软删除端点，后端数据保留，仅标记为 `ARCHIVED`，列表自动过滤。
- **新增：**Enter 发送消息，Shift+Enter 换行。
- **新增：**会话卡片删除按钮，鼠标悬停时显示，触屏设备始终显示。
- **新增：**删除会话前二次确认，支持取消、按 `Escape` 或点击遮罩关闭。
- **调整：**当前前端删除入口仅在本浏览器隐藏会话，不调用后端删除接口；隐藏状态写入 `localStorage`。
- **调整：**删除当前会话后，聊天主区域自动恢复为未选择状态。
- **文档：**新增 `docs/iteration3-plan.md` 并同步 `docs/LLD.md`。
- **阶段性验收：**后端 19 项测试、前端 6 项测试通过；迭代3最终验收结果以上述 39/17 项为准。
