# FieldPilot｜跨城外勤任务编排 Agent

FieldPilot 面向经常跨省市出差的外勤人员，把口语描述中的地点、任务时间窗、紧密程度、交通偏好和公司报销规则转换为可验证、可比较、可动态重规划的执行方案。

当前开发版本是可本地运行的 `0.4.0-dev`。PydanticAI 单 Agent 只负责自然语言到严格 MissionDraft 的转换；确定性 Planner、Policy Engine 和独立 Verifier 负责时窗、候选、费用与报销判断。系统不会让模型编造车次、计算成本或执行购票订房。

> `0.1.0` 是已提交、可回退的技术基线，不是最终求职版本。目标 `v1.0` 将围绕真实跨城出差、任务时窗、报销约束和动态重规划重构；完整设计见 [企业级目标设计](docs/specs/2026-07-30-fieldpilot-enterprise-design.md)。在对应实现、评测和部署证据完成前，目标设计中的能力不得写成已落地事实。

当前实现已完成领域持久化、有限搜索规划、高德路线与餐饮适配及降级、Agent 解析与审计、事件驱动重规划、执行检查点、严格后缀重规划、修订差异和 Vue 工作台闭环。高德与 LLM 真实密钥、Docker 容器和公网部署仍未在本机完成验证，相关能力不会冒充已上线。

![FieldPilot v1 工作台](docs/fieldpilot-workbench.png)

## 已完成的业务闭环

```text
自然语言输入 -> PydanticAI MissionDraft / 澄清问题
-> Mission + VisitTask + ExpensePolicy 持久化
-> Candidate Provider（高德路线/餐饮 POI live/mixed 或显式 Fixture）
-> PolicyEngine -> Bounded Planner -> Independent Verifier
-> PlanRevision / ProviderSnapshot -> Vue 时间线与来源展示
-> ExecutionCheckpoint 锁定/完成已执行前缀
-> ReplanEvent 原子应用 -> 仅求解可变后缀 -> Revision Diff
```

已实现：

- 自然语言双态输出：完整时生成严格草案，缺失时最多返回三组澄清问题；AgentRun 只保存输入指纹和结构化结果。
- 1～7 天、1～6 个工作任务、任务时窗、优先级、交通偏好与报销上限的严格领域契约。
- 有界 Beam Search 返回最多三个方案；Policy Engine 过滤硬约束，Verifier 独立复算任务覆盖、时间重叠、费用和合规。
- 高德 v3 地理编码与 v5 市内路线/周边餐饮 POI 适配，具备异步并发、超时、有限重试、调用预算、缓存和逐能力降级。
- Planner 在工作点、交通枢纽或酒店附近的可用缓冲中安排餐次；只采用带人均消费且不超过剩余餐补的候选，Policy Engine 按自然日核算，Verifier 复查餐次、锚点、时间窗和费用。
- 计划请求、Agent 请求与业务事件分别幂等；active revision 使用乐观并发控制。
- 任务改期/取消/新增/延长、预算和偏好事件可原子应用；天气与交通中断在尚未接入规划过滤前明确标记 `recorded_only`。
- 执行检查点命令使用 command ID 幂等与版本号并发控制；锁定/完成位置只能单调前进，重规划会逐段保留已执行前缀并从检查点恢复后缀求解，Verifier 再独立校验边界。
- Vue 3 + TypeScript 工作台展示 Agent trace、候选比较、执行时间线、政策判定、来源快照和重规划差异。
- SQLite 本地验证与 PostgreSQL Compose 交付配置；Alembic 迁移、健康/就绪检查和 GitHub Actions CI。

## 当前证据边界

