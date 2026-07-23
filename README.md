# 多模型路由聊天系统

当前实现范围为 LLD 规定的**迭代2**：在迭代1基础上，已接入本地 MIRT+BERT 三模型路由、各模型真实 Tokenizer、统一 Prompt、无鉴权 `/v1/completions` 调用、搜索/上下文/路由快照、失败重试与自动降级，以及预测和实际 Token/成本审计。

360 搜索按本轮确认暂不实现：每轮保存明确的失败搜索快照后继续生成。MODEL_C 保留配置槽但默认禁用。回答重新生成、历史分支、备忘录和角色将在后续迭代实现。

## 环境要求

- Python 3.11+
- Node.js 20+
- pnpm

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

正式模型及展示名称在 `backend/config/models.yaml` 统一管理；模型接口不需要 API Key，也不会发送 `Authorization`。`.env` 已启用真实 Provider，测试通过依赖注入使用 Mock，不访问外网。

后端默认地址：`http://localhost:8000`，OpenAPI：`http://localhost:8000/docs`。

## 启动前端

另开一个 PowerShell：

```powershell
cd D:\codex\frontend
pnpm install
pnpm dev
```

前端默认地址：`http://localhost:5173`，Vite 会把 `/api` 转发到本地后端。

## 运行验证

```powershell
cd D:\codex\backend
.\.venv\Scripts\python.exe -m pytest

cd D:\codex\frontend
pnpm test
pnpm build
```

## 目录说明

- `docs/LLD.md`：完整详细设计与五个迭代边界。
- `backend/app`：FastAPI、SQLAlchemy、Service、Repository 和 Provider 接口。
- `backend/resources/router`：从已确认参考目录复制的 MIRT、BERT、Embedding 和映射资产。
- `backend/resources/tokenizers`：两个已启用模型的真实 Tokenizer。
- `backend/alembic`：迭代1与迭代2数据库迁移。
- `frontend/src`：React 页面、API 客户端、Hooks 与组件。
- `backend/tests`、`frontend/src/test`：自动化测试。

## 变更日志

### 2026-07-23
- **Prompt 修复**：回归 `User:/Assistant:` 格式，HTTP 请求仅含 `prompt`/`max_tokens`/`temperature`/`stop`，`stop: ["\nUser:"]` 防止模型自我循环输出
- **新增**：`DELETE /api/v1/conversations/{id}` 软删除端点，数据保留仅标记 ARCHIVED，列表自动过滤
- **新增**：Enter 发送消息，Shift+Enter 换行
- **新增**：会话卡片删除按钮（hover 显示），`window.confirm` 二次确认
- **新增**：迭代3实施计划文档 `docs/iteration3-plan.md`
- 后端 19 个测试、前端 6 个测试全部通过
