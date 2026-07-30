<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { FieldTaskPlan } from "../types/field";
import TargetMap from "./TargetMap.vue";

const props = defineProps<{ plan: FieldTaskPlan }>();
const emit = defineEmits<{ reset: [] }>();

function clonePlan(plan: FieldTaskPlan): FieldTaskPlan {
  return JSON.parse(JSON.stringify(plan)) as FieldTaskPlan;
}

const workingPlan = ref(clonePlan(props.plan));
const savedPlan = ref(clonePlan(props.plan));
const editMode = ref(false);
watch(
  () => props.plan,
  (plan) => {
    workingPlan.value = clonePlan(plan);
    savedPlan.value = clonePlan(plan);
  }
);

const targets = computed(() => workingPlan.value.days.flatMap((day) => day.targets));
const costItems = computed(() => [
  ["点位执行", workingPlan.value.costs.target_operations],
  ["驻点费用", workingPlan.value.costs.lodging],
  ["餐食补贴", workingPlan.value.costs.meals],
  ["市内交通", workingPlan.value.costs.transportation]
]);

function startEdit() {
  savedPlan.value = clonePlan(workingPlan.value);
  editMode.value = true;
}

function saveEdit() {
  editMode.value = false;
  savedPlan.value = clonePlan(workingPlan.value);
  sessionStorage.setItem("fieldPilotPlan", JSON.stringify(workingPlan.value));
}

function cancelEdit() {
  workingPlan.value = clonePlan(savedPlan.value);
  editMode.value = false;
}

function moveTarget(dayIndex: number, targetIndex: number, direction: -1 | 1) {
  const dayTargets = workingPlan.value.days[dayIndex].targets;
  const nextIndex = targetIndex + direction;
  if (nextIndex < 0 || nextIndex >= dayTargets.length) return;
  [dayTargets[targetIndex], dayTargets[nextIndex]] = [dayTargets[nextIndex], dayTargets[targetIndex]];
}

function removeTarget(dayIndex: number, targetIndex: number) {
  workingPlan.value.days[dayIndex].targets.splice(targetIndex, 1);
}

