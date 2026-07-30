from __future__ import annotations

from time import perf_counter

from app.config import settings
from app.models import DailyFieldPlan, FieldTaskRequest, ToolStatus


class SummaryService:
    def summarize(
        self,
        request: FieldTaskRequest,
        days: list[DailyFieldPlan],
    ) -> tuple[str, ToolStatus]:
        started = perf_counter()
        fallback = self._fallback(request, days)
        if settings.use_mock_llm or not settings.openai_api_key:
            return fallback, ToolStatus(
                tool="llm_summary",
                status="mock",
                detail="使用确定性摘要；未调用模型。",
                elapsed_ms=self._elapsed(started),
            )

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=15,
                max_retries=0,
            )
            schedule = "\n".join(
                f"第{day.day_index}天：{', '.join(target.name for target in day.targets)}；风险={day.risk_level}"
                for day in days
            )
            completion = client.chat.completions.create(
                model=settings.model_name,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是城市外勤执行方案审核助手。只能依据给定结构化计划总结，"
                            "不得编造点位、承诺或权威结论。输出一段不超过180字的中文概览。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"城市：{request.city}\n行业：{request.industry}\n"
                            f"目标：{request.objective}\n预算：{request.budget}\n{schedule}"
                        ),
                    },
                ],
            )
            content = completion.choices[0].message.content
            if not content:
                raise RuntimeError("模型返回空摘要")
            return content.strip(), ToolStatus(
                tool="llm_summary",
                status="success",
                detail="模型基于结构化执行计划生成概览。",
                elapsed_ms=self._elapsed(started),
            )
        except Exception as exc:  # provider SDK and network exceptions vary by version
            return fallback, ToolStatus(
                tool="llm_summary",
                status="degraded",
                detail=f"模型摘要不可用，保留完整确定性方案：{type(exc).__name__}",
                elapsed_ms=self._elapsed(started),
            )

    @staticmethod
    def _fallback(request: FieldTaskRequest, days: list[DailyFieldPlan]) -> str:
        target_count = sum(len(day.targets) for day in days)
        risk_days = sum(day.risk_level != "low" for day in days)
        return (
            f"本方案围绕“{request.objective}”在{request.city}编排 {len(days)} 天、"
            f"{target_count} 个不重复点位任务；按区域分日执行，并为 {risk_days} 个"
            "存在环境影响的日期配置缓冲和替代建议。点位与环境信息在出发前仍需人工复核。"
        )

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(round((perf_counter() - started) * 1000), 0)
