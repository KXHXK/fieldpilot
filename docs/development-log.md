# FieldPilot 开发日志

本文按“事实、决策、实现、验证、限制、下一步”记录开发过程，避免把目标设计与已完成能力混写。

## 2026-07-30｜Target v1.0 Stage 1：领域与持久化

### 基线

- 回退提交：`main@f723221`
- 开发分支：`feature/fieldpilot-v1-domain`
- 基线状态：后端 5 条测试通过，前端 TypeScript 与 Vite 生产构建通过。
- 既有 `POST /api/field-task/plan` 保留，未在 Stage 1 删除。

### 观察事实

- 原 `FieldTaskRequest` 以行业、目标场所和预算为核心，不能表达跨城出差、任务时间窗和报销政策。
- 原日程使用轮询分配，不计算交通可行性。
- 原成本使用固定数值，没有政策版本或历史快照。
- 原系统没有持久化 Mission、计划修订或事件幂等边界。

### 设计决策

1. 先实现领域和数据库，不先接 LLM、地图或规划算法。
2. v1 API 与 0.1 API 并存，降低重构风险。
3. 时间输入必须带时区；写入前统一为 UTC，同时保留 Mission 时区。
4. 金额使用整数元，避免浮点误差。
5. 报销政策随 Mission 保存快照，不能只引用可能变化的政策 ID。
6. Replan Event 使用唯一 `event_id`，重复事件返回同一记录。
7. 事件必须基于当前 `active_revision`，过期请求返回 `409`。
8. 不提供任意 PlanRevision 写入 API；等 Stage 2 Planner + Verifier 完成后再生成可信修订。
9. 本地默认 SQLite 便于启动，目标部署使用 PostgreSQL；ORM 和迁移均按两者兼容设计。

### 已实现

- `MissionCreate/MissionRead` 严格 Pydantic 契约。
- `LocationInput` 经纬度成对校验。
- 1–7 天任务周期、1–6 个现场、带时区时间窗和持续时间校验。
- 紧密程度、交通偏好、任务优先级和任务锁定字段。
- 交通等级、住宿、餐饮、市内交通和总预算政策契约。
- 八类 Replan Event 及各自 payload 校验。
- SQLAlchemy AsyncSession 和 SQLite/PostgreSQL 配置。
- Mission、VisitTask、ExpensePolicySnapshot、ProviderSnapshot、PlanRevision、ReplanEvent 表。
- Alembic 初始迁移及升级/降级。
- `POST /api/v1/missions`
- `GET /api/v1/missions/{mission_id}`
- `POST /api/v1/missions/{mission_id}/events`
- `GET /api/ready` 数据库就绪检查。
- 前端 `mission.ts` 镜像类型。
- 杭州两日外勤固定示例。

### 排障记录

#### 虚拟环境没有 pip

- 现象：`.venv\Scripts\python.exe -m pip` 返回 `No module named pip`。
- 诊断：该环境由 `uv` 创建，不能假设包含 pip。
- 处理：使用 `uv pip install --python backend\.venv\Scripts\python.exe -r backend\requirements.txt`。

#### Windows 无法识别 Asia/Shanghai

- 现象：Pydantic 校验合法时区时返回“未知时区”。
- 诊断：精简 Python 环境缺少 IANA 时区数据库。
- 处理：显式增加 `tzdata` 依赖，不放宽时区校验。

#### SQLite 丢失时区偏移

- 现象：首次创建响应和重新读取响应的时间相差 8 小时。
- 诊断：SQLite DateTime 不保留原始 `+08:00` 偏移。
- 处理：写入前统一转 UTC，读取时为无时区值恢复 UTC；Mission 单独保存业务时区。

#### Alembic 模式漂移

- 现象：`alembic check` 检测政策快照 `mission_id` 的普通索引与唯一索引不一致。
- 诊断：ORM 同时声明 `unique=True` 和 `index=True`，迁移又创建唯一约束与普通索引。
- 处理：统一为唯一约束，重新执行 downgrade/upgrade/check。

### 验证结果

