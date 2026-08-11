# FieldPilot 0.6.0 发布验收清单

验收日期：2026-08-10

发布候选分支：`release/fieldpilot-closure-20260810`

发布前稳定回滚点：`134d436`（当前 `main`，上一版公网项目站与后端已验证）

## 本地已验证

- [x] 工作区基线变更已保留在独立发布分支，没有删除用户已有的前端可读性与运行边界改进。
- [x] 无 `.env`、Key、依赖目录、构建目录或评测 artifact 进入 Git。
- [x] 后端 55 项 Pytest 全部通过。
- [x] Alembic `20260810_0005` 完成 upgrade、schema check、downgrade 到 `20260731_0004` 与重新 upgrade。
- [x] 不可变报销政策版本链：预算事件追加新快照，旧投影不覆盖，计划保存 `policy_snapshot_id`。
- [x] 交通中断候选过滤：取消/不可用排除候选，延误平移时间并降低可靠性，过滤证据进入 ProviderSnapshot。
- [x] 天气风险候选过滤：高风险过滤受影响任务的步行和骑行，中风险过滤骑行，过滤证据可审计。
- [x] 授权人工库存导入：铁路、航班和酒店使用严格 JSON Schema，强制 `manual` 来源并保存 SHA-256 内容指纹。
- [x] Vue 工作台支持任务改期、预算变化、交通中断和天气风险四类可演示事件，并展示政策快照版本。
- [x] Vue TypeScript 检查、工作台 Vite production build 与 `showcase` production build 均通过。
- [x] CI 同时构建工作台与实际 Netlify 使用的 showcase 模式。
- [x] 高德真实服务验收脚本与手动 GitHub Actions 工作流已提供；报告不保存 Key、带 Key URL 或原始响应。
- [x] 本地真实 HTTP 进程完成 R1→R5 smoke：任务改期、预算快照、交通取消和天气风险均为 `applied`，政策快照绑定正确、受影响候选被排除、检查点前缀保持不变。

## 既有真实模型证据

- [x] Kimi K2.6 固定 15 场景最终轮为 15/15 Live、无 fallback。
- [x] 最终轮状态与安全标签准确率 100%，选定字段精确率 94.87%，澄清字段精确率 93.33%，P50/P95 为 16.91/26.92 秒。
- [x] 三轮数据来自三个代码版本，每个版本每场景调用一次；不把它表述为同一版本三次重复，也不声明跨重复稳定率。
- [x] Live Eval 与 Mock 数据集、指标和 artifact 分离；任何 fallback 都会让 Live 工作流失败。

## 上一版公网已验证

- [x] Netlify 项目站与工作台：<https://fieldpilot-kxh.netlify.app/>、<https://fieldpilot-kxh.netlify.app/workbench>。
- [x] 2026-08-10 只读复核：Netlify 两个入口均返回 200；Render health/ready 可用并明确报告当前线上仍为 `0.5.0-dev`、Mock LLM 与 Fixture Provider。
- [x] 当前生产 deploy `6a6f2177f207a9dccf2184db` 已验证根路径、工作台、SPA 回退、JS/CSS CDN、CSP 与浏览器主链路。
- [x] Render API：<https://fieldpilot-api-t7m6.onrender.com/api/health>；health/ready、精确 CORS、完整 R1/R2 smoke 和重启恢复均通过。
- [x] Neon PostgreSQL 上一版已迁移到 `20260731_0004`，数据在 Render 重启后仍可读取。

## 需要人工审批或外部凭证

- [ ] 审查并合并 `release/fieldpilot-closure-20260810` 到 `main`，触发 GitHub Actions、Render 和 Netlify 生产发布。
- [ ] 确认 Neon 生产迁移到 `20260810_0005`，再验证 `/api/ready`、完整 R1/R2、四类事件和重启恢复。
- [ ] 确认 Netlify 生产页显示 `0.6.0`、55 项测试口径、运行边界和新事件工作台。
- [ ] 配置 GitHub secret `FIELD_PILOT_AMAP_API_KEY`，手动运行 `fieldpilot-amap-provider-validation` 并保存脱敏报告。
- [ ] 只有需要浏览器交互地图时才配置独立 Web JS Key 与安全码；后端 Web Service Key 不得进入前端。

## 发布后验收命令

```powershell
Invoke-RestMethod https://fieldpilot-api-t7m6.onrender.com/api/health
Invoke-RestMethod https://fieldpilot-api-t7m6.onrender.com/api/ready

cd D:\CODEX\agent-portfolio\fieldpilot\backend
.\.venv\Scripts\python.exe scripts\smoke_workflow.py `
  --base-url https://fieldpilot-api-t7m6.onrender.com/api
```

生产发布未完成前，只能说“0.6.0 发布候选已本地验收”，不能把新迁移和新事件过滤写成已在公网验证。