| 能力 | 当前状态 | 验收边界 |
| --- | --- | --- |
| FastAPI + Pydantic 数据契约 | 已实现并测试 | 结构化 API 可复现 |
| PydanticAI 单 Agent + MissionDraft | 已实现结构化输出、Mock/fallback 和 TestModel 测试；真实模型未复验 | 只验收类型化语义入口，不声称真实模型质量 |
| 高德 v5 市内路线适配 | 已进入规划链路并完成 MockTransport 契约/故障测试；真实密钥未复验 | 已验证适配与降级，未验证实时服务可用性 |
| 高德 v5 周边餐饮 POI | 已实现预算过滤、缓存、失败降级和来源快照；真实密钥未复验 | 无人均消费字段的 POI 不进入方案，Fixture 不冒充实时报价 |
| Vue v1 任务、方案、来源与重规划工作台 | 已实现并完成生产构建 | 本地真实浏览器链路已验收 |
| Mission、政策快照与计划修订持久化 | 已实现并测试 | SQLite 已验证，PostgreSQL 容器尚未实跑 |
| 有限搜索 Planner + Policy Engine + 独立 Verifier | 已实现；跨城、酒店和无 Key 餐饮使用明确 Fixture | 确定性规划可复现，数据模式必须随 segment 传递 |
| 计划请求幂等、revision 冲突与激活 | 已实现并测试 | 并发与重放路径已有接口测试 |
| AgentRun 审计、幂等与固定集 | 已实现输入指纹、trace 查询和 5 场景 Mock 基线 | Mock 指标不能替代真实模型指标 |
| ReplanEvent 事实应用与 Revision Diff | 已实现并测试；外部风险信号仅 recorded_only | 不声称所有中断已自动处置 |
| ExecutionCheckpoint 与严格后缀重规划 | 已实现命令幂等、版本冲突、单调锁定/完成和前缀逐段一致性校验 | 只重算检查点后的可变后缀；有界搜索不声称全局最优 |
| CrewAI、LlamaIndex、Pydantic Evals | 未接入 | 当前业务不需要 |
| RAG、审批流、SSE、全局路线最优化 | 未实现 | 不属于当前已验收能力 |
| 独立公网部署 | 未完成 | 不提供或复用其他项目 URL |

## 本地运行

### 后端

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\backend
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\alembic.exe upgrade head
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

### Docker Compose（配置已提供，本机尚未验证）

```powershell
docker compose up --build
```

浏览器访问 <http://localhost:8080>。Compose 使用 PostgreSQL，并在 API 启动前执行 Alembic 迁移。

## 杭州跨城示例

结构化示例位于 [`examples/hangzhou-mission-v1.json`](examples/hangzhou-mission-v1.json)，前端内置同场景自然语言：上海出发、杭州两日三任务、高铁二等座、酒店/餐补/市内交通和总预算约束。执行后会得到三个可解释候选方案，时间线包含工作点或酒店附近的餐次，并可修改任务时间触发 R2 与差异视图。Fixture 交通、住宿和餐饮只用于验证工程闭环，不代表实时票价、库存、酒店或餐饮报价。

## 真实模式

密钥只放在 `backend/.env` 或云平台环境变量中：

```env
USE_MOCK_TOOLS=false
USE_MOCK_LLM=false
AMAP_API_KEY=
LOCAL_ROUTE_PROVIDER=amap
PROVIDER_TIMEOUT_SECONDS=3.0
PROVIDER_MAX_RETRIES=1
PROVIDER_MAX_CONCURRENCY=4
PROVIDER_MAX_LIVE_CALLS=32
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

后端 `AMAP_API_KEY` 与浏览器 `VITE_AMAP_JS_KEY` 不是同一种 Key。`LOCAL_ROUTE_PROVIDER=fixture` 完全离线；设为 `amap` 后按路线查询真实接口，失败会保留原因并逐项降级。真实密钥完成复验前，不应声称线上可用。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

当前本机结果（2026-07-31）：后端 `46 passed`；Alembic `upgrade head / check / downgrade 20260730_0003 / upgrade head` 通过；前端 `vue-tsc --noEmit && vite build` 成功；运行中 HTTP 冒烟与真实浏览器主链路通过，执行检查点从 V0 推进至 V2，R2 严格保留受保护前缀。Docker CLI 未安装，因此容器构建未验证。详细记录见 [开发日志](docs/development-log.md)。

运行中的完整 HTTP 冒烟（需要先启动后端）：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_workflow.py
```

## 项目演进

FieldPilot 的早期工程基础来自本人此前完成并部署的“智能旅行助手”，其中前后端分层和外部工具接入方式参考了 Datawhale HelloAgents 第十三章。在此基础上，FieldPilot 面向真实外勤场景重新设计了领域模型、Agent 边界、API 契约、任务与报销语义、规划验证链路及页面信息架构。

两个项目各自维护独立的代码目录、数据契约与部署配置。原旅行助手 `1.0.0` 冻结目录和 `1.0.1` 工作区保持不变，FieldPilot 的迭代记录与验证证据均在本仓库独立维护。

## 文档

- [架构与技术取舍](docs/architecture.md)
- [简历与面试事实口径](docs/resume-project-description.md)
- [后续迭代边界](docs/roadmap.md)
- [企业级目标设计（Target v1.0）](docs/specs/2026-07-30-fieldpilot-enterprise-design.md)
- [开发日志](docs/development-log.md)
- [Mission Interpret v1 Mock 基线报告](docs/evals/mission-interpret-v1-baseline.md)
- [五分钟演示与面试讲解](docs/demo-guide.md)
- [发布验收清单](docs/release-readiness.md)
