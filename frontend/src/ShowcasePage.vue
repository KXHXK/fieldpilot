<script setup lang="ts">
import { computed, ref } from "vue";

type Revision = 1 | 2;

const revision = ref<Revision>(2);

const timeline = {
  1: [
    { time: "06:30", title: "上海虹桥 → 杭州东", detail: "高铁二等座 · ¥73", state: "fixture" },
    { time: "08:53", title: "首个任务前缓冲", detail: "277 分钟 · 覆盖午餐窗口", state: "manual" },
    { time: "13:30", title: "西湖区客户现场", detail: "任务窗口内完成", state: "planned" },
    { time: "15:00", title: "转场至交通便利型酒店", detail: "出租车 · ¥36", state: "fixture" },
    { time: "翌日 09:30", title: "萧山区交付", detail: "原任务时间窗", state: "planned" },
    { time: "17:30", title: "杭州东 → 上海虹桥", detail: "返程高铁二等座 · ¥73", state: "fixture" }
  ],
  2: [
    { time: "06:30", title: "上海虹桥 → 杭州东", detail: "受保护前缀 · 内容不变", state: "locked" },
    { time: "08:53", title: "首个任务前缓冲", detail: "受保护前缀 · 内容不变", state: "locked" },
    { time: "13:30", title: "西湖区客户现场", detail: "已完成 · 检查点 V2", state: "completed" },
    { time: "15:00", title: "转场至交通便利型酒店", detail: "后缀重新求解", state: "fixture" },
    { time: "翌日 10:00", title: "萧山区交付", detail: "事件改期后重新编排", state: "changed" },
    { time: "17:30", title: "杭州东 → 上海虹桥", detail: "预算内返程 · ¥73", state: "fixture" }
  ]
} as const;

const currentTimeline = computed(() => timeline[revision.value]);

const evidence = [
  ["46 passed", "后端全量回归"],
  ["0004", "Alembic 最新迁移"],
  ["V2", "执行检查点"],
  ["6 / 11", "变化段 / 保持段"]
] as const;

const stack = [
  ["PydanticAI", "只负责自然语言到严格 MissionDraft，不拥有业务副作用。"],
  ["FastAPI + Pydantic", "承载版本化契约、幂等请求和明确错误边界。"],
  ["Bounded Beam Planner", "在时窗、交通、住宿、餐饮和报销约束下返回最多三套方案。"],
  ["Independent Verifier", "独立复算任务覆盖、费用、政策与受保护前缀。"],
  ["SQLAlchemy + Alembic", "持久化 Mission、Revision、Event、Snapshot 与执行检查点。"],
  ["Vue 3 + TypeScript", "呈现候选对比、执行时间线、来源和修订差异。"]
] as const;
</script>

