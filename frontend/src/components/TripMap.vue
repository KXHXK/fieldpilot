<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

interface TripMapPoint {
  key: string;
  dayIndex: number;
  name: string;
  address: string;
  latitude?: number | null;
  longitude?: number | null;
  imageUrl?: string | null;
}

const props = defineProps<{
  points: TripMapPoint[];
  fallbackImageUrl?: string | null;
}>();

declare global {
  interface Window {
    AMap?: any;
  }
}

const mapContainer = ref<HTMLDivElement | null>(null);
const mapInstance = ref<any>(null);
const markerList = ref<any[]>([]);
const routeLine = ref<any>(null);
const loadError = ref("");

const amapKey = import.meta.env.VITE_AMAP_JS_KEY as string | undefined;

const validPoints = computed(() =>
  props.points.filter((point) => point.longitude != null && point.latitude != null)
);

function clearOverlays() {
  if (!mapInstance.value) {
    return;
  }

  markerList.value.forEach((marker) => {
    mapInstance.value.remove(marker);
  });
  markerList.value = [];

  if (routeLine.value) {
    mapInstance.value.remove(routeLine.value);
    routeLine.value = null;
  }
}

function renderMarkers() {
  if (!window.AMap || !mapInstance.value) {
    return;
  }

  clearOverlays();

  const sorted = [...validPoints.value].sort((a, b) => a.dayIndex - b.dayIndex);
  const bounds: [number, number][] = [];
  const routePath: [number, number][] = [];

  sorted.forEach((point, index) => {
    const position: [number, number] = [point.longitude as number, point.latitude as number];
    bounds.push(position);
    routePath.push(position);

    const marker = new window.AMap.Marker({
      position,
      title: point.name,
      offset: new window.AMap.Pixel(-12, -32),
      content: `
        <div class="amap-point-marker">
          <span>${index + 1}</span>
        </div>
      `,
    });

    const imageHtml = point.imageUrl
      ? `<img src="${point.imageUrl}" alt="${point.name}" />`
      : `<div class="amap-point-card__empty">暂无图片</div>`;

    const card = new window.AMap.Marker({
      position,
      offset: new window.AMap.Pixel(16, -56),
      zIndex: 100,
      content: `
        <div class="amap-point-card">
          <div class="amap-point-card__image">${imageHtml}</div>
          <div class="amap-point-card__body">
            <strong>D${point.dayIndex} ${point.name}</strong>
            <span>${point.address || ""}</span>
          </div>
        </div>
      `,
    });

    mapInstance.value.add(marker);
    mapInstance.value.add(card);
    markerList.value.push(marker, card);
  });

  if (routePath.length >= 2) {
    routeLine.value = new window.AMap.Polyline({
      path: routePath,
      strokeColor: "#4263eb",
      strokeWeight: 4,
      strokeOpacity: 0.8,
      strokeStyle: "dashed",
      lineJoin: "round",
      lineCap: "round",
      showDir: true,
    });
    mapInstance.value.add(routeLine.value);
  }

  if (bounds.length === 1) {
    mapInstance.value.setZoomAndCenter(13, bounds[0]);
  } else if (bounds.length > 1) {
    mapInstance.value.setFitView(markerList.value, false, [70, 70, 70, 70]);
  }
}

function ensureMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve();
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-amap-loader="true"]'
    );
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("高德地图脚本加载失败。")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${amapKey}`;
    script.async = true;
    script.defer = true;
    script.dataset.amapLoader = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("高德地图脚本加载失败。"));
    document.head.appendChild(script);
  });
}

async function initMap() {
  if (!amapKey) {
    loadError.value = "未配置前端高德 JavaScript Key，当前展示后端静态地图。";
    return;
  }

  if (!mapContainer.value || validPoints.value.length === 0) {
    return;
  }

  try {
    loadError.value = "";
    await ensureMapScript();
    if (!window.AMap) {
      loadError.value = "高德地图对象初始化失败。";
      return;
    }

    mapInstance.value = new window.AMap.Map(mapContainer.value, {
      zoom: 11,
      resizeEnable: true,
      viewMode: "2D",
      mapStyle: "amap://styles/whitesmoke",
    });

    renderMarkers();
  } catch (error) {
    console.error(error);
    loadError.value = "地图加载失败，请检查前端高德 Key 或网络环境。";
  }
}

onMounted(() => {
  void initMap();
});

watch(validPoints, () => {
  if (mapInstance.value) {
    renderMarkers();
  }
});

onBeforeUnmount(() => {
  clearOverlays();
  if (mapInstance.value) {
    mapInstance.value.destroy();
    mapInstance.value = null;
  }
});
</script>

<template>
  <div class="trip-map">
    <div v-if="!amapKey || loadError" class="trip-map__fallback">
      <img
        v-if="fallbackImageUrl"
        class="map-image"
        :src="fallbackImageUrl"
        alt="高德静态地图景点分布"
      />
      <p v-else>{{ loadError || "当前没有可展示的景点坐标。" }}</p>
      <p v-if="loadError" class="trip-map__note">{{ loadError }}</p>
    </div>
    <div v-else-if="validPoints.length === 0" class="trip-map__placeholder">
      当前没有可展示的景点坐标。
    </div>
    <div v-else ref="mapContainer" class="trip-map__canvas"></div>
  </div>
</template>
