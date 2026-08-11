# FieldPilot 简历与面试事实口径

## 项目标题

**FieldPilot｜报销约束驱动的跨城外勤任务编排 Agent（个人项目）**
PydanticAI、FastAPI、Pydantic v2、SQLAlchemy/Alembic、Vue 3/TypeScript、httpx、PostgreSQL/SQLite

## 可用于简历的描述

- 针对本人跨省市外勤中交通、住宿、多工作点时窗与报销规则分散的问题，设计“类型化语义 Agent Harness + 确定性编排内核”：用严格契约、有界模型调用、确定性后置校验、幂等与运行审计管理自然语言入口，避免 LLM 编造车次、价格和合规结论。
- 实现异步 Candidate Provider 与有界 Beam Search，融合跨城交通、住宿和市内路线候选，Policy Engine 过滤席别/舱位及费用上限，Verifier 独立复算任务覆盖、时间冲突、分类成本和政策不变量，输出最多 3 个带评分明细的可解释方案。
- 封装高德地理编码与 v5 路径规划适配器，加入显式超时、有限重试/并发/调用预算、查询缓存、in-flight 去重和按路线方式降级；通过 ProviderSnapshot 与 `live/mixed/fixture` 标记保留来源和失败证据。
- 建立 Mission/PlanRevision/ReplanEvent/ExecutionCheckpoint/AgentRun 与不可变政策版本持久化，以输入指纹、命令幂等、乐观并发和严格前缀保护实现检查点后的后缀重规划；本地 `0.6.0` 完成 55 项后端回归，上一版已部署 Render Docker/FastAPI、Neon PostgreSQL 与 Netlify 工作台。
- 建立 15 场景版本化 Kimi K2.6 Live Eval，覆盖完整/缺失输入、精确报销字段、任务时窗和 Prompt Injection；依据失败样本重算澄清与安全标签，最终 15/15 live、状态/安全 100%、字段 94.87%、澄清 93.33%，且 fallback 不计入模型指标。

篇幅受限时，保留 Harness、确定性规划/校验和真实 Eval 三条，把部署与测试数合并到项目链接或面试讲解中。

## 60 秒讲法

FieldPilot 来自我真实跨省市出差时反复遇到的痛点：工作地点有时间窗，交通、酒店和餐饮分散在不同平台，公司又有报销上限，临时改期后很难快速确认整条行程仍可执行。我没有让大模型直接生成行程，而是让一个 PydanticAI Agent 只做口语到严格任务草案的转换；确认后由 Provider 层拿候选，确定性 Planner 做有界搜索，Policy Engine 算报销规则，再由独立 Verifier 复算不变量。计划和候选来源都会存成版本。现场改期时，事件在同一事务里修改事实，新计划引用事件，并输出前后成本、评分和行程段差异。Kimi K2.6 独立真实评测与无密钥 Fixture 全链路已经验证；Render Docker/FastAPI、Neon PostgreSQL 和 Netlify 工作台已经上线。公开环境仍明确使用 Mock LLM/Fixture，不把它描述为实时库存或生产 SLA。

## 高频追问

**为什么是 Agent，不是普通表单？**
Agent Harness 负责从不完整口语中抽取多类约束并生成最少澄清问题，同时限制模型调用预算、重算关键标签并记录可审计 trace；可执行计划必须经过用户确认、确定性 Provider/Planner/Policy/Verifier 和状态化修订。Agent 的价值在管理语言不确定性，而不是替代计算。

**为什么不用 CrewAI/LlamaIndex？**
这里只有一个必要的语义角色，没有多角色协商；也没有文档知识库。状态恢复由数据库完成，规划由确定性算法完成，引入两者会增加依赖却不解决新问题。

**为什么不是 OR-Tools？**
当前上限只有 6 个任务和少量候选，有界 Beam Search 更易解释和调试。规模、复杂资源约束或最优性要求增长后，再以固定场景对照 OR-Tools。

**为什么没有让 Agent 调用工具或引入 MCP？**
当前唯一需要模型推理的是语义抽取，工具数固定为 0，避免用户文本直接触发外部网络或副作用。Provider 只由本后端消费，类型化 Python 端口已能更直接地治理超时、预算、缓存、来源和降级；等同一只读能力需要跨多个 Agent 客户端复用时再引入 MCP。

**12306 是否已接入？**
没有。铁路/航班/酒店使用明确 Fixture，或由用户通过严格 Schema 导入授权候选；不调用或抓取未授权内部接口。高德适配已做契约和故障测试并提供脱敏验收工作流，真实 Key 尚未验收。

## 暂时不能写

- “真实高德/Kimi/12306 已在线上工作台运行”或“实时库存准确”；Kimi 只在独立 Live Eval 中验证。
- “全局最优”“所有天气/延误自动处置”；可写“检查点后的严格后缀重规划”。
- “生产级稳定性/SLA/多租户隔离”——当前验证的是免费层公网闭环、重启恢复和精确 CORS，不等于生产流量验证。
- CrewAI、LlamaIndex、RAG、MCP、SSE、HITL、自动预订。
- Mock 固定集的 1.00 指标作为真实模型准确率。
