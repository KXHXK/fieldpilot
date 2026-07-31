<script setup lang="ts">
import { computed, ref } from "vue";

import {
  activateRevision,
  advanceExecutionCheckpoint,
  checkHealth,
  createMission,
  createReplanEvent,
  diffRevisions,
  generatePlan,
  getExecutionCheckpoint,
  getMission,
  interpretMission
} from "./services/api";
import type { InterpretMissionResponse, MissionDraft } from "./types/agent";
import type { Mission, MissionCreate, VisitPriority } from "./types/mission";
import type { ExecutionAction, ExecutionCheckpoint, PlanOption, PlanRevision, PlanSegment, RevisionDiff } from "./types/planning";

const exampleText = `2026-08-06从上海虹桥站（上海市闵行区申贵路1500号）出发到杭州，行程很紧，只报高铁二等座。
任务：2026-08-06 13:30-15:30|西湖区客户现场|杭州市西湖区文三路|90分钟；
任务：2026-08-07 09:30-11:30|萧山区交付|杭州市萧山区市心北路|90分钟；
酒店每晚不超过450，餐补每天120，市内交通每天200，总预算1600。`;

const inputText = ref(exampleText);
const interpretation = ref<InterpretMissionResponse | null>(null);
const mission = ref<Mission | null>(null);
const revision = ref<PlanRevision | null>(null);
const diff = ref<RevisionDiff | null>(null);
const execution = ref<ExecutionCheckpoint | null>(null);
const selectedOptionId = ref("");
const loading = ref(false);
const stage = ref("等待输入");
const error = ref("");
const health = ref("未检查");
const replanTaskId = ref("");
const replanStart = ref("");
const replanEnd = ref("");

const selectedOption = computed<PlanOption | null>(() => {
  if (!revision.value) return null;
  return revision.value.bundle.options.find((item) => item.option_id === selectedOptionId.value)
    || revision.value.bundle.options[0];
});

const sourceModes = computed(() => {
  const modes = new Set(selectedOption.value?.segments.map((segment) => segment.source_mode) || []);
  return Array.from(modes);
});

const preferredOptionSelected = computed(
  () => selectedOption.value?.option_id === revision.value?.bundle.preferred_option_id
);

const checkpointableTypes = new Set(["intercity_transport", "local_transport", "visit"]);

function required<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined || value === "") throw new Error(`缺少 ${field}`);
  return value;
}

function missionFromDraft(draft: MissionDraft): MissionCreate {
  return {
    origin: {
      name: required(draft.origin.name, "出发地名称"),
      address: required(draft.origin.address, "出发地地址"),
      city: required(draft.origin.city, "出发城市")
    },
    start_date: required(draft.start_date, "开始日期"),
    end_date: required(draft.end_date, "结束日期"),
    timezone: draft.timezone,
    urgency: draft.urgency,
    visits: draft.visits.map((visit) => ({
      name: required(visit.name, "任务名称"),
      location: {
        name: required(visit.name, "任务地点名称"),
        address: required(visit.address, "任务地址"),
        city: required(visit.city, "任务城市")
      },
      window_start: required(visit.window_start, "任务开始时间"),
      window_end: required(visit.window_end, "任务结束时间"),
      duration_minutes: required(visit.duration_minutes, "任务持续时间"),
      priority: visit.priority as VisitPriority,
      locked: false,
      notes: visit.notes
    })),
    expense_policy: {
      policy_id: draft.expense_policy.policy_id,
      policy_version: draft.expense_policy.policy_version,
      allowed_rail_classes: draft.expense_policy.allowed_rail_classes || [],
      allowed_flight_classes: draft.expense_policy.allowed_flight_classes || [],
      hotel_nightly_cap_yuan: required(draft.expense_policy.hotel_nightly_cap_yuan, "酒店限额"),
      meal_daily_cap_yuan: required(draft.expense_policy.meal_daily_cap_yuan, "餐补限额"),
      local_transport_daily_cap_yuan: required(draft.expense_policy.local_transport_daily_cap_yuan, "市内交通限额"),
      trip_total_cap_yuan: required(draft.expense_policy.trip_total_cap_yuan, "总预算")
    },
    transport_preferences: {
      preferred_intercity_modes: draft.preferred_intercity_modes,
      preferred_local_modes: draft.preferred_local_modes,
      minimum_transfer_minutes: 30,
      allow_early_arrival_day: false
    },
    notes: draft.notes
  };
}