- 后端：`12 passed`。
- 覆盖创建/读取、政策快照、任务顺序、事件幂等、revision 冲突、事件 payload、非法日期和数据库 readiness。
- Alembic：`upgrade head`、`downgrade base`、再次升级和 `alembic check` 通过。
- OpenAPI：存在 `/api/v1/missions`、任务读取、事件和 `/api/ready`。
- 前端：`vue-tsc --noEmit && vite build` 通过。
- Git：`git diff --check` 通过。

### 当前限制

- 尚未实现 Planner、Policy Engine 计算和独立 Verifier。
- ProviderSnapshot 只有表结构，没有高德/铁路/航班/酒店写入逻辑。
- PlanRevision 只有表结构，没有可信计划生成和激活 API。
- v1 前端只有 TypeScript 类型，尚未接入页面。
- PydanticAI、自然语言解析和模型评测尚未接入。
- PostgreSQL 迁移尚未在本机容器中实跑；当前已验证的是 SQLite。
- 本机未安装 Docker CLI；Dockerfile 已携带 Alembic 文件，但镜像构建和容器启动尚未验证。
- 当前变更尚未提交、发布或部署。

### 下一步

进入 Stage 2：使用冻结 Provider Fixture 实现 `PolicyEngine -> Candidate Normalizer -> Bounded Planner -> Independent Verifier`，生成第一版可持久化 `PlanRevision`。完成确定性场景和不变量测试后，再接高德真实 Provider。

## 2026-07-30｜Target v1.0 Stage 2：确定性规划内核

### 业务目标

把 Mission、任务时窗和报销政策转成可审计的候选方案：不仅给出行程结果，还保存候选数据快照、成本分类、政策判断、评分明细和计划修订，使同一输入可复现、可核验、可激活。

### 设计决策

1. 先使用版本固定的 Fixture Provider 验证业务语义，再接真实 API；所有输出显式标记 `source_mode=fixture`，不冒充实时交通或酒店数据。
2. 当前问题规模使用有限 Beam Search，而非引入 OR-Tools。任务排序、交通候选和住宿候选均有明确搜索上限，评分权重随紧密程度变化。
3. `PolicyEngine` 负责候选预过滤与整单报销判断；`PlanVerifier` 不信任 Planner 输出，独立复算任务覆盖、时窗、时间重叠、费用分类和政策合规。
4. 生成请求的 `request_id` 与动态重规划触发的 `input_event_id` 分离，避免把 API 幂等键错误解释为业务事件。
5. 计划生成只创建 draft revision；显式激活后才更新 Mission 的 `active_revision`。过期基线返回冲突，重复激活保持幂等。
6. 当前不引入 CrewAI、LlamaIndex 或 PydanticAI：确定性规划、政策核算和校验不需要 LLM，先用代码建立可信边界。

### 已实现

- 交通、住宿、路段、成本账本、政策决策、评分和修订的严格 Pydantic 契约。
- `FixtureCandidateProvider`：生成跨城铁路/航班、酒店与市内交通候选，并保留来源和假设。
- `PolicyEngine`：校验席别/舱位、住宿上限、市内交通/餐饮日限额和整单上限。
- `BoundedMissionPlanner`：枚举有限任务顺序和候选组合，执行时间窗、换乘缓冲、返程和预算约束，返回最多 3 个可解释选项。
- `PlanVerifier`：独立复算不变量，拒绝任务遗漏/重复、时间重叠、成本篡改、政策违规和不完整往返。
- ProviderSnapshot 与 PlanRevision 数据库存储，以及请求幂等、版本冲突、激活和旧版本 supersede。
- `POST /api/v1/missions/{mission_id}/plans`
- `GET /api/v1/missions/{mission_id}/revisions`
- `GET /api/v1/missions/{mission_id}/revisions/{revision_number}`
- `POST /api/v1/missions/{mission_id}/revisions/{revision_number}/activate`
- 杭州两日三任务固定场景，覆盖跨日住宿、任务转点与返程。

### 验证结果

- 后端：`17 passed`。
- 新增覆盖计划生成与持久化、候选快照、请求幂等、激活重放、过期 revision 冲突、旧版本 supersede、低预算无解和篡改方案拒绝。
- Alembic：`downgrade base -> upgrade head -> check -> current` 全部通过，当前为 `20260730_0001 (head)`。
- 前端：`vue-tsc --noEmit && vite build` 通过。

