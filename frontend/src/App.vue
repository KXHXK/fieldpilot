<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";

import FieldPlanResult from "./components/FieldPlanResult.vue";
import FieldTaskForm from "./components/FieldTaskForm.vue";
import { checkHealth, createFieldTaskPlan } from "./services/api";
import type { FieldTaskPlan, FieldTaskRequest } from "./types/field";

const cached = sessionStorage.getItem("fieldPilotPlan");
const plan = ref<FieldTaskPlan | null>(cached ? JSON.parse(cached) : null);
const loading = ref(false);
const progress = ref(0);
const loadingStatus = ref("");
const notice = ref("");
const error = ref("");
let timer: number | undefined;

const stages = [
  "正在校验任务边界",
  "正在并行收集点位与环境信息",
  "正在选择执行驻点",
  "正在生成不重复的每日任务",
  "正在汇总成本与降级状态"
];

function startProgress() {
  progress.value = 8;
  loadingStatus.value = stages[0];
  timer = window.setInterval(() => {
    progress.value = Math.min(progress.value + 9, 89);
    loadingStatus.value = stages[Math.min(Math.floor(progress.value / 20), stages.length - 1)];
  }, 450);
}

function stopProgress() {
  if (timer) window.clearInterval(timer);
  timer = undefined;
}

async function submit(request: FieldTaskRequest) {
  loading.value = true;
  error.value = "";
  notice.value = "";
  startProgress();
  try {
    plan.value = await createFieldTaskPlan(request);
    progress.value = 100;
    loadingStatus.value = "执行方案已生成";
    sessionStorage.setItem("fieldPilotPlan", JSON.stringify(plan.value));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "生成失败，请稍后重试";
  } finally {
    stopProgress();
    loading.value = false;
  }
}

async function health() {
  notice.value = "正在检查服务…";
  error.value = "";
  try {
    const response = await checkHealth();
    notice.value = `服务状态：${response.status}`;
  } catch (reason) {
    notice.value = "";
    error.value = reason instanceof Error ? reason.message : "服务暂不可用";
  }
}

function reset() {
  plan.value = null;
  sessionStorage.removeItem("fieldPilotPlan");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

onBeforeUnmount(stopProgress);
</script>

<template>
  <main>
    <header class="topbar">
      <a class="brand" href="#"><span>FP</span><strong>FieldPilot</strong></a>
      <div><span class="live-dot" />Hybrid Agent Workflow · MVP 0.1</div>
    </header>

    <template v-if="!plan">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">CITY FIELD OPERATIONS</p>
          <h1>把分散的线下目标，<br /><em>编排成可执行任务。</em></h1>
          <p class="hero-description">
            FieldPilot 将城市、点位、环境风险、预算和执行目标整理成每日方案；
            确定性工具负责事实与成本，模型仅用于受约束的语义总结。
          </p>
          <div class="capability-row">
            <span>点位去重</span><span>环境风险</span><span>任务编排</span><span>失败降级</span>
          </div>
        </div>
        <aside class="flow-card">
          <span>COORDINATOR FLOW</span>
          <ol>
            <li><i>01</i><div><strong>Target Discovery</strong><small>点位搜索、清洗、去重</small></div></li>
            <li><i>02</i><div><strong>Field Risk</strong><small>天气证据与执行风险</small></div></li>
            <li><i>03</i><div><strong>Base Location</strong><small>驻点建议与成本边界</small></div></li>
            <li><i>04</i><div><strong>Task Planning</strong><small>每日不重复任务分配</small></div></li>
          </ol>
        </aside>
      </section>

      <FieldTaskForm :loading="loading" :progress="progress" :status="loadingStatus" @submit="submit" @health="health" />
      <p v-if="notice" class="notice success">{{ notice }}</p>
      <p v-if="error" class="notice error">{{ error }}</p>
    </template>

    <FieldPlanResult v-else :plan="plan" @reset="reset" />

    <footer class="page-footer">
      <span>FieldPilot · 可复现外勤编排 MVP</span>
      <span>示例数据不代表实时商业事实</span>
    </footer>
  </main>
</template>
