# FieldPilot 0.4.0-dev 发布验收清单

验收日期：2026-07-31

分支：`feature/execution-checkpoint-replan`

已知稳定回滚点：`1df9f6c`

## 已验证

- [x] 无 `.env`、Key、依赖目录或构建目录进入 Git。
- [x] SQLite + Alembic `20260731_0004` 升降级和 schema check。
- [x] 46 项 Pytest，包含执行检查点单调推进/幂等/并发冲突、严格前缀保留、Verifier 篡改拦截，以及既有自然语言到事件式 R2 的 API E2E。
- [x] 时间线生成工作点/酒店附近餐次，按自然日核算餐补；候选、失败原因和来源写入 ProviderSnapshot。
- [x] 锁定/完成操作更新任务执行态；重规划从检查点恢复，首选 R2 对受保护段保持逐字段一致。
- [x] Vue TypeScript 检查与 Vite production build。
- [x] 实际进程 `/api/health`、`/api/ready` 返回成功。
- [x] Vite `/api` 代理到正式后端端口 8000。
- [x] `Origin: http://localhost:5173` 获得正确 CORS 响应。
- [x] 真实浏览器完成 interpret → R1 → lock V1 → event → R2 → complete V2 → diff。
- [x] 浏览器控制台无 warning/error。
- [x] Fixture、manual、mock 状态在页面明确显示。

## 已配置但未验证

- [ ] Docker 镜像构建与 PostgreSQL Compose：本机没有 Docker CLI。
- [ ] Netlify 静态前端和独立后端部署：尚未配置生产 URL。

## 远端验证

- [x] GitHub Actions `verify`：后端测试、Alembic schema check 与前端构建通过。

## 需要外部凭证

- [ ] 使用个人高德 Web Service Key 做最小真实地理编码、路线和周边餐饮 POI 验收。
- [ ] 使用独立模型 Key 跑 `mission-interpret-v1`，生成与 Mock 分开的指标。
- [ ] 如果需要交互地图，单独配置公开的 Web JS Key 与安全码。

## 发布前必须再次确认

- [ ] 后端先部署并直接访问 HTTPS `/api/health` 和 `/api/ready`。
- [ ] CORS 只允许实际前端 origin。
- [ ] 前端 `VITE_API_BASE_URL` 指向正确 HTTPS 后端并重新构建。
- [ ] 云端运行 migration，验证重启后 revision 和 event 仍存在。
- [ ] 先跑便宜的 health/smoke，再运行真实 Provider 请求。
- [ ] README 中只保留已验证事实，记录部署 commit 与回滚 commit。
