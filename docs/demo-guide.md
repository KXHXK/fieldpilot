# FieldPilot 五分钟演示与面试讲解

## 演示前准备

后端首次运行：

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\backend
Copy-Item .env.example .env
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe run.py
```

前端另开终端：

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\frontend
npm run dev
```

访问 Vite 实际打印的地址。若 5173 被 WSL 或其他程序占用，Vite 会自动选择 5174；后端仍应使用 8000，因为开发代理默认指向该端口。

也可以先执行运行中 HTTP 冒烟：

```powershell
cd D:\CODEX\agent-portfolio\fieldpilot\backend
.\.venv\Scripts\python.exe scripts\smoke_workflow.py
```

## 五分钟主线

### 1. 说明真实问题（30 秒）

我经常跨省市出差，人工需要在交通、住宿、多个任务时间窗和公司报销规则之间来回核对。FieldPilot 的目标不是自动下单，而是生成可执行、可追溯、途中可调整的方案。

### 2. 展示 Agent 边界（45 秒）

点击“解析任务”。指出：

- Agent 只生成严格 MissionDraft 或最多三项澄清问题；
- Trace 展示 mode、prompt version 和 latency；
- 工具数为 0，模型不能访问数据库、地图、文件或预订接口；
- Mock 会明确显示，不能当作真实模型效果。

### 3. 展示确定性规划（90 秒）

点击“确认草案并生成方案”。依次讲：

- 最多三个可解释候选，而不是模型自由写一段行程；
- 时间线包含跨城、转点、任务、住宿、工作点/酒店附近餐次、缓冲和返程；
- Policy Engine 判断席别、住宿、市内交通、餐补和总预算；
- Verifier 独立复算任务覆盖、时间重叠、分类成本和政策不变量；
- 每个 segment 保留 provider 与 `source_mode`，Fixture 不冒充实时数据。

### 4. 展示执行检查点与后缀重规划（90 秒）

在首个现场任务点击“锁定至此”，再把第二个任务改为 10:00–12:00，点击“应用事件并重规划”。最后回到首个现场任务点击“完成至此”。指出：

- 检查点从 V0 → V1 → V2 单调推进，重复 command ID 可安全重放，过期版本会返回冲突；
- 已锁定任务不能再选择修改，R2 逐段保留检查点前的交通、缓冲、餐饮和任务内容；
- Planner 从锁定段结束时间与位置恢复，只求解后缀，Verifier 独立拒绝前缀篡改或越界后缀；
- 事件先在事务内修改 Mission facts，并保存 before/after；
- R2 显式引用 `input_event_id`，激活时使用 expected revision 防止覆盖新版本；
- Diff 展示新增、删除、变化和保留路段，以及成本、评分和告警增量。

本地 2026-07-31 浏览器验收中，该场景产生 R1 → R2、6 处变化、11 段保持、成本不变；执行检查点推进到 V2，控制台无 warning/error。具体数字来自固定 Fixture，只用于回归演示。

### 5. 主动说明边界（45 秒）

- 高德适配完成契约与故障测试，但尚未使用真实 Key 验收；
- 铁路、航班和酒店当前是冻结 Fixture/Provider Port，未抓取 12306；
- 天气和交通中断目前只 `recorded_only`，尚未进入候选过滤；
- 已实现受保护前缀不变的后缀重规划，但 Planner 仍是有界启发式搜索，不声称全局最优；
- Docker/PostgreSQL 配置已提供，本机尚无 Docker CLI 运行证据。

## 面试官追问时打开的材料

- 架构：[`architecture.md`](architecture.md)
- 事实口径：[`resume-project-description.md`](resume-project-description.md)
- 开发取舍和故障记录：[`development-log.md`](development-log.md)
- Agent 固定集：[`evals/mission-interpret-v1-baseline.md`](evals/mission-interpret-v1-baseline.md)
- 后续边界：[`roadmap.md`](roadmap.md)