### 当前限制

- Provider 仍为 Fixture；高德路线、铁路/航班和酒店真实数据尚未接入和做契约测试。
- 餐饮暂以 `0` 计入并显式警告，尚未生成餐饮安排；出发地到车站/机场的首段接驳也未建模。
- Planner 是有界启发式搜索，不声称获得数学意义上的全局最优解。
- Replan Event 已持久化，但尚未把事件应用为新 Mission facts 并自动生成后续 revision。
- v1 前端任务录入、方案对比、激活和重规划页面尚未实现。
- PydanticAI 单 Agent、自然语言意图解析与模型评测尚未接入。
- PostgreSQL、Docker 镜像、部署和真实服务监控仍未完成本机验证。
- 当前变更尚未提交、发布或部署。

### 下一步

进入 Stage 3：先实现高德市内路线 Provider 的真实/Fixture 双模式、超时重试、限流、熔断式降级、快照与契约测试；铁路、航班和酒店在缺少稳定官方接口时采用可替换适配器与受控样例，不伪造“已接入 12306”。

## 2026-07-30｜Target v1.0 Stage 3：高德路线 Provider 与受控降级

### 业务目标

让市内转点具备真实路线数据接入能力，同时保证无密钥、超时、部分接口失败或调用量受限时仍能生成可解释方案，并能从 PlanRevision 追溯每条路线的数据来源与失败原因。

### 设计决策

