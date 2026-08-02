# FieldPilot 0.5.0-dev 发布验收清单

验收日期：2026-08-02

验收分支：`agent/public-workbench`

已知稳定回滚点：`bc53426`（首个已验证 Render 生产部署）

## 已验证

- [x] 无 `.env`、Key、依赖目录或构建目录进入 Git。
- [x] SQLite + Alembic `20260731_0004` 升降级和 schema check。
- [x] 51 项 Pytest，包含执行检查点单调推进/幂等/并发冲突、严格前缀保留、Verifier 篡改拦截、Neon URL 归一化、Kimi K2.6 非思考结构化输出、确定性澄清/安全标签与显式日期归一化，以及自然语言到事件式 R2 的 API E2E。
- [x] 删除旧 `/api/field-task/plan`、旧多 Agent、旧模型/服务和未使用前端组件；回归测试固定旧接口返回 404。
- [x] 15 场景独立 live 数据集、三次重复、延迟/Token/稳定率指标及 OpenAI-compatible 手动工作流；fallback 不进入 live 得分。
- [x] 时间线生成工作点/酒店附近餐次，按自然日核算餐补；候选、失败原因和来源写入 ProviderSnapshot。
- [x] 锁定/完成操作更新任务执行态；重规划从检查点恢复，首选 R2 对受保护段保持逐字段一致。
- [x] Vue TypeScript 检查与 Vite production build。
- [x] 实际进程 `/api/health`、`/api/ready` 返回成功。
- [x] Vite `/api` 代理到正式后端端口 8000。
- [x] `Origin: http://localhost:5173` 获得正确 CORS 响应。
- [x] 真实浏览器完成 interpret → R1 → lock V1 → event → R2 → complete V2 → diff。
- [x] 浏览器控制台无 warning/error。
- [x] Fixture、manual、mock 状态在页面明确显示。
- [x] 根路径使用 `showcase` 项目专题，`/workbench` 连接实际公网后端；Mock/Fixture 来源在 UI 明确标记。
- [x] 专题页桌面/移动端无横向溢出，R1/R2 时间线切换有效，浏览器控制台无 warning/error。
- [x] Neon `fieldpilot` 数据库执行 Alembic 至 `20260731_0004 (head)`，并通过独立就绪查询。
- [x] Kimi K2.6 完成 15 场景真实评测：15/15 live、无 fallback；最终全量 run 的状态/安全标签准确率 100%，字段 94.87%，澄清 93.33%。

## 已配置但未验证

- [x] Docker 镜像已由 Render 云端构建并运行；本地 PostgreSQL Compose/Nginx 仍因本机没有 Docker CLI 未实跑。
- [x] Render Free Blueprint、Neon PostgreSQL URL 归一化、migration-on-start、`/api/ready` 和生产 CORS 配置。
- [x] 独立 FastAPI/PostgreSQL 公网后端：Render Docker/FastAPI 已连接 Neon，并通过完整 smoke、CORS 和重启恢复验证。

## 远端验证

- [x] GitHub Actions `verify`：后端测试、Alembic schema check 与前端构建通过。
- [x] Netlify 项目站与在线工作台：<https://fieldpilot-kxh.netlify.app/>、<https://fieldpilot-kxh.netlify.app/workbench>。
- [x] 生产 deploy `6a6f13259646109fe6f02be6`：根路径、工作台、SPA 回退、JS/CSS CDN、CSP 与真实浏览器 Agent 解析通过。
- [x] Render API：<https://fieldpilot-api-t7m6.onrender.com/api/health>；初始生产 commit `bc53426`。
- [x] GitHub Actions live eval run `30687086569`：15/15 Kimi K2.6 调用为 live，artifact 已下载核验。

## 需要外部凭证

- [ ] 使用个人高德 Web Service Key 做最小真实地理编码、路线和周边餐饮 POI 验收。
- [x] 配置 `FIELD_PILOT_LLM_API_KEY` 与供应商 variables，运行 `fieldpilot-live-agent-eval`，下载与 Mock 分开的真实模型报告并记录 run URL/commit。
- [ ] 如果需要交互地图，单独配置公开的 Web JS Key 与安全码。

## 公网后端发布验收

- [x] 后端 HTTPS `/api/health` 和 `/api/ready` 返回 200。
- [x] CORS 只允许实际前端 origin，随机预览 origin 被拒绝。
- [x] 前端 `VITE_API_BASE_URL` 指向正确 HTTPS 后端并重新构建。
- [x] 云端 migration 完成；Render 重启后 revision、event 和执行检查点仍存在。
- [x] health、完整 smoke 与公网真实浏览器链路通过；没有消耗真实 Provider 配额。
- [x] README 记录已验证事实、初始部署 commit 与 Netlify deploy。
