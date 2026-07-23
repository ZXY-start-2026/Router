# 多模型路由聊天系统

当前实现范围为 LLD 规定的**迭代3**：在迭代2基础上，已增加三种回答重新生成、回答历史版本按需查看与激活、历史用户消息编辑、新分支创建与切换，并保持原消息、原回答和原分支不可变。

360 搜索按本轮确认暂不实现：每轮保存明确的失败搜索快照后继续生成。MODEL_C 保留配置槽但默认禁用。备忘录和角色将在后续迭代实现。

## 变更日志

### 2026-07-23

- **迭代3：**新增原模型、自动路由、临时指定模型三种重新生成方式
- **迭代3：**新增回答历史版本按需加载、预览和安全激活
- **迭代3：**新增历史用户消息编辑、不可变分支创建、分支列表与切换
- **迭代3：**新增 `0003_answer_branching` 迁移及 6 个 API 端点
- **迭代3：**后端 39 项测试、前端 17 项测试全部通过，生产构建和迁移升降级通过
- **文档：**新增 `docs/iteration3-plan.md` 并同步 `docs/LLD.md`
- **新增：**会话卡片删除按钮，鼠标悬停时显示，触屏设备始终显示
- **新增：**删除会话前弹出二次确认，支持取消、按 `Escape` 或点击遮罩关闭
- **调整：**删除仅在当前浏览器隐藏会话，不调用后端删除接口，后端数据保持不变
- **新增：**通过 `localStorage` 持久化隐藏状态，刷新页面后仍保持隐藏
- **调整：**删除当前会话后，聊天主区域自动恢复为未选择状态
- **文档：**同步更新详细设计文档 `docs/LLD.md`
- 前端隐藏会话相关测试继续通过

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
