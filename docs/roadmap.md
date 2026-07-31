# FieldPilot 后续迭代边界

## P0：交付验收

- 在具备 Docker 的环境运行 PostgreSQL Compose，验证 migration、ready probe、Nginx 代理、数据持久化与重启恢复。
- 用独立高德 Web Service Key 执行最小真实路线验收，保存脱敏快照；用模型 Key 跑 `mission-interpret-v1` 固定集，生成与 Mock 分开的延迟、Token、失败率和字段指标。
- [已完成] 增加浏览器主链路验收与工作台截图，并发布独立静态专题地址；不复用智能旅游助手域名。完整可写公网后端仍未部署。

## P1：补齐核心业务

- [已完成] 增加高德周边餐饮 POI/Fixture 候选、时间线餐次和逐日餐补核算；缺价或失败时保留来源与降级证据。
- 为铁路/航班/酒店实现授权 Provider 或人工候选导入，不抓取 12306 内部接口。
- 让 transport disruption/weather risk 真正过滤候选；在此之前保持 `recorded_only`。
- [已完成] 引入 segment lock 与执行进度，严格保留 completed/locked 前缀，只重新求解受影响后缀；命令重放与并发冲突已有接口测试。
- 政策改为不可变快照历史，而不是在事件审计保护下更新当前快照行。

## P2：达到真实规模后再引入

- OR-Tools：当任务/候选数量和资源约束使 Beam Search 质量或耗时不再满足固定集时。
- Pydantic Evals：当需要模型/Prompt/数据集实验矩阵和持续报告，而当前脚本难以维护时。
- LlamaIndex/RAG：当用户真的上传多份 SOP、报销文档或现场证据，并需要引用定位时。
- CrewAI Flows：仅当出现多个必要的长时自治角色、可恢复分支与人工节点；当前数据库状态机足够。
- Redis/队列/SSE：当真实调用超过同步请求预算，需后台作业、取消和进度流时。

## 明确不做

自动支付、购票、订房、叫车、提交报销；绕过平台授权；虚构生产客户、并发量、准确率或节省比例。
