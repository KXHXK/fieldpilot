<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { TargetPlace } from "../types/field";

const props = defineProps<{ targets: TargetPlace[]; fallbackImageUrl?: string | null }>();
const mapElement = ref<HTMLDivElement | null>(null);
const mapError = ref("");
let mapInstance: { destroy?: () => void } | null = null;

const jsKey = import.meta.env.VITE_AMAP_JS_KEY as string | undefined;
const securityCode = import.meta.env.VITE_AMAP_JS_SECURITY_CODE as string | undefined;
const hasCoordinates = computed(() => props.targets.length > 0);

async function loadMap() {
  if (!jsKey || !mapElement.value || !hasCoordinates.value) {
    mapError.value = jsKey ? "暂无可绘制点位" : "未配置浏览器地图 Key，显示点位坐标清单。";
    return;
  }
  try {
    const browser = window as unknown as {
      AMap?: new (...args: unknown[]) => unknown;
      _AMapSecurityConfig?: { securityJsCode: string };
    };
    if (securityCode) {
      browser._AMapSecurityConfig = { securityJsCode: securityCode };
    }
    if (!browser.AMap) {
      await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(jsKey)}`;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("地图脚本加载失败"));
        document.head.appendChild(script);
      });
    }
    await nextTick();
    const amap = (window as unknown as { AMap: any }).AMap;
    const markers = props.targets.map(
      (target) =>
        new amap.Marker({
          position: [target.location.longitude, target.location.latitude],
          title: target.name
        })
    );
    mapInstance = new amap.Map(mapElement.value, {
      zoom: 11,
      center: [props.targets[0].location.longitude, props.targets[0].location.latitude]
    });
    (mapInstance as any).add(markers);
    (mapInstance as any).setFitView(markers);
  } catch (error) {
    mapError.value = error instanceof Error ? error.message : "地图暂不可用";
  }
}

watch(() => props.targets, loadMap, { deep: true });
onMounted(loadMap);
onBeforeUnmount(() => mapInstance?.destroy?.());
</script>

<template>
  <div class="map-shell">
    <div v-show="jsKey && !mapError" ref="mapElement" class="map-canvas" />
    <img v-if="mapError && fallbackImageUrl" :src="fallbackImageUrl" alt="目标点位静态地图" />
    <div v-else-if="mapError" class="map-fallback">
      <p>{{ mapError }}</p>
      <ol>
        <li v-for="target in targets" :key="target.target_id">
          <strong>{{ target.name }}</strong>
          <span>{{ target.location.longitude.toFixed(4) }}, {{ target.location.latitude.toFixed(4) }}</span>
        </li>
      </ol>
    </div>
  </div>
</template>
