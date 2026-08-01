# Mission Interpret v1 真实模型评测报告

评测日期：2026-08-01

## 评测边界

- 数据集：`backend/evals/mission_interpret_live_v1.json`
- 数据集版本：`mission-interpret-live-v1`
- 场景数：15
- 模型：`kimi-k2.6`
- Prompt：`mission-interpret-v1`
- 调用入口：GitHub Actions `fieldpilot-live-agent-eval`
- 每轮每场景调用一次；为控制个人试用额度，本次没有执行三次重复，因此不声明跨重复稳定率。

场景覆盖完整单城/多城任务、口语化缺失信息、交通偏好、精确报销额度、任务时窗、铁路限定和 Prompt Injection。只有 `AgentMode.LIVE` 调用进入模型质量指标；任一 fallback 都会使工作流失败。artifact 不保存用户原文、模型自由文本或密钥，只保留结构化判定、模式、模型、延迟、Token 和脱敏失败分类。

## 三轮结果

| 轮次 | Run / Commit | Live 完成率 | 状态准确率 | 选定字段精确率 | 澄清字段精确率 | 安全标签精确率 | P50 / P95 | Token |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 原始真实基线 | [30686423222](https://github.com/KXHXK/fieldpilot/actions/runs/30686423222) / `f586208` | 100% | 53.33% | 94.87% | 0% | 86.67% | 17.92s / 35.19s | 22,984 |
| 确定性护栏后 | [30686753792](https://github.com/KXHXK/fieldpilot/actions/runs/30686753792) / `12bb625` | 100% | 93.33% | 100% | 86.67% | 100% | 20.35s / 35.08s | 22,893 |
| 单一交通方式规则后 | [30687086569](https://github.com/KXHXK/fieldpilot/actions/runs/30687086569) / `b3cec02` | 100% | 100% | 94.87% | 93.33% | 100% | 16.91s / 26.92s | 22,788 |

这些数字是三次不同代码版本、每场景一次调用的迭代证据，不能合并为同一版本的稳定性统计。最终全量轮次没有 fallback；字段波动来自 `missing_route_and_policy` 的任务城市与 `injection_execute_command` 的目的城市漏抽，均未改变需要澄清的状态或触发外部动作。

## Eval 驱动的修正

1. 首轮显示字段抽取基本正确，但模型自行增加无依据的澄清项和安全标签。修正后，LLM 仍只负责类型化语义抽取；澄清分组与安全标签由确定性代码根据 typed draft 和原始输入重新计算。
2. 第二轮暴露完整性规则同时要求铁路与航班等级，导致只允许一种跨城方式的合法政策被误判。规则改为任一跨城方式有明确等级即可，状态准确率升至 100%。
3. 最后一轮仍显示单日期的一日行程可能被模型只填入开始日。代码随后增加显式日期归一化，并由单元测试覆盖；为控制调用额度，没有再次运行整套真实模型评测，因此这里不把该本地修正计入上表指标。
4. 评测器在单次运行时不再输出没有统计意义的 `stable_case_rate=1.0`，而是输出 `null`；后续只有每例至少两次调用时才计算稳定率。

## 可复现方式

在 GitHub 仓库 Actions 中手动运行 `fieldpilot-live-agent-eval`，选择 1 或 3 次重复。模型凭证只从 `FIELD_PILOT_LLM_API_KEY` secret 读取，兼容端点和模型由仓库 variables 固定。成功后下载 `mission-interpret-live-v1` artifact；报告保留 30 天。

若后续需要发布“稳定率”或模型版本对比，应在同一 commit、同一模型与相同数据集上执行每例三次，再单独记录费用、失败样例和结论。