function chinaLocalInput(iso: string): string {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((part) => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

function setReplanDefaults(current: Mission) {
  const task = current.visits.find((item) => item.task_id === replanTaskId.value && !item.locked && !item.completed)
    || current.visits.find((item) => !item.locked && !item.completed)
    || null;
  if (!task) {
    replanTaskId.value = "";
    replanStart.value = "";
    replanEnd.value = "";
    return;
  }
  replanTaskId.value = task.task_id;
  replanStart.value = chinaLocalInput(task.window_start);
  replanEnd.value = chinaLocalInput(task.window_end);
}

async function interpret() {
  loading.value = true;
  error.value = "";
  stage.value = "Agent 正在提取约束";
  try {
    interpretation.value = await interpretMission(inputText.value, "2026-07-30");
    stage.value = interpretation.value.ready_for_submission ? "结构化草案可提交" : "等待补充信息";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "解释失败";
    stage.value = "解释失败";
  } finally {
    loading.value = false;
  }
}

async function createAndPlan() {
  if (!interpretation.value?.ready_for_submission) return;
  loading.value = true;
  error.value = "";
  try {
    stage.value = "固化任务与报销约束";
    mission.value = await createMission(missionFromDraft(interpretation.value.draft));
    stage.value = "候选搜索、约束求解与独立校验";
    revision.value = await generatePlan(mission.value.mission_id, {
      request_id: `plan-${crypto.randomUUID()}`,
      based_on_revision: null
    });
    selectedOptionId.value = revision.value.bundle.preferred_option_id;
    stage.value = "激活首版执行方案";
    await activateRevision(mission.value.mission_id, revision.value.revision, null);
    revision.value.status = "active";
    mission.value.active_revision = revision.value.revision;
    mission.value.status = "active";
    execution.value = await getExecutionCheckpoint(mission.value.mission_id);
    setReplanDefaults(mission.value);
    stage.value = "执行方案已激活";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "规划失败";
    stage.value = "规划失败";
  } finally {
    loading.value = false;
  }
}

async function replan() {
  if (!mission.value?.active_revision || !revision.value) return;
  loading.value = true;
  error.value = "";
  try {
    const basedOn = mission.value.active_revision;
    const eventId = `evt-${crypto.randomUUID()}`;
    stage.value = "应用任务改期并写入事件审计";
    await createReplanEvent(mission.value.mission_id, {
      event_id: eventId,
      event_type: "task_rescheduled",
      based_on_revision: basedOn,
      payload: {
        task_id: replanTaskId.value,
        new_window_start: `${replanStart.value}:00+08:00`,
        new_window_end: `${replanEnd.value}:00+08:00`
      }
    });
    stage.value = "生成事件关联修订";
    const next = await generatePlan(mission.value.mission_id, {
      request_id: `plan-${crypto.randomUUID()}`,
      based_on_revision: basedOn,
      input_event_id: eventId
    });
    diff.value = await diffRevisions(mission.value.mission_id, basedOn, next.revision);
    await activateRevision(mission.value.mission_id, next.revision, basedOn);
    next.status = "active";
    revision.value = next;
    selectedOptionId.value = next.bundle.preferred_option_id;
    mission.value.active_revision = next.revision;
    mission.value.status = "active";
    execution.value = await getExecutionCheckpoint(mission.value.mission_id);
    mission.value = await getMission(mission.value.mission_id);
    setReplanDefaults(mission.value);
    stage.value = "重规划修订已激活";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "重规划失败";
    stage.value = "重规划失败";
  } finally {
    loading.value = false;
  }
}

function executionStatus(segment: PlanSegment): "planned" | "locked" | "completed" {
  const end = new Date(segment.end_at).getTime();
  if (execution.value?.completed_through_at && end <= new Date(execution.value.completed_through_at).getTime()) {
    return "completed";
  }
  if (execution.value?.protected_segment_ids.includes(segment.segment_id)) return "locked";
  return "planned";
}

async function advanceExecution(segment: PlanSegment, action: ExecutionAction) {
  if (!mission.value?.active_revision || !execution.value || !preferredOptionSelected.value) return;
  loading.value = true;
  error.value = "";
  try {
    stage.value = action === "lock_through" ? "固化执行前缀" : "推进完成位置";
    execution.value = await advanceExecutionCheckpoint(mission.value.mission_id, {
      command_id: `exec-${crypto.randomUUID()}`,
      based_on_revision: mission.value.active_revision,
      expected_version: execution.value.version,
      action,
      through_segment_id: segment.segment_id
    });
    mission.value = await getMission(mission.value.mission_id);
    setReplanDefaults(mission.value);
    stage.value = action === "lock_through" ? "执行前缀已锁定" : "完成位置已推进";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "执行状态更新失败";
    stage.value = "执行状态更新失败";
  } finally {
    loading.value = false;
  }
}

async function probeHealth() {
  try { health.value = (await checkHealth()).status; }
  catch { health.value = "unavailable"; }
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(new Date(value));
}

function reset() {
  interpretation.value = null;
  mission.value = null;
  revision.value = null;
  diff.value = null;
  execution.value = null;
  stage.value = "等待输入";
  error.value = "";
}
</script>

<template>
  <main>
    <header class="topbar">
      <a class="brand" href="#" @click.prevent="reset"><span>FP</span><strong>FieldPilot</strong></a>
      <nav><span class="live-dot" />API {{ health }}</nav>
      <button class="text-button" @click="probeHealth">健康检查</button>
    </header>

    <section class="hero compact-hero">
      <div class="hero-copy">
        <p class="eyebrow">FIELD MISSION ORCHESTRATION</p>
        <h1>把出差要求，<br /><em>变成可执行行程。</em></h1>
        <p class="hero-description">自然语言负责收集意图；确定性规划器负责时间窗、交通、住宿、费用和报销合规；每次调整都有事件、版本和差异证据。</p>
      </div>
      <aside class="status-card">
        <span>WORKFLOW STATUS</span><strong>{{ stage }}</strong>
        <div class="step-line"><i :class="{ done: interpretation }" />解释<i :class="{ done: mission }" />建模<i :class="{ done: revision }" />规划<i :class="{ done: diff }" />重规划</div>
        <small>模型不直接调用交通与地图工具，外部事实由受控 Provider 层采集。</small>
      </aside>
    </section>

    <p v-if="error" class="notice error">{{ error }}</p>

    <section v-if="!revision" class="workspace-grid">
      <article class="content-card input-panel">
        <div class="section-heading compact"><span>01 / INPUT</span><h3>描述本次外勤</h3></div>
        <textarea v-model="inputText" rows="10" :disabled="loading" />
        <div class="form-actions">
          <button class="primary" :disabled="loading" @click="interpret">{{ loading ? stage : "解析任务" }}</button>
          <button class="secondary" :disabled="loading" @click="inputText = exampleText">载入杭州示例</button>
        </div>
      </article>

      <article class="content-card evidence-panel">
        <div class="section-heading compact"><span>02 / AGENT OUTPUT</span><h3>结构化草案与追踪</h3></div>
        <div v-if="!interpretation" class="empty-state">提交描述后，这里展示严格 Schema 输出、补充问题和运行追踪。</div>
        <template v-else>
          <div class="trace-row">
            <span :class="`source-${interpretation.trace.mode}`">{{ interpretation.trace.mode }}</span>
            <code>{{ interpretation.trace.trace_id }}</code>
            <small>{{ interpretation.trace.latency_ms.toFixed(1) }} ms · {{ interpretation.trace.prompt_version }}</small>
          </div>
          <div v-if="interpretation.clarifications.length" class="question-list">
            <article v-for="question in interpretation.clarifications" :key="question.field"><strong>{{ question.question }}</strong><small>{{ question.reason }}</small></article>
          </div>
          <template v-else>
            <dl class="draft-summary">
              <div><dt>路线</dt><dd>{{ interpretation.draft.origin.city }} → {{ interpretation.draft.destination_city }}</dd></div>
              <div><dt>日期</dt><dd>{{ interpretation.draft.start_date }} 至 {{ interpretation.draft.end_date }}</dd></div>
              <div><dt>任务</dt><dd>{{ interpretation.draft.visits.length }} 个工作点</dd></div>
              <div><dt>预算</dt><dd>¥{{ interpretation.draft.expense_policy.trip_total_cap_yuan }}</dd></div>
            </dl>
            <ol class="visit-preview"><li v-for="visit in interpretation.draft.visits" :key="String(visit.name)"><strong>{{ visit.name }}</strong><span>{{ visit.address }} · {{ visit.duration_minutes }} 分钟</span></li></ol>
            <button class="primary full" :disabled="loading || !interpretation.ready_for_submission" @click="createAndPlan">确认草案并生成方案</button>
          </template>
        </template>
      </article>
    </section>

    <section v-else class="result-stack">
      <div class="result-hero plan-header">
        <div><span class="result-label">MISSION {{ mission?.mission_id }}</span><h2>{{ mission?.origin.city }} → {{ mission?.visits[0]?.location.city }}</h2><p>修订 R{{ revision.revision }} · {{ revision.status }} · {{ revision.bundle.planner_version }} / {{ revision.bundle.verifier_version }}</p></div>
        <div class="result-actions"><button class="secondary" @click="reset">新建任务</button></div>
      </div>

      <div class="metric-grid">
        <article><span>首选评分</span><strong>{{ selectedOption?.score.total.toFixed(1) }}</strong></article>
        <article><span>计划费用</span><strong>¥{{ selectedOption?.costs.planned_total_yuan }}</strong></article>
        <article><span>预算余量</span><strong>¥{{ selectedOption?.costs.remaining_yuan }}</strong></article>
        <article><span>执行检查点</span><strong>V{{ execution?.version || 0 }}</strong></article>
      </div>

      <div class="option-tabs"><button v-for="option in revision.bundle.options" :key="option.option_id" :class="{ active: selectedOption?.option_id === option.option_id }" @click="selectedOptionId = option.option_id"><strong>{{ option.label }}</strong><span>{{ option.score.total.toFixed(1) }} 分 · ¥{{ option.costs.planned_total_yuan }}</span></button></div>

      <section class="content-card">
        <div class="section-heading compact"><span>03 / EXECUTION TIMELINE</span><h3>{{ selectedOption?.summary }}</h3></div>
        <div class="timeline">
          <article v-for="segment in selectedOption?.segments" :key="segment.segment_id" :class="`execution-${executionStatus(segment)}`">
            <time>{{ formatTime(segment.start_at) }}<small>{{ formatTime(segment.end_at) }}</small></time>
            <i :class="`segment-${segment.segment_type}`" />
            <div><strong>{{ segment.title }}</strong><p>{{ segment.from_ref || "" }}<template v-if="segment.to_ref"> → {{ segment.to_ref }}</template></p><span :class="`source-${segment.source_mode}`">{{ segment.source_mode }}</span><span class="execution-pill">{{ executionStatus(segment) }}</span><small>{{ segment.provider }} · ¥{{ segment.cost_yuan }}</small><div v-if="checkpointableTypes.has(segment.segment_type) && preferredOptionSelected" class="execution-actions"><button v-if="executionStatus(segment) === 'planned'" :disabled="loading" @click="advanceExecution(segment, 'lock_through')">锁定至此</button><button v-else-if="executionStatus(segment) === 'locked'" :disabled="loading" @click="advanceExecution(segment, 'complete_through')">完成至此</button></div></div>
          </article>
        </div>
        <p v-if="!preferredOptionSelected" class="provenance-note">执行位置只绑定当前激活的首选方案；切回推荐方案后可推进检查点。</p>
      </section>

      <section class="two-column">
        <article class="content-card">
          <div class="section-heading compact"><span>04 / POLICY</span><h3>报销规则判定</h3></div>
          <dl v-if="selectedOption" class="v1-cost-ledger">
            <div><dt>跨城交通</dt><dd>¥{{ selectedOption.costs.intercity_transport_yuan }}</dd></div>
            <div><dt>市内交通</dt><dd>¥{{ selectedOption.costs.local_transport_yuan }}</dd></div>
            <div><dt>住宿</dt><dd>¥{{ selectedOption.costs.lodging_yuan }}</dd></div>
            <div><dt>餐饮</dt><dd>¥{{ selectedOption.costs.meals_yuan }}</dd></div>
          </dl>
          <ul class="policy-list"><li v-for="rule in selectedOption?.policy_decisions" :key="rule.rule_id"><span :class="`policy-${rule.status}`">{{ rule.status }}</span><div><strong>{{ rule.explanation }}</strong><small>{{ rule.observed }} / {{ rule.limit }}</small></div></li></ul>
        </article>
        <article class="content-card">
          <div class="section-heading compact"><span>05 / PROVENANCE</span><h3>来源与可复现证据</h3></div>
          <p class="provenance-note">每个行程段保留 provider 与 source_mode；本次数据模式为 {{ sourceModes.join(" + ") }}，候选快照可用于复盘。</p>
          <code v-for="snapshot in revision.bundle.provider_snapshot_ids" :key="snapshot" class="snapshot-id">{{ snapshot }}</code>
          <div v-if="selectedOption?.warnings.length" class="warning-list"><p v-for="warning in selectedOption.warnings" :key="warning">{{ warning }}</p></div>
        </article>
      </section>

      <section class="content-card replan-card">
        <div class="section-heading compact"><span>06 / EVENT-DRIVEN REPLAN</span><h3>现场变更后生成新修订</h3><p>选择任务并调整时间窗。系统先应用事件事实，再生成关联修订和差异，最后通过乐观锁激活。</p></div>
        <div class="replan-form">
          <label>工作任务<select v-model="replanTaskId" @change="mission && setReplanDefaults(mission)"><option v-for="visit in mission?.visits" :key="visit.task_id" :value="visit.task_id" :disabled="visit.locked || visit.completed">{{ visit.name }}{{ visit.completed ? "（已完成）" : visit.locked ? "（已锁定）" : "" }}</option></select></label>
          <label>新开始时间<input v-model="replanStart" type="datetime-local" /></label>
          <label>新结束时间<input v-model="replanEnd" type="datetime-local" /></label>
          <button class="primary" :disabled="loading || !replanTaskId" @click="replan">{{ loading ? stage : "应用事件并重规划" }}</button>
        </div>
        <div v-if="diff" class="diff-panel">
          <div><strong>R{{ diff.from_revision }} → R{{ diff.to_revision }}</strong><span>{{ diff.changes.length }} 处变化 · {{ diff.preserved_segment_count }} 段保持</span></div>
          <div class="diff-metrics"><span>成本 {{ diff.cost_delta_yuan >= 0 ? "+" : "" }}{{ diff.cost_delta_yuan }} 元</span><span>评分 {{ diff.score_delta >= 0 ? "+" : "" }}{{ diff.score_delta }}</span></div>
          <ul><li v-for="change in diff.changes" :key="change.identity"><b>{{ change.change_type }}</b><span>{{ change.after?.title || change.before?.title }}</span><small>{{ change.identity }}</small></li></ul>
        </div>
      </section>
    </section>

    <footer class="page-footer"><span>FieldPilot · Agent + deterministic planner + verifier</span><span>fixture 数据会明确标记，不代表实时票价、库存或餐饮报价</span></footer>
  </main>
</template>