function exportText() {
  const plan = workingPlan.value;
  const lines = [
    `FieldPilot 外勤执行方案 ${plan.task_id}`,
    `${plan.city}｜${plan.start_date} 至 ${plan.end_date}`,
    `行业：${plan.industry}`,
    `目标：${plan.objective}`,
    "",
    plan.overview,
    ""
  ];
  plan.days.forEach((day) => {
    lines.push(`第 ${day.day_index} 天 ${day.date}｜风险：${day.risk_level}`, day.summary);
    day.targets.forEach((target, index) => {
      lines.push(`${index + 1}. ${target.name}｜${target.address}`, `   ${target.task_brief}`);
    });
    lines.push(`交通：${day.transport_guidance}`, "");
  });
  lines.push(`计划成本：${plan.costs.planned_total} 元 / 预算：${plan.costs.budget_limit} 元`);
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `FieldPilot-${plan.task_id}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function printPlan() {
  window.print();
}
</script>

<template>
  <section class="result-stack">
    <div class="result-hero">
      <div>
        <span class="result-label">TASK {{ workingPlan.task_id }}</span>
        <h2>{{ workingPlan.city }} · {{ workingPlan.industry }}</h2>
        <p>{{ workingPlan.overview }}</p>
      </div>
      <div class="result-actions">
        <button v-if="!editMode" class="primary" @click="startEdit">调整任务顺序</button>
        <button v-if="editMode" class="primary" @click="saveEdit">保存调整</button>
        <button v-if="editMode" class="secondary" @click="cancelEdit">取消</button>
        <button class="secondary" @click="exportText">导出文本</button>
        <button class="secondary" @click="printPlan">打印 PDF</button>
        <button class="ghost" @click="emit('reset')">新建任务</button>
      </div>
    </div>

    <div v-if="workingPlan.warnings.length" class="warning-list">
      <p v-for="warning in workingPlan.warnings" :key="warning">{{ warning }}</p>
    </div>

    <div class="metric-grid">
      <article>
        <span>执行周期</span><strong>{{ workingPlan.days.length }} 天</strong>
      </article>
      <article><span>目标点位</span><strong>{{ targets.length }} 个</strong></article>
      <article>
        <span>计划成本</span><strong>{{ workingPlan.costs.planned_total }} 元</strong>
      </article>
      <article>
        <span>预算余量</span>
        <strong :class="{ over: workingPlan.costs.remaining < 0 }">
          {{ workingPlan.costs.remaining }} 元
        </strong>
      </article>
    </div>

    <section class="content-card map-section">
      <div class="section-heading compact"><span>02 / 点位分布</span><h3>目标点位与执行驻点</h3></div>
      <TargetMap :targets="targets" :fallback-image-url="workingPlan.map_image_url" />
      <div class="base-note">
        <strong>{{ workingPlan.operation_base.name }}</strong>
        <p>{{ workingPlan.operation_base.rationale }}</p>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading compact"><span>03 / 风险证据</span><h3>每日环境与执行风险</h3></div>
      <div class="risk-grid">
        <article v-for="risk in workingPlan.risks" :key="risk.date" :class="`risk-${risk.level}`">
          <div><strong>{{ risk.date }}</strong><span>{{ risk.level }}</span></div>
          <p>{{ risk.weather_summary }}</p>
          <p>{{ risk.execution_risk }}</p>
          <small>{{ risk.mitigation }}</small>
        </article>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading compact"><span>04 / 执行编排</span><h3>每日不重复点位任务</h3></div>
      <div class="day-list">
        <article v-for="(day, dayIndex) in workingPlan.days" :key="day.day_index" class="day-card">
          <header>
            <div><span>DAY {{ String(day.day_index).padStart(2, '0') }}</span><h4>{{ day.date }}</h4></div>
            <span :class="`risk-pill risk-${day.risk_level}`">{{ day.risk_level }}</span>
          </header>
          <p>{{ day.summary }}</p>
          <div class="target-list">
            <article v-for="(target, targetIndex) in day.targets" :key="target.target_id">
              <div class="target-index">{{ targetIndex + 1 }}</div>
              <div>
                <h5>{{ target.name }}</h5>
                <p>{{ target.category }} · {{ target.address }}</p>
                <small>{{ target.task_brief }}</small>
              </div>
              <div v-if="editMode" class="target-actions">
                <button :disabled="targetIndex === 0" @click="moveTarget(dayIndex, targetIndex, -1)">↑</button>
                <button :disabled="targetIndex === day.targets.length - 1" @click="moveTarget(dayIndex, targetIndex, 1)">↓</button>
                <button @click="removeTarget(dayIndex, targetIndex)">×</button>
              </div>
            </article>
          </div>
          <footer><strong>交通</strong>{{ day.transport_guidance }}</footer>
        </article>
      </div>
    </section>

    <section class="two-column">
      <div class="content-card">
        <div class="section-heading compact"><span>05 / 成本</span><h3>执行成本拆分</h3></div>
        <dl class="cost-list">
          <div v-for="item in costItems" :key="String(item[0])"><dt>{{ item[0] }}</dt><dd>{{ item[1] }} 元</dd></div>
          <div class="cost-total"><dt>计划合计</dt><dd>{{ workingPlan.costs.planned_total }} 元</dd></div>
        </dl>
      </div>
      <div class="content-card">
        <div class="section-heading compact"><span>06 / 可观测</span><h3>工具调用状态</h3></div>
        <ul class="tool-list">
          <li v-for="tool in workingPlan.tool_statuses" :key="tool.tool">
            <span :class="`tool-${tool.status}`">{{ tool.status }}</span>
            <div><strong>{{ tool.tool }}</strong><p>{{ tool.detail }} · {{ tool.elapsed_ms }}ms</p></div>
          </li>
        </ul>
      </div>
    </section>
  </section>
</template>
