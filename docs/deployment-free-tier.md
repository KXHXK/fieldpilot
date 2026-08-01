# FieldPilot 零成本公网部署

## 目标拓扑

```text
Netlify 静态专题  ->  Render FastAPI  ->  Neon PostgreSQL
fieldpilot-kxh        fieldpilot-api       fieldpilot database
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

随后用 `backend/scripts/smoke_workflow.py --base-url <URL>`（脚本支持该参数后）跑完整写入链路，并在 Render 手动重启后读取既有 Mission/Revision/Event，证明数据不依赖临时文件系统。最后发送 `Origin: https://fieldpilot-kxh.netlify.app` 请求，确认仅该生产 origin 获得 CORS 响应。

## 当前状态

截至 2026-08-01，Neon 项目和独立 `fieldpilot` 数据库已创建，四段 Alembic migration 已执行到 `20260731_0004 (head)`，并通过 `SELECT 1` 就绪查询。代码侧 Blueprint、Neon URL 归一化、migration-on-start、健康/就绪探针和 CORS 已准备。Render CLI 的 device-grant 请求在当前网络持续超时，应用内 Render 控制台尚未登录，因此仍没有公网 API URL，也不把“已配置”写成“已部署”。
