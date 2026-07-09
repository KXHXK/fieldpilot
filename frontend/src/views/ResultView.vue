<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import TripMap from "../components/TripMap.vue";
import type { TripPlan } from "../types";

type SectionId = "overview" | "budget" | "map" | "weather" | "days";

const router = useRouter();

const cachedTripPlan = sessionStorage.getItem("tripPlan");
const tripPlan = ref<TripPlan | null>(cachedTripPlan ? JSON.parse(cachedTripPlan) : null);

const editMode = ref(false);
const originalPlan = ref<TripPlan | null>(null);
const activeSection = ref<SectionId>("overview");

const navigationItems: Array<{ id: SectionId; label: string }> = [
  { id: "overview", label: "行程概览" },
  { id: "budget", label: "预算明细" },
  { id: "map", label: "景点地图" },
  { id: "weather", label: "天气信息" },
  { id: "days", label: "每日行程" }
];

const totalAttractions = computed(() => {
  if (!tripPlan.value) {
    return 0;
  }
  return tripPlan.value.days.reduce((total, day) => total + day.attractions.length, 0);
});

const budgetItems = computed(() => {
  const budget = tripPlan.value?.budget;
  if (!budget) {
    return [];
  }
  return [
    { label: "景点门票", value: budget.total_attractions },
    { label: "酒店住宿", value: budget.total_hotels },
    { label: "餐饮费用", value: budget.total_meals },
    { label: "交通费用", value: budget.total_transportation }
  ];
});

const mapPoints = computed(() => {
  if (!tripPlan.value) {
    return [];
  }

  return tripPlan.value.days.flatMap((day) =>
    day.attractions.map((attraction, index) => ({
      key: `${day.day_index}-${index}-${attraction.name}`,
      dayIndex: day.day_index,
      name: attraction.name,
      address: attraction.address,
      latitude: attraction.location?.latitude,
      longitude: attraction.location?.longitude,
      imageUrl: attraction.image_url
    }))
  );
});

function clonePlan(plan: TripPlan): TripPlan {
  return JSON.parse(JSON.stringify(plan)) as TripPlan;
}

function persistPlan() {
  if (tripPlan.value) {
    sessionStorage.setItem("tripPlan", JSON.stringify(tripPlan.value));
  }
}

function goHome() {
  router.push({ name: "home" });
}