1. 使用高德 Web 服务路径规划 2.0 的 v5 驾车、步行、骑行与公交接口；地址解析使用 v3 地理编码。接口参数和返回结构以[高德官方文档](https://lbs.amap.com/api/webservice/guide/api/newroute)为准。
2. Planner 改为依赖异步 `CandidateProvider` 协议，不依赖具体 Fixture 类；外部 HTTP 不阻塞 FastAPI 事件循环。
3. Beam Search 同层扩展并发执行，Provider 对同一查询做 in-flight 合并和结果缓存；HTTP 并发、重试次数及单次规划的真实调用总量均有上限。
4. 降级粒度是“路线方式”，不是整单：例如出租车成功、步行失败时保留真实出租车候选，只对步行回退 Fixture，快照标记为 `mixed`。
5. 只持久化规范化候选、查询指纹、耗时、状态码和失败类别，不保存高德原始响应，不记录 Key 或带 Key 的完整 URL。
6. 跨城车次、酒店和酒店路线锚点仍为 Fixture；Stage 3 不把局部真实路线包装为整单实时方案。
7. 系统内部时间统一为 UTC，但公交查询的 `date/time` 在请求前按 Mission 时区转换为当地时间。

### 已实现

- `CandidateProvider` 与 `ProviderSnapshotData` 协议。
- `AmapLocalRouteProvider`：v3 地理编码；v5 驾车/出租车、步行、骑行、公交解析。
- `httpx.AsyncClient` 显式超时、可配置的一次重试、有限并发和真实调用预算。
- 坐标与路线查询缓存、并发请求合并，避免 Beam Search 重复消耗配额。
- API 错误、HTTP 429/5xx、超时、传输异常、缺少 citycode、空结果、无 Key 和预算耗尽的分类失败。
- 按方式回退 `FixtureCandidateProvider`，在候选 metadata、方案 warning 和 ProviderSnapshot 中写入 `fallback_reason`。
- PlanRevision 同时引用 planning candidates 快照与 local routes 快照。
- `/api/health` 和 `/api/ready` 暴露非敏感的路线模式与 Key 配置状态。

### 验证结果

- 后端：`24 passed`。
- 高德契约测试：解析官方 v5 形状的驾车/出租车、步行和公交响应，验证 citycode、出发时间、费用/耗时/换乘次数与查询去重。
- 故障测试：超时重试一次后降级、部分接口失败产生 mixed 来源、无 Key 零网络降级、调用预算耗尽停止远程扩张。
- 端到端测试：`LOCAL_ROUTE_PROVIDER=amap` 且无 Key 时仍生成计划，并持久化高德失败类别和 Fixture 来源快照。
- 本阶段没有可用真实 Key，因此未向高德公网发送真实业务请求；“实时路况已验证”仍不是已完成事实。

### 当前限制

- 高德真实密钥、配额和生产网络尚未实测，当前证据是官方响应契约的 MockTransport 测试。
- 骑行与步行共用 v5 基础路径解析逻辑，但尚未增加独立骑行响应样例。
- Fixture 跨城交通使用通用“目的城市东站”作为路线锚点，真实铁路/航班 Provider 接入后必须由具体班次提供准确枢纽。
- 酒店候选仍为 Fixture，其路线锚点复用任务地点；不能表述为真实酒店推荐。
- ProviderSnapshot 为一次规划内的聚合快照，尚未实现跨请求缓存、熔断器状态共享或历史数据重放接口。
- v1 前端尚未展示 live/mixed/fixture 来源、失败原因和快照详情。
- PostgreSQL、Docker 与公网部署仍未完成验证。
- 当前变更尚未提交、发布或部署。

### 下一步

先用个人高德 Web 服务 Key 做一组最小真实请求验收，并保存脱敏证据；随后进入 Stage 4，用单个 PydanticAI Agent 只负责自然语言 Mission 草稿与工具调用决策，Planner、PolicyEngine 和 Verifier 继续保持确定性。

## 2026-07-30｜Target v1.0 Stage 4A：单 Agent 自然语言入口

### 已实现

- 单个 `FieldPilotMissionInterpreter`，职责仅为自然语言到 `MissionDraft` 的语义转换；不提供数据库、Provider、文件、HTTP 或预订工具。
- PydanticAI `Agent` 严格 `output_type=AgentMissionOutput`，通过 OpenAI-compatible 异步客户端预留 Kimi/其他兼容模型。
- 模型请求上限、Token 总量上限、客户端超时和一次 SDK 重试。
- 确定性后处理器独立检查路线基本信息、任务时窗和报销政策，最多生成三项合并澄清，不信任模型自行声称“完整”。
- 无密钥 Mock 提取器支持固定演示语法；真实模式无 Key 或运行异常时返回 `fallback`、失败类别和澄清结果。
- Prompt Injection 类文本标记；Agent 工具数固定为 0，用户文字不能触发外部动作。
- `POST /api/v1/agent/interpret-mission` 及前端镜像类型。

### 验证结果

- 后端：`29 passed`。
- 新增覆盖完整草稿提取、最多三项澄清、注入文本标记、PydanticAI `TestModel` 结构化输出和 live 模式缺 Key 降级。
- 测试全局设置 `ALLOW_MODEL_REQUESTS=False`，避免 CI 或本地回归意外产生真实模型费用。
- 当前无 LLM Key，未完成 Kimi/OpenAI-compatible 真实模型质量与 Token/延迟复验。

### 当前限制

- 本阶段是 Stage 4A：尚未实现自然语言变更解析、计划解释、白名单应用工具和对话历史。
- Agent Trace 随响应返回但尚未持久化；`request_id` 已进入契约，尚未实现解释请求幂等记录。
- Mock 提取器只支持固定、公开的演示语法，不冒充通用中文理解能力。
- v1 前端尚未接入自然语言输入与草稿确认页面。

### 下一步

Stage 4B：增加 AgentRun/DecisionTrace 持久化与请求幂等，建立版本化固定数据集和字段提取评测脚本；获得 LLM Key 后再做真实模型 A/B，不用 Mock 指标替代模型指标。

## 2026-07-30｜Target v1.0 Stage 4B：Agent 审计与固定评测

- 新增 `agent_runs` 表和 Alembic `20260730_0002`，保存 request/trace、输入 SHA-256 指纹、Prompt/模型/模式、结构化输出、Token/请求数、延迟和失败类别；不保存自由文本原文。
- 相同 `request_id + 输入` 返回同一 trace 并标记幂等重放；相同 request_id 对应不同输入返回 `409 agent_request_conflict`。
- 新增 `GET /api/v1/agent/runs/{trace_id}`。
- 新增版本化固定集 `mission-interpret-v1`、评测脚本和基线报告，覆盖完整任务、三类缺失与 Prompt Injection。
- 当前 deterministic Mock 的 5 个固定场景四项精确指标均为 1.00；该结果只作为规则回归，不作为真实 LLM 指标。
- 后端全量测试：`32 passed`；迁移 head 为 `20260730_0002`。

下一步进入 Stage 5：先让受支持的 ReplanEvent 安全应用到 Mission facts，再生成带 `input_event_id` 的计划修订和结构化 revision diff。

## 2026-07-30｜Target v1.0 Stage 5：事件应用与可解释重规划

- ReplanEvent 增加 `application_status / changed_fields / applied_at`，事件 ID 重放必须同时匹配任务、类型、基线和 payload。
- 任务改期/取消/新增/延长、预算和交通偏好在同一数据库事务内更新 Mission facts，并保存 before/after；locked/completed task 拒绝变更。
- 天气和交通中断在尚未进入候选过滤器前只记录为 `recorded_only`，不冒充已经影响规划。
- PlanGenerationRequest 增加 `input_event_id`，验证事件属于当前 Mission 且基线一致；同一 request_id 对应不同参数返回冲突。
- 新增 Revision Diff，按稳定任务/候选身份输出 added/removed/changed、保持段数、成本/评分与告警差异。
- 专项接口测试覆盖事实应用、严格幂等、recorded-only、事件关联修订、未知事件和 diff。

## 2026-07-30｜Target v1.0 Stage 6：v1 工作台与交付配置

- Vue 页面升级为“自然语言输入 -> Agent 草案/澄清 -> Mission -> 三方案比较 -> 来源/政策 -> 事件重规划 -> Revision Diff”的完整工作台。
- 页面展示 Agent trace、模型/Prompt/耗时、segment provider/source mode、ProviderSnapshot ID 和 Fixture 警告。
- 新增 PostgreSQL Compose、Nginx 反向代理、API migration-on-start 与 GitHub Actions 后端/迁移/前端验证流程。
- 本阶段验证：`38 passed`；Alembic `upgrade head / check / downgrade 20260730_0002 / upgrade head` 通过；前端 TypeScript 与 Vite 生产构建通过；`git diff --check` 通过。
- 本机没有 Docker CLI，因此 Compose 和镜像只完成配置审查，不能写成已实际运行；真实高德和模型 Key 仍未测试。

## 2026-07-31｜Stage 7：真实浏览器验收与演示交付

- 按正式本地端口启动 FastAPI 8000 与 Vite，直接 health/ready、Vite API 代理和 localhost CORS 均通过。
- 在真实浏览器完成健康检查、自然语言解析、R1 生成/激活、任务改期、R2 生成/激活和 Revision Diff；固定场景显示 5 处变化、8 段保持。
- 浏览器控制台无 warning/error；首屏 1440px 截图加入 README。
- 新增 `scripts/smoke_workflow.py`，可对运行中 API 重复执行完整 v1 HTTP 主链路并输出结构化摘要。
- 新增五分钟演示手册与发布验收清单，明确已验证、仅配置和需要外部凭证的三类状态。
- 运行中冒烟发现相同业务输入重建后 Fixture 费用会因随机 mission/task ID 改变；将查询指纹、路线种子和候选 ID 改为基于地点/日期等业务字段，并新增跨 Mission ID 稳定性测试。连续两次完整冒烟的 R1/R2 费用均为 571 元。
- Stage 7 完成后后端全量测试为 `39 passed`。

## 2026-07-31｜Stage 8：周边餐饮候选与逐日餐补闭环

- 新增 `MealCandidate / MealType` 领域契约和 `CandidateProvider.nearby_meals` 端口，餐饮不是写死的每日常量，而是带锚点、餐次、人均费用、距离、评分、来源和候选 ID 的规划输入。
- Fixture 以地点语义生成稳定候选与查询指纹；缓存键额外包含当前任务/酒店锚点，避免等价地点复用时串用其他 Mission 的引用。
- 高德适配按官方搜索 POI 2.0 契约调用 `GET /v5/place/around`，使用餐饮类型 `050000`、距离排序和 `show_fields=business`；只接收包含人均消费且不超过剩余餐补的 POI，缺价、超价、无结果或调用失败时记录原因并降级。
- Planner 在现有任务缓冲或住宿时间中安排早/午/晚餐，不移动任务和交通骨架；紧密行程优先距离和用时，灵活行程优先费用，无法安排的餐次返回日期级告警。
- Policy Engine 按任务时区聚合每日餐饮费用；Verifier 独立复查餐次唯一性、候选、就近锚点、餐次时间窗、分类费用和政策结论。住宿和缓冲是可叠加背景区间，交通、任务和餐次仍禁止互相重叠。
- ProviderSnapshot 分开保存 `planning_candidates`、`local_routes` 和 `meal_candidates` 的查询指纹、归一化候选、来源与安全 HTTP 事件摘要，不保存 Key、完整 URL 或原始响应。
- Vue 工作台新增四类费用明细和餐饮时间线节点；Fixture 页脚和告警明确不代表实时餐饮报价。

### 验证结果

- 后端全量：`42 passed`；新增高德餐饮预算过滤/查询去重、无价格结果诚实降级、餐饮快照、跨 Mission ID 稳定性和 Verifier 餐饮锚点篡改覆盖。
- 前端：`vue-tsc --noEmit && vite build` 通过，版本升级为 `0.3.0-dev`。
- 连续两次运行中 HTTP 冒烟均通过：R1/R2 均为 710 元，R1 餐饮 148 元，R2 包含 4 个餐次、2 份 ProviderSnapshot；事件应用、修订差异与来源模式保持稳定。
- 真实浏览器重新完成 health → interpret → R1 → event → R2 → diff，页面展示 4 个餐次和跨城/市内/住宿/餐饮四类费用，重规划为 8 处变化、9 段保持，控制台无 warning/error。
- 浏览器前置检查发现 Vite 将 `/api` 代理到 `localhost:8000` 时在当前 Windows 环境命中错误监听端；改为 `127.0.0.1:8000` 后开发代理健康检查恢复，避免 IPv4/IPv6 解析差异造成假故障。
- 本机仍无真实高德 Key；POI 证据来自官方响应契约的 MockTransport 和无 Key Fixture 链路，不能表述为实时餐厅推荐已上线。

## 2026-07-31｜Stage 9：执行检查点与严格后缀重规划

- 新增 `ExecutionCheckpoint` 与 `ExecutionCommand` 持久化模型和 Alembic `20260731_0004`。检查点保存来源修订、锁定/完成边界及受保护段；命令使用指纹保证相同 command ID 可重放、不同负载冲突，并以版本号进行乐观并发控制。
- 新增执行状态查询与推进 API。锁定/完成边界只能沿激活首选方案单调向前，完成不得越过锁定位置；任务记录同步更新 locked/completed，最终任务完成后 Mission 进入 completed。
- Planner 升级为 `bounded-beam-v3`：从检查点结束时间、位置、住宿与累计成本等状态恢复，移除受保护任务，只求解后续任务、交通、住宿与餐饮。Verifier 升级为 `plan-verifier-v3`，逐段校验受保护前缀一致，并拒绝缺失恢复段或越过检查点的后缀。
- Vue 工作台展示 V0/V1/V2 执行检查点、planned/locked/completed 状态和“锁定至此/完成至此”操作；已锁定或完成任务不会再进入事件重规划选择器。

### 验证结果

- 后端全量 `46 passed`，覆盖锁定与完成的单调推进、严格幂等、过期版本冲突、command ID 冲突、受保护任务拒绝修改、R2 前缀逐字段一致和 Verifier 篡改拦截。
- Alembic `upgrade head / check / downgrade 20260730_0003 / upgrade head` 通过，最终 head 为 `20260731_0004`；前端 `vue-tsc --noEmit && vite build` 通过，版本升级为 `0.4.0-dev`。
- 运行中 HTTP 冒烟通过：R1/R2 均为 710 元，保护 5 个前缀段，`protected_prefix_unchanged=true`，执行版本推进到 2，来源模式保持 `fixture + manual`。
- 真实浏览器完成 interpret → R1 → lock V1 → 第二任务改期 → R2 → complete V2。页面显示 6 处变化、11 段保持，已完成任务禁用，浏览器控制台无 warning/error。
