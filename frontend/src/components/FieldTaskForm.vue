<script setup lang="ts">
import { reactive, ref } from "vue";

import type { FieldTaskRequest } from "../types/field";

defineProps<{ loading: boolean; progress: number; status: string }>();
const emit = defineEmits<{ submit: [request: FieldTaskRequest]; health: [] }>();

const targetTypesText = ref("新能源汽车品牌门店、核心商圈");
const form = reactive({
  city: "上海",
  start_date: "2026-08-01",
  end_date: "2026-08-03",
  industry: "新能源汽车",
  objective: "调研品牌门店分布与周边竞品",
  budget: 3000,
  transport_type: "public_transport" as FieldTaskRequest["transport_type"],
  base_preference: "靠近地铁，便于覆盖多个商圈"
});

function submit() {
  const targetTypes = targetTypesText.value
    .split(/[、,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
  emit("submit", { ...form, target_place_types: targetTypes });
}
</script>

<template>
  <section class="form-card">
    <div class="section-heading">
      <span>01 / 任务输入</span>
      <h2>建立外勤任务边界</h2>
      <p>结构化输入会先经过校验，再交给专职 Agent 与确定性工具编排。</p>
    </div>

    <form @submit.prevent="submit">
      <div class="form-grid">
        <label>
          执行城市
          <input v-model="form.city" required maxlength="40" />
        </label>
        <label>
          行业方向
          <input v-model="form.industry" required maxlength="80" />
        </label>
        <label>
          开始日期
          <input v-model="form.start_date" required type="date" />
        </label>
        <label>
          结束日期
          <input v-model="form.end_date" required type="date" />
        </label>
        <label class="wide">
          目标场所类型（使用顿号或逗号分隔）
          <input v-model="targetTypesText" required />
        </label>
        <label class="wide">
          任务目标
          <textarea v-model="form.objective" required rows="3" maxlength="500" />
        </label>
        <label>
          预算上限（元）
          <input v-model.number="form.budget" required type="number" min="1" max="100000" />
        </label>
        <label>
          交通方式
          <select v-model="form.transport_type">
            <option value="public_transport">公共交通</option>
            <option value="taxi">网约车</option>
            <option value="walking">步行优先</option>
          </select>
        </label>
        <label class="wide">
          驻点偏好
          <input v-model="form.base_preference" maxlength="200" />
        </label>
      </div>

      <div v-if="loading" class="progress" aria-live="polite">
        <div class="progress-track"><div :style="{ width: `${progress}%` }" /></div>
        <span>{{ status }} · {{ progress }}%</span>
      </div>

      <div class="form-actions">
        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? "正在编排" : "生成执行方案" }}
        </button>
        <button class="secondary" type="button" :disabled="loading" @click="emit('health')">
          检查服务
        </button>
      </div>
    </form>
  </section>
</template>