<template>
  <main class="showcase-shell">
    <nav class="showcase-nav" aria-label="项目专题导航">
      <a class="brand" href="#top"><span>FP</span>FieldPilot</a>
      <div>
        <a href="#flow">闭环</a>
        <a href="#architecture">架构</a>
        <a href="#evidence">证据</a>
        <a href="#boundary">边界</a>
      </div>
      <a class="source-link" href="https://github.com/KXHXK/fieldpilot" target="_blank" rel="noreferrer">GitHub ↗</a>
    </nav>

    <header id="top" class="showcase-hero">
      <div class="hero-copy">
        <p class="eyebrow">FIELD MISSION ORCHESTRATION · STATIC SHOWCASE</p>
        <h1>把出差要求，<br /><em>变成可执行行程。</em></h1>
        <p class="hero-summary">
          FieldPilot 面向跨省市外勤场景，把地点、任务时间窗、紧密程度与报销规则转成可验证的交通、住宿、餐饮和多点任务方案；途中变化通过事件与执行检查点安全重规划。
        </p>
        <div class="hero-actions">
          <a class="button primary" href="#flow">查看 90 秒链路</a>
          <a class="button secondary" href="https://github.com/KXHXK/fieldpilot/blob/main/docs/architecture.md" target="_blank" rel="noreferrer">阅读架构取舍</a>
        </div>
      </div>
      <aside class="mission-card" aria-label="示例任务摘要">
        <span class="card-label">MISSION / HANGZHOU · 2 DAYS</span>
        <strong>上海 → 杭州</strong>
        <p>两个现场 · 高铁二等座 · 酒店 ≤ ¥450/晚</p>
        <div class="route-line" aria-hidden="true"><i></i><b></b><i></i><b></b><i></i></div>
        <dl>
          <div><dt>推荐方案</dt><dd>¥710</dd></div>
          <div><dt>预算余量</dt><dd>¥890</dd></div>
          <div><dt>来源模式</dt><dd>fixture + manual</dd></div>
        </dl>
        <small>公开页使用已验证的合成数据证据，不连接可写后端。</small>
      </aside>
    </header>

    <section class="fact-strip" aria-label="项目验证摘要">
      <article v-for="item in evidence" :key="item[1]"><strong>{{ item[0] }}</strong><span>{{ item[1] }}</span></article>
    </section>

    <section id="flow" class="showcase-section flow-section">
      <div class="section-heading">
        <p class="kicker">CHECKPOINTED REPLANNING</p>
        <h2>已执行的不能被重写，<br />变化只发生在后缀。</h2>
        <p>锁定首个现场任务后，第二个任务发生改期。Planner 从检查点的时间、位置和累计成本恢复搜索，Verifier 再逐段确认受保护前缀。</p>
      </div>

      <div class="flow-grid">
        <article class="trace-card">
          <ol class="trace-steps">
            <li><span>01</span><div><strong>解释</strong><small>自然语言 → MissionDraft</small></div></li>
            <li><span>02</span><div><strong>规划 R1</strong><small>三方案 + 政策判定</small></div></li>
            <li><span>03</span><div><strong>锁定 V1</strong><small>保护已承诺行程段</small></div></li>
            <li><span>04</span><div><strong>事件改期</strong><small>原子更新 Mission facts</small></div></li>
            <li><span>05</span><div><strong>重规划 R2</strong><small>仅求解检查点后缀</small></div></li>
            <li><span>06</span><div><strong>完成 V2</strong><small>执行位置单调推进</small></div></li>
          </ol>
        </article>

        <article class="timeline-card">
          <header>
            <div><span>EXECUTION TIMELINE</span><strong>修订 R{{ revision }}</strong></div>
            <div class="revision-tabs" role="group" aria-label="切换计划修订">
              <button :class="{ active: revision === 1 }" @click="revision = 1">R1 初始</button>
              <button :class="{ active: revision === 2 }" @click="revision = 2">R2 重规划</button>
            </div>
          </header>
          <div class="showcase-timeline">
            <article v-for="segment in currentTimeline" :key="`${revision}-${segment.time}-${segment.title}`" :class="`state-${segment.state}`">
              <time>{{ segment.time }}</time><i></i>
              <div><strong>{{ segment.title }}</strong><p>{{ segment.detail }}</p><span>{{ segment.state }}</span></div>
            </article>
          </div>
          <footer v-if="revision === 2"><b>R1 → R2</b><span>6 处变化 · 11 段保持 · 成本 +0 元</span></footer>
          <footer v-else><b>R1 ACTIVE</b><span>执行检查点 V0 · 等待锁定</span></footer>
        </article>
      </div>
    </section>

    <section id="architecture" class="showcase-section architecture-section">
      <div class="section-heading compact">
        <p class="kicker">DETERMINISTIC CORE</p>
        <h2>模型解释意图，<br />代码决定能否执行。</h2>
      </div>
      <div class="architecture-flow" aria-label="系统架构链路">
        <div><span>01</span><strong>Vue Workbench</strong><small>输入 / 时间线 / Diff</small></div><i>→</i>
        <div><span>02</span><strong>PydanticAI</strong><small>类型化语义入口</small></div><i>→</i>
        <div><span>03</span><strong>Provider Port</strong><small>高德 / Fixture / Snapshot</small></div><i>→</i>
        <div><span>04</span><strong>Planner</strong><small>有界搜索 + Policy</small></div><i>→</i>
        <div><span>05</span><strong>Verifier</strong><small>独立不变量复核</small></div>
      </div>
      <div class="stack-grid">
        <article v-for="item in stack" :key="item[0]"><strong>{{ item[0] }}</strong><p>{{ item[1] }}</p></article>
      </div>
    </section>

    <section id="evidence" class="showcase-section evidence-section">
      <div class="section-heading compact">
        <p class="kicker">VERIFIED DELIVERY</p>
        <h2>每个结论都有可复核证据。</h2>
      </div>
      <div class="evidence-grid">
        <article><span>API & DATABASE</span><strong>幂等、版本冲突与迁移往返</strong><p>ExecutionCommand 保存命令指纹；expected_version 防止并发覆盖；Alembic 0004 可升级、检查和回退。</p></article>
        <article><span>PLANNING</span><strong>受保护前缀逐字段一致</strong><p>HTTP 冒烟输出 protected_prefix_unchanged=true；Verifier 测试覆盖删除、篡改和越界。</p></article>
        <article><span>FRONTEND</span><strong>真实浏览器主链路</strong><p>R1 → lock V1 → event → R2 → complete V2；已完成任务禁用，控制台无 warning/error。</p></article>
        <article><span>DELIVERY</span><strong>GitHub main CI success</strong><p>后端 46 项测试、迁移 schema check 与 Vue TypeScript/Vite production build 均通过。</p></article>
      </div>
      <div class="evidence-actions">
        <a href="https://github.com/KXHXK/fieldpilot/blob/main/docs/development-log.md" target="_blank" rel="noreferrer">开发日志 ↗</a>
        <a href="https://github.com/KXHXK/fieldpilot/blob/main/docs/demo-guide.md" target="_blank" rel="noreferrer">五分钟演示 ↗</a>
        <a href="https://github.com/KXHXK/fieldpilot/actions" target="_blank" rel="noreferrer">CI 记录 ↗</a>
      </div>
    </section>

    <section id="boundary" class="showcase-section boundary-section">
      <div>
        <p class="kicker">HONEST BOUNDARY</p>
        <h2>这是静态项目专题，<br />不是公开预订或写入服务。</h2>
      </div>
      <div class="boundary-copy">
        <p>完整工作台在本地连接 FastAPI、SQLite/PostgreSQL 配置与显式 Mock/Fixture。公网页面只展示已验证的合成场景和工程证据，不暴露模型、地图或数据库凭据。</p>
        <ul>
          <li><b>已实现：</b>高德路线/餐饮适配契约、降级、缓存与来源快照。</li>
          <li><b>当前 Fixture：</b>铁路、航班、酒店库存和价格，不抓取 12306 内部接口。</li>
          <li><b>尚未验证：</b>真实高德/LLM Key、Docker/PostgreSQL 公网运行与生产级限流。</li>
          <li><b>算法口径：</b>有界 Beam Search 可解释、可复现，但不声称全局最优。</li>
        </ul>
        <a class="button primary" href="https://github.com/KXHXK/fieldpilot" target="_blank" rel="noreferrer">查看源码、测试与文档</a>
      </div>
    </section>

    <footer class="showcase-footer"><span>FieldPilot · 0.4.0-dev</span><b>EXPLAINABLE · REPLANNABLE · AUDITABLE</b><span>2026</span></footer>
  </main>
