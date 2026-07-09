<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";

import { checkHealth, generateTripPlan } from "../services/api";
import type { TripPlanRequest } from "../types";

const router = useRouter();

const formData = ref<TripPlanRequest>({
  destination: "上海",
  start_date: "",
  end_date: "",
  preferences: "第一次去，喜欢历史文化和轻松路线，不想太赶。",
  budget: 3000,
  transport_type: "public_transport",
  accommodation_type: "comfort"
});

const loading = ref(false);
const loadingProgress = ref(0);
const loadingStatus = ref("");
const backendStatus = ref("未检测");
const errorMessage = ref("");
let progressTimer: number | undefined;

function updateLoadingStatus() {
  if (loadingProgress.value <= 30) {
    loadingStatus.value = "正在搜索景点...";
  } else if (loadingProgress.value <= 50) {
    loadingStatus.value = "正在查询天气...";
  } else if (loadingProgress.value <= 70) {
    loadingStatus.value = "正在推荐酒店...";
  } else {
    loadingStatus.value = "正在生成行程规划...";
  }
}

function startProgress() {
  loadingProgress.value = 0;
  updateLoadingStatus();
  progressTimer = window.setInterval(() => {
    if (loadingProgress.value < 90) {
      loadingProgress.value += 10;
      updateLoadingStatus();
    }
  }, 500);
}

function stopProgress() {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = undefined;
  }
}

async function handleSubmit() {
  errorMessage.value = "";
  loading.value = true;
  startProgress();

  try {
    const tripPlan = await generateTripPlan(formData.value);
    loadingProgress.value = 100;
    loadingStatus.value = "规划完成";
    sessionStorage.setItem("tripPlan", JSON.stringify(tripPlan));
    await router.push({ name: "result" });
  } catch (error) {
    errorMessage.value = "生成规划失败，请确认后端服务已经启动，或稍后重试。";
  } finally {
    stopProgress();
    loading.value = false;
  }
}

async function testBackend() {
  backendStatus.value = "检测中...";
  try {
    const result = await checkHealth();
    backendStatus.value = result.status;
  } catch (error) {
    backendStatus.value = "后端暂未连接";
  }
}

onBeforeUnmount(stopProgress);
</script>

<template>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">智能旅行助手</p>
      <h1>规划你的下一段行程</h1>
      <p class="description">
        填写目的地、日期、偏好、预算、交通和住宿类型，系统会调用 Tavily、高德、Unsplash 和
        Kimi，生成真实数据驱动的旅行计划。
      </p>
    </section>

    <section class="panel">
      <h2>旅行需求表单</h2>
      <form @submit.prevent="handleSubmit">
        <div class="form-grid">
          <label>
            目的地城市
            <input v-model="formData.destination" required placeholder="如：上海" />
          </label>
          <label>
            开始日期
            <input v-model="formData.start_date" required type="date" />
          </label>
          <label>
            结束日期
            <input v-model="formData.end_date" required type="date" />
          </label>
          <label>
            预算
            <input v-model.number="formData.budget" required type="number" min="0" />
          </label>
          <label>
            交通类型
            <select v-model="formData.transport_type">
              <option value="public_transport">公共交通</option>
              <option value="taxi">打车为主</option>
              <option value="walking">步行为主</option>
            </select>
          </label>
          <label>
            住宿类型
            <select v-model="formData.accommodation_type">
              <option value="budget">经济型</option>
              <option value="comfort">舒适型</option>
              <option value="premium">高品质</option>
            </select>
          </label>
        </div>

        <label class="wide">
          旅行偏好
          <textarea v-model="formData.preferences" rows="4" />
        </label>

        <div v-if="loading" class="progress-box">
          <div class="progress-track">
            <div class="progress-bar" :style="{ width: `${loadingProgress}%` }" />
          </div>
          <p>{{ loadingStatus }} {{ loadingProgress }}%</p>
        </div>

        <div class="actions">
          <button type="submit" :disabled="loading">
            {{ loading ? "规划中..." : "开始规划" }}
          </button>
          <button type="button" class="secondary" @click="testBackend">检测后端</button>
        </div>

        <p class="status">后端状态：{{ backendStatus }}</p>
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </form>
    </section>
  </main>
</template>
