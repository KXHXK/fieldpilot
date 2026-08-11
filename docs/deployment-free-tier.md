# FieldPilot 零成本公网部署

## 目标拓扑

```text
Netlify 项目站 + 工作台  ->  Render FastAPI  ->  Neon PostgreSQL
fieldpilot-kxh             fieldpilot-api       fieldpilot database
```

仓库根目录的 `render.yaml` 固定 Singapore、Docker runtime、`/api/ready` 健康检查、生产 CORS 和无密钥 Fixture 模式。`DATABASE_URL` 标记为 `sync: false`，只能在 Render 控制台录入，不能提交到 Git。

## 为什么选择这组免费层

- Render Free Web Service 可运行 Docker Web 服务，代价是空闲休眠、冷启动和临时文件系统；因此业务状态必须进入外部 PostgreSQL。
- Render 自带的 Free PostgreSQL 会在 30 天后到期，不适合作为持续展示数据库。
- Neon Free 提供无需信用卡的托管 PostgreSQL；FieldPilot 使用直接连接串，应用启动时由 Docker CMD 先执行 Alembic migration。
- Netlify 继续承载已有静态专题，不在当前 credits 已耗尽的账号上新建 Netlify Database。

官方边界：

- <https://render.com/docs/free>
- <https://neon.com/pricing>
- <https://render.com/docs/blueprint-spec>

## 首次发布

1. 在 Neon 创建 `fieldpilot` project/database，复制 direct connection string。不要把连接串粘贴到聊天、Issue、Actions log 或仓库文件。
2. 从仓库 Blueprint 创建 Render 服务：<https://dashboard.render.com/blueprint/new?repo=https%3A%2F%2Fgithub.com%2FKXHXK%2Ffieldpilot>。
3. 在 Blueprint 表单中把 `DATABASE_URL` 设为 Neon secret，其他变量使用 `render.yaml` 默认值。
4. 等待 Docker 构建、`alembic upgrade head` 和 Uvicorn 启动完成。
5. 记录实际服务 URL 和 deploy commit，然后运行下列验收。

## 上线验收

```powershell
$apiBase = "https://<actual-render-service>.onrender.com"
Invoke-RestMethod "$apiBase/api/health"
Invoke-RestMethod "$apiBase/api/ready"
```

随后用 `backend/scripts/smoke_workflow.py --base-url <URL>` 跑完整写入链路，并在 Render 手动重启后读取既有 Mission/Revision/Event，证明数据不依赖临时文件系统。最后发送 `Origin: https://fieldpilot-kxh.netlify.app` 请求，确认仅该生产 origin 获得 CORS 响应。

## 当前状态

截至 2026-08-12，三层免费拓扑的 `0.6.0` 已上线：Netlify 项目站与工作台为 <https://fieldpilot-kxh.netlify.app/> 和 `/workbench`，Render API 为 <https://fieldpilot-api-t7m6.onrender.com>，数据进入 Neon `fieldpilot` PostgreSQL。生产合并 commit 为 `c41b51b`，首次 `0.6.0` 验收 deploy 为 `6a7b65c4c0df50fb6e96d2b5`；已完成 health/ready、R1～R5 smoke、政策版本查询、CORS、SPA/CSP、浏览器主链路和冷启动恢复复验。

已取得的上线证据：

- `/api/health` 与 `/api/ready` 均为 HTTPS 200，数据库状态为 reachable，公开环境明确返回 `agent_mode=mock`、`local_route_provider=fixture`。
- 公网 smoke 完成 Mission → R1 → 激活 → 执行检查点 → 任务改期事件 → R2 → Diff，得到 `protected_prefix_unchanged=true`。
- Render 手动重启后，既有 Mission 仍为 active、R1/R2 与执行检查点仍可读取，证明状态不依赖临时文件系统。
- 生产 Netlify origin 获得精确 CORS 许可；随机 Deploy Preview origin 被拒绝。工作台真实浏览器显示 `API ok` 并完成杭州示例 Agent 解析。
- 数据库 owner 凭证在发布后完成轮换，旧凭证失效；仓库、文档和命令输出均不记录连接串。

免费层边界仍然存在：Render 空闲时可能冷启动；公开环境没有多租户认证和生产限流；高德真实 Key 未验收。`0.6.0` 已支持铁路、航班与酒店的授权人工候选导入，但公开环境仍使用显式 Fixture。因此这是可交互工程演示环境，不承担真实预订或生产 SLA。