</template>

<style scoped>
.showcase-shell{width:min(1180px,calc(100% - 40px));margin:0 auto;color:#17251e}.showcase-nav{position:sticky;top:0;z-index:20;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:18px 0;background:rgba(244,246,241,.9);border-bottom:1px solid #d9dfd8;backdrop-filter:blur(12px)}.showcase-nav a{color:inherit;text-decoration:none}.showcase-nav>div{display:flex;gap:28px;font-size:12px;font-weight:700}.brand{display:flex;align-items:center;gap:10px;font-weight:800}.brand span{display:grid;place-items:center;width:31px;height:31px;color:#fff;background:#174e39;border-radius:9px;font-size:11px}.source-link{justify-self:end;padding:9px 13px;border:1px solid #b9c8be;border-radius:9px;color:#174e39!important;font-size:11px;font-weight:800}.showcase-hero{display:grid;grid-template-columns:1.25fr .75fr;gap:72px;align-items:center;min-height:660px;padding:80px 0}.eyebrow,.kicker{margin:0 0 18px;color:#e5663e;font-size:11px;font-weight:800;letter-spacing:.16em}.showcase-hero h1{margin:0;font-size:clamp(54px,7vw,94px);line-height:.98;letter-spacing:-.065em}.showcase-hero h1 em{color:#1c694a;font-style:normal}.hero-summary{max-width:760px;margin:30px 0 0;color:#58675f;font-size:16px;line-height:1.9}.hero-actions{display:flex;gap:12px;margin-top:32px}.button{display:inline-flex;align-items:center;justify-content:center;padding:12px 17px;border-radius:10px;text-decoration:none;font-size:12px;font-weight:800}.button.primary{color:#fff;background:#1c694a}.button.secondary{color:#17251e;background:#e4e9e3}.mission-card{padding:32px;color:#eff7f1;background:#123e2e;border-radius:24px;box-shadow:0 28px 80px rgba(18,62,46,.18)}.card-label{color:#9cc2ae;font-size:9px;letter-spacing:.13em}.mission-card>strong{display:block;margin:14px 0 7px;font-size:30px}.mission-card>p,.mission-card>small{color:#b8d0c3;line-height:1.65}.route-line{display:grid;grid-template-columns:12px 1fr 12px 1fr 12px;align-items:center;margin:30px 0}.route-line i{height:12px;background:#c5f04d;border:3px solid #486e5e;border-radius:50%}.route-line b{height:1px;background:#66897a}.mission-card dl{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 22px}.mission-card dl div{padding:12px;background:rgba(255,255,255,.06);border-radius:10px}.mission-card dt{color:#9cc2ae;font-size:9px}.mission-card dd{margin:6px 0 0;font-size:13px;font-weight:800}.fact-strip{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #d6ddd6;border-bottom:1px solid #d6ddd6}.fact-strip article{padding:25px;border-right:1px solid #d6ddd6}.fact-strip article:last-child{border-right:0}.fact-strip strong,.fact-strip span{display:block}.fact-strip strong{color:#174e39;font-size:27px}.fact-strip span{margin-top:6px;color:#6a776f;font-size:10px;letter-spacing:.07em}.showcase-section{padding:110px 0;border-bottom:1px solid #d6ddd6}.section-heading{display:grid;grid-template-columns:1.05fr .95fr;gap:70px;align-items:end;margin-bottom:50px}.section-heading h2{margin:0;font-size:clamp(38px,5vw,66px);line-height:1.08;letter-spacing:-.05em}.section-heading>p:last-child{color:#647169;line-height:1.85}.section-heading.compact{display:block;max-width:760px}.flow-grid{display:grid;grid-template-columns:.72fr 1.28fr;gap:18px}.trace-card,.timeline-card{padding:30px;background:#fff;border:1px solid #d7dfd8;border-radius:20px}.trace-steps{display:grid;gap:0;padding:0;margin:0;list-style:none}.trace-steps li{display:grid;grid-template-columns:42px 1fr;gap:13px;min-height:70px}.trace-steps li>span{display:grid;place-items:center;width:31px;height:31px;color:#1c694a;background:#e3efe7;border-radius:9px;font-size:10px;font-weight:800}.trace-steps li:not(:last-child)>span:after{content:"";position:absolute;width:1px;height:39px;margin-top:70px;background:#cdd9d1}.trace-steps strong,.trace-steps small{display:block}.trace-steps small{margin-top:5px;color:#758178}.timeline-card>header{display:flex;align-items:center;justify-content:space-between;padding-bottom:20px;border-bottom:1px solid #e1e6e1}.timeline-card header span,.timeline-card header strong{display:block}.timeline-card header span{color:#758178;font-size:9px;letter-spacing:.12em}.timeline-card header strong{margin-top:6px}.revision-tabs{display:flex;gap:5px}.revision-tabs button{padding:7px 10px;color:#526058;background:#edf1ed;border:0;border-radius:7px;font-size:10px}.revision-tabs button.active{color:#fff;background:#1c694a}.showcase-timeline{padding-top:24px}.showcase-timeline article{display:grid;grid-template-columns:75px 14px 1fr;gap:13px;min-height:74px}.showcase-timeline time{font-size:11px;font-weight:800;text-align:right}.showcase-timeline i{position:relative;width:10px;height:10px;background:#1c694a;border:3px solid #deebe3;border-radius:50%}.showcase-timeline i:after{content:"";position:absolute;top:9px;left:2px;width:1px;height:56px;background:#ced8d1}.showcase-timeline article:last-child i:after{display:none}.showcase-timeline strong,.showcase-timeline p{display:block;margin:0}.showcase-timeline p{margin-top:5px;color:#718078;font-size:10px}.showcase-timeline span{display:inline-block;margin-top:7px;padding:3px 6px;color:#1b6044;background:#e4f0e8;border-radius:5px;font-size:8px;font-weight:800;text-transform:uppercase}.showcase-timeline .state-changed i{background:#e5663e;border-color:#f8ddd4}.showcase-timeline .state-completed{opacity:.72}.showcase-timeline .state-completed strong{text-decoration:line-through}.timeline-card>footer{display:flex;justify-content:space-between;padding-top:17px;border-top:1px solid #e1e6e1;font-size:10px}.timeline-card>footer b{color:#e5663e}.architecture-section{background:#173f30;color:#edf6ef;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw);padding-left:max(20px,calc((100vw - 1180px)/2));padding-right:max(20px,calc((100vw - 1180px)/2))}.architecture-section .kicker{color:#c8ee55}.architecture-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr;gap:10px;align-items:center;margin:52px 0}.architecture-flow>div{padding:19px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.11);border-radius:14px}.architecture-flow span,.architecture-flow strong,.architecture-flow small{display:block}.architecture-flow span{color:#c8ee55;font-size:9px}.architecture-flow strong{margin-top:10px;font-size:13px}.architecture-flow small{margin-top:5px;color:#a8c0b2;font-size:9px}.architecture-flow>i{color:#8daa9b;font-style:normal}.stack-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.stack-grid article{padding:21px;background:#f0f5f1;border-radius:14px;color:#17251e}.stack-grid p{margin:8px 0 0;color:#66736b;font-size:11px;line-height:1.65}.evidence-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.evidence-grid article{padding:27px;background:#fff;border:1px solid #d7dfd8;border-radius:17px}.evidence-grid span{color:#e5663e;font-size:9px;font-weight:800;letter-spacing:.12em}.evidence-grid strong{display:block;margin-top:12px;font-size:18px}.evidence-grid p{margin:9px 0 0;color:#66736b;font-size:12px;line-height:1.7}.evidence-actions{display:flex;gap:10px;margin-top:18px}.evidence-actions a{padding:10px 13px;color:#174e39;background:#e5ede7;border-radius:8px;text-decoration:none;font-size:10px;font-weight:800}.boundary-section{display:grid;grid-template-columns:1fr 1fr;gap:80px}.boundary-section h2{margin:0;font-size:clamp(38px,5vw,62px);line-height:1.07;letter-spacing:-.045em}.boundary-copy>p,.boundary-copy li{color:#5f6d65;line-height:1.75}.boundary-copy ul{display:grid;gap:8px;padding-left:20px;margin:22px 0 30px}.boundary-copy b{color:#20342a}.showcase-footer{display:flex;justify-content:space-between;padding:28px 0;color:#6e7c74;font-size:9px;letter-spacing:.1em}.showcase-footer b{color:#174e39}@media(max-width:900px){.showcase-nav{grid-template-columns:1fr auto}.showcase-nav>div{display:none}.showcase-hero,.section-heading,.flow-grid,.boundary-section{grid-template-columns:1fr}.showcase-hero{gap:42px;padding:60px 0}.fact-strip{grid-template-columns:repeat(2,1fr)}.fact-strip article:nth-child(2){border-right:0}.fact-strip article:nth-child(-n+2){border-bottom:1px solid #d6ddd6}.architecture-flow{grid-template-columns:1fr}.architecture-flow>i{transform:rotate(90deg);justify-self:center}.stack-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.showcase-shell{width:min(100% - 24px,1180px)}.showcase-hero h1{font-size:49px}.mission-card{padding:24px}.mission-card dl,.stack-grid,.evidence-grid{grid-template-columns:1fr}.fact-strip strong{font-size:22px}.showcase-section{padding:75px 0}.trace-card,.timeline-card{padding:20px}.revision-tabs{display:grid}.showcase-timeline article{grid-template-columns:58px 12px 1fr}.evidence-actions,.showcase-footer{display:grid}.architecture-section{padding-left:12px;padding-right:12px}.source-link{font-size:0}.source-link:after{content:"↗";font-size:12px}}
.architecture-section{margin-left:0;margin-right:0;padding-left:50px;padding-right:50px;border-radius:28px}
@media(max-width:560px){.architecture-section{padding-left:20px;padding-right:20px}}
</style>