function scrollToSection(id: SectionId) {
  activeSection.value = id;
  document.getElementById(id)?.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

function startEdit() {
  if (!tripPlan.value) {
    return;
  }
  originalPlan.value = clonePlan(tripPlan.value);
  editMode.value = true;
}

function saveChanges() {
  editMode.value = false;
  originalPlan.value = null;
  persistPlan();
}

function cancelEdit() {
  if (originalPlan.value) {
    tripPlan.value = clonePlan(originalPlan.value);
  }
  editMode.value = false;
  originalPlan.value = null;
}

function moveAttraction(dayIndex: number, attractionIndex: number, direction: "up" | "down") {
  const attractions = tripPlan.value?.days[dayIndex]?.attractions;
  if (!attractions) {
    return;
  }

  const nextIndex = direction === "up" ? attractionIndex - 1 : attractionIndex + 1;
  if (nextIndex < 0 || nextIndex >= attractions.length) {
    return;
  }

  [attractions[attractionIndex], attractions[nextIndex]] = [
    attractions[nextIndex],
    attractions[attractionIndex]
  ];
}

function deleteAttraction(dayIndex: number, attractionIndex: number) {
  tripPlan.value?.days[dayIndex]?.attractions.splice(attractionIndex, 1);
}

function buildExportText() {
  if (!tripPlan.value) {
    return "";
  }

  const lines = [
    `${tripPlan.value.city}旅行计划`,
    `${tripPlan.value.start_date} 至 ${tripPlan.value.end_date}`,
    "",
    "行程概览",
    tripPlan.value.overall_suggestions,
    ""
  ];

  if (tripPlan.value.budget) {
    lines.push(
      "预算明细",
      `景点门票：${tripPlan.value.budget.total_attractions} 元`,
      `酒店住宿：${tripPlan.value.budget.total_hotels} 元`,
      `餐饮费用：${tripPlan.value.budget.total_meals} 元`,
      `交通费用：${tripPlan.value.budget.total_transportation} 元`,
      `总费用：${tripPlan.value.budget.total} 元`,
      ""
    );
  }

  tripPlan.value.days.forEach((day) => {
    lines.push(`第 ${day.day_index} 天：${day.date}`, day.description);
    lines.push(`交通建议：${day.transportation}`);
    lines.push(`住宿建议：${day.accommodation}`);
    day.attractions.forEach((attraction, index) => {
      lines.push(`${index + 1}. ${attraction.name}：${attraction.description}`);
    });
    lines.push("");
  });

  return lines.join("\n");
}

function exportAsText() {
  const content = buildExportText();
  if (!tripPlan.value || !content) {
    return;
  }

  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${tripPlan.value.city}旅行计划.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function printAsPdf() {
  window.print();
}
</script>

<template>
  <main class="page result-page">
    <section class="hero">
      <p class="eyebrow">智能旅行助手</p>
      <h1>{{ tripPlan?.city || "旅行计划" }}</h1>
      <p v-if="tripPlan" class="description">
        {{ tripPlan.start_date }} 至 {{ tripPlan.end_date }}，共 {{ tripPlan.days.length }} 天，
        包含 {{ totalAttractions }} 个景点。
      </p>
    </section>

    <section v-if="!tripPlan" class="panel empty-state">
      <h2>还没有旅行计划</h2>
      <p>请先回到首页填写旅行需求并生成计划。</p>
      <button type="button" @click="goHome">返回首页</button>
    </section>

    <template v-else>
      <div class="result-layout">
        <aside class="side-nav">
          <button
            v-for="item in navigationItems"
            :key="item.id"
            type="button"
            :class="{ active: activeSection === item.id }"
            @click="scrollToSection(item.id)"
          >
            {{ item.label }}
          </button>
        </aside>

        <div id="trip-plan-content" class="result-content">
          <section id="overview" class="panel summary-grid">
            <div>
              <h2>行程概览</h2>
              <p>{{ tripPlan.overall_suggestions }}</p>
            </div>
            <div class="overview-actions">
              <button v-if="!editMode" type="button" @click="startEdit">编辑行程</button>
              <button v-if="editMode" type="button" @click="saveChanges">保存修改</button>
              <button v-if="editMode" type="button" class="secondary" @click="cancelEdit">
                取消编辑
              </button>
              <button type="button" class="secondary" @click="exportAsText">导出文本</button>
              <button type="button" class="secondary" @click="printAsPdf">打印为 PDF</button>
            </div>
          </section>

          <section id="budget" v-if="tripPlan.budget" class="panel">
            <h2>预算明细</h2>
            <div class="stat-grid">
              <article v-for="item in budgetItems" :key="item.label" class="stat-card">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }} 元</strong>
              </article>
            </div>
            <div class="total-budget">
              <span>预计总费用</span>
              <strong>{{ tripPlan.budget.total }} 元</strong>
            </div>
          </section>

          <section id="map" class="panel">
            <h2>景点地图</h2>
            <TripMap :points="mapPoints" :fallback-image-url="tripPlan.map_image_url" />
          </section>

          <section id="weather" class="panel">
            <h2>天气信息</h2>
            <div class="weather-grid">
              <article v-for="weather in tripPlan.weather_info" :key="weather.date" class="weather-card">
                <strong>{{ weather.date }}</strong>
                <p>白天：{{ weather.day_weather }}，{{ weather.day_temp }}℃</p>
                <p>夜间：{{ weather.night_weather }}，{{ weather.night_temp }}℃</p>
                <p>{{ weather.wind_direction }} {{ weather.wind_power }}</p>
              </article>
            </div>
          </section>

          <section id="days" class="panel">
            <h2>每日行程详情</h2>
            <article v-for="(day, dayIndex) in tripPlan.days" :key="day.day_index" class="day-card">
              <h3>第 {{ day.day_index }} 天：{{ day.date }}</h3>
              <p>{{ day.description }}</p>
              <p><strong>交通建议：</strong>{{ day.transportation }}</p>
              <p><strong>住宿建议：</strong>{{ day.accommodation }}</p>

              <div class="attraction-grid">
                <article
                  v-for="(attraction, attractionIndex) in day.attractions"
                  :key="`${day.day_index}-${attraction.name}`"
                  class="attraction-card"
                >
                  <img v-if="attraction.image_url" :src="attraction.image_url" :alt="attraction.name" />
                  <div>
                    <h4>{{ attraction.name }}</h4>
                    <p>{{ attraction.description }}</p>
                    <p>{{ attraction.address }}</p>
                    <p v-if="attraction.ticket_price">门票：{{ attraction.ticket_price }} 元</p>
                    <div v-if="editMode" class="edit-buttons">
                      <button
                        type="button"
                        class="small"
                        :disabled="attractionIndex === 0"
                        @click="moveAttraction(dayIndex, attractionIndex, 'up')"
                      >
                        上移
                      </button>
                      <button
                        type="button"
                        class="small"
                        :disabled="attractionIndex === day.attractions.length - 1"
                        @click="moveAttraction(dayIndex, attractionIndex, 'down')"
                      >
                        下移
                      </button>
                      <button
                        type="button"
                        class="small danger"
                        @click="deleteAttraction(dayIndex, attractionIndex)"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </article>
          </section>
        </div>
      </div>

      <div class="actions result-actions">
        <button type="button" @click="goHome">重新规划</button>
      </div>
    </template>
  </main>
</template>
