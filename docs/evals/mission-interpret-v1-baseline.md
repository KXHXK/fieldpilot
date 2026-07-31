# Mission Interpret v1 基线报告

- 运行日期：2026-07-30
- 数据集：`backend/evals/mission_interpret_v1.json`
- 数据集版本：`mission-interpret-v1`
- 执行模式：`deterministic-mock-v1`
- 场景数：5
- Status Accuracy：1.00
- Selected Field Exact Accuracy：1.00
- Clarification Exact Accuracy：1.00
- Safety Flag Exact Accuracy：1.00
- Live Completion Rate：不适用（Mock 报告为 `null`）
- Stable Case Rate：1.00

运行命令：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\evaluate_agent.py --mode mock
```

## 证据边界

该报告只证明固定语法 Mock、澄清后处理器和安全标记在版本化样例上的确定性回归，不代表真实 LLM 的中文理解质量，也不能写成模型 Field Extraction F1。真实模型必须在独立报告中记录模型名、Prompt 版本、Token、延迟、重复运行波动和失败样例。
