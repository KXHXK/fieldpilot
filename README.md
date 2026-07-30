# FieldPilot｜城市外勤任务编排 Agent

FieldPilot 面向商务拓展、市场调研、巡店与线下执行人员，把执行城市、目标场所、环境风险、预算和任务目标整理为可编辑、可导出的每日外勤方案。

当前版本是可本地运行的 `0.1.0 MVP`。它采用混合式 Agent 工作流：确定性代码负责数据校验、点位去重、日期分配和成本计算，可选 LLM 仅对已经形成的结构化计划做受约束总结。系统不会让模型直接生成权威点位、计算成本或执行外部动作。

## 已完成的业务闭环

```text
Vue 3 表单
-> FastAPI / Pydantic 请求校验
-> FieldPilotCoordinator
-> 并行执行 FieldRiskAgent + TargetDiscoveryAgent
-> BaseLocationAgent
-> TaskPlanningAgent
-> 确定性成本计算 + 可选 LLM 摘要
-> 结构化 FieldTaskPlan
-> 点位、风险、日程、成本、工具状态展示
```

已实现：

- `POST /api/field-task/plan` 完整业务接口与 `/api/health` 健康检查。
- `FieldRiskAgent`、`TargetDiscoveryAgent`、`BaseLocationAgent`、`TaskPlanningAgent` 和总协调器。
- 目标点位按名称与地址去重，按日期分配时不循环复用旧点位。
- 高德点位、Tavily 环境检索、Kimi/OpenAI-Compatible 摘要的可选适配；显式超时、有限并发和逐工具降级。
- 无密钥 Mock 模式，可复现上海 3 日外勤案例；页面明确标记合成数据与降级状态。
- Vue 3 + TypeScript 任务表单与结果工作台，支持点位地图/坐标回退、任务顺序调整、删除、文本导出和浏览器打印 PDF。
- 后端 5 条自动化测试通过，前端 TypeScript 检查与生产构建通过。

## 当前证据边界

| 能力 | 当前状态 | 可以怎样表述 |
| --- | --- | --- |
| FastAPI + Pydantic 数据契约 | 已实现并测试 | 可写入简历 |
| 4 个专职 Agent + Coordinator | 已实现并测试 | 可写“受控多角色工作流”，不写“完全自治” |
| 并行点位/风险收集 | 已实现，Mock 路径已测试 | 可写“并行编排独立工具步骤” |
| 高德/Tavily/Kimi 适配 | 代码已接入，FieldPilot 尚未用真实密钥复验 | 暂不写成“真实服务已上线” |
| Vue 编辑、导出、地图回退 | 已实现并完成生产构建 | 可写入项目说明 |
| CrewAI、LlamaIndex、Pydantic Evals | 未接入 | 不写入简历 |
| 数据库、RAG、审批流、SSE、缓存、路线最优化 | 未实现 | 不写入简历 |
| 独立公网部署 | 未完成 | 不提供或冒用原项目 URL |

## 本地运行

### 后端

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\backend
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

访问：

- OpenAPI：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

### 前端

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。Vite 开发服务器会把 `/api` 代理到本地后端。

## 上海示例

示例输入位于 [`examples/shanghai-field-task.json`](examples/shanghai-field-task.json)：

- 城市：上海
- 周期：3 天
- 行业：新能源汽车
- 目标场所：品牌门店、核心商圈
- 目标：调研品牌门店分布与周边竞品
- 预算：3000 元
- 交通：公共交通
- 驻点偏好：靠近地铁，便于覆盖多个商圈

执行后会得到 3 天方案、6 个不重复合成点位、每日环境风险、驻点建议、成本拆分和 5 个工具/编排步骤状态。合成点位只用于验证工程闭环，不代表实时商业事实。

## 真实模式

密钥只放在 `backend/.env` 或云平台环境变量中：

```env
USE_MOCK_TOOLS=false
USE_MOCK_LLM=false
AMAP_API_KEY=
TAVILY_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.moonshot.cn/v1
MODEL_NAME=kimi-k2.6
```

浏览器交互地图使用独立的 Web JS 凭证，在 `frontend/.env` 配置：

```env
VITE_AMAP_JS_KEY=
VITE_AMAP_JS_SECURITY_CODE=
```

后端 `AMAP_API_KEY` 与浏览器 `VITE_AMAP_JS_KEY` 不是同一种 Key。真实模式在 FieldPilot 中重新完成复验前，不应声称线上可用。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

当前本机结果：后端 `5 passed`；前端 `vue-tsc --noEmit && vite build` 成功。结果需要在后续代码变化后重新运行。

## 来源与二次开发说明

初始前后端分层与工具治理经验受 Datawhale HelloAgents 第十三章启发，并来自本人已完成、部署过的“智能旅行助手”项目。FieldPilot 在独立目录中重新实现了外勤领域模型、Agent 职责、请求/响应契约、点位任务语义、页面信息架构、Mock 数据、导出内容和项目文档；原 `1.0.0` 冻结目录和 `1.0.1` 工作区未被修改。

这不是只替换标题的包装项目。旅行项目中的“目的地/景点/酒店/行程”类型没有进入 FieldPilot 的接口与 UI；两个项目也不会共用线上 URL 或部署身份。

## 文档

- [架构与技术取舍](docs/architecture.md)
- [简历与面试事实口径](docs/resume-project-description.md)
- [后续迭代边界](docs/roadmap.md)
