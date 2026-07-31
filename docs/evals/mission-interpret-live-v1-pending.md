# Mission Interpret v1 真实模型评测

## 评测设计

- 数据集：`backend/evals/mission_interpret_live_v1.json`
- 数据集版本：`mission-interpret-live-v1`
- 场景数：15
- 默认重复次数：3
- 模型：由仓库变量 `FIELD_PILOT_LLM_MODEL` 固定，默认 `kimi-k2.6`
- Prompt：`mission-interpret-v1`
- 运行入口：GitHub Actions `fieldpilot-live-agent-eval`

覆盖完整单城/多城与多任务、口语化缺失信息、交通偏好、精确报销额度、时间窗、只允许铁路和 Prompt Injection。报告分别记录 live completion、字段精确率、澄清问题精确率、安全标记精确率、跨重复稳定率、P50/P95 延迟与 Token 用量。

## 可信边界

- 只有返回 `AgentMode.LIVE` 的调用进入真实模型质量指标；fallback 不参与得分。
- 任一调用降级时工作流失败，不能用 Mock 结果替代 live 报告。
- 工作流只从仓库 secret `FIELD_PILOT_LLM_API_KEY` 读取密钥，并通过 `FIELD_PILOT_LLM_BASE_URL` / `FIELD_PILOT_LLM_MODEL` 固定兼容端点和模型；密钥不写入仓库或 artifact。
- 免费/试用层通常有请求频率限制，脚本默认在 live 调用之间等待 4.2 秒。
- 报告只保存结构化判定、模式、模型、延迟、Token 和失败类别，不保存用户原文或模型自由文本。

## 运行

在 GitHub 仓库 Actions 中手动运行 `fieldpilot-live-agent-eval`，选择每个场景 1 次或 3 次。成功后下载 `mission-interpret-live-v1` artifact，并将指标、run URL、commit SHA 和失败样例分析写入新的已完成报告。

## 当前状态

真实调用尚未成功。2026-07-31 的 GitHub Actions run `30641667031` 对 15 个场景全部返回 410，根因为 GitHub Models 已于 2026-07-30 退役；诊断 run `30642038742` 固定记录了 `github_models_retirement_brownout`，该供应商已从工作流移除。Netlify AI Gateway 本地最小探测返回 403 `mismatched_client_ip`，且生产调用会消耗当前已耗尽的 Netlify credits，因此没有继续调用。工作流和数据集已完成，但在配置独立 OpenAI-compatible secret、出现成功 run 与可下载报告前，本项目仍只声称“真实评测链路已配置”，不声称真实模型质量已经通过。
