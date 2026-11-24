<template>
  <div class="admin-page" data-testid="etl-quality-dashboard">
    <!-- ── 页头 ── -->
    <div class="page-header">
      <div class="page-heading">
        <h1>ETL 抽取质检</h1>
        <p class="page-subtitle">LLM 抽取 → 校验 → 归一 → 建图</p>
      </div>
      <button class="btn-primary" type="button" @click="handleReextract">重新抽取</button>
    </div>

    <!-- ── 统计卡片行 ── -->
    <div class="stat-grid">
      <div v-for="s in STATS" :key="s.key" class="stat-card" :class="'tone-' + s.tone">
        <p class="stat-label">{{ s.label }}</p>
        <p class="stat-value">
          {{ s.value }}
          <span v-if="s.suffix" class="stat-suffix">{{ s.suffix }}</span>
        </p>
        <p v-if="s.extra" class="stat-extra">{{ s.extra }}</p>
      </div>
    </div>

    <!-- ── 抽取状态分布 ── -->
    <section class="panel">
      <div class="panel-head">
        <h2 class="panel-title">抽取状态分布</h2>
        <span class="panel-hint">共 {{ STATS[0].value }} 篇文献</span>
      </div>
      <div class="status-list">
        <div v-for="s in EXTRACT_STATUS" :key="s.key" class="status-row">
          <span class="status-label">{{ s.label }}</span>
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="'fill-' + s.key"
              :style="{ width: s.pct + '%' }"
            ></div>
          </div>
          <span class="status-pct" :class="{ 'pct-idle': s.pct === 0 }">{{ s.pct }}%</span>
        </div>
      </div>
    </section>

    <!-- ── 节点 / 边 类型分布 ── -->
    <div class="dist-grid">
      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">节点类型分布</h2>
          <span class="panel-hint">节点总数 {{ nodeTotal }}</span>
        </div>
        <div class="bar-list">
          <div v-for="n in NODE_TYPES" :key="n.key" class="bar-row">
            <span class="bar-name">{{ n.key }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: barWidth(n.count, NODE_TYPES) + '%', background: n.color }"
              ></div>
            </div>
            <span class="bar-value">{{ n.count }}</span>
            <span class="bar-share">{{ shareOf(n.count, NODE_TYPES) }}%</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">边类型分布</h2>
          <span class="panel-hint">边总数 {{ edgeTotal }}</span>
        </div>
        <div class="bar-list">
          <div v-for="e in EDGE_TYPES" :key="e.key" class="bar-row">
            <span class="bar-name bar-name-mono">{{ e.key }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: barWidth(e.count, EDGE_TYPES) + '%', background: e.color }"
              ></div>
            </div>
            <span class="bar-value">{{ e.count }}</span>
            <span class="bar-share">{{ shareOf(e.count, EDGE_TYPES) }}%</span>
          </div>
        </div>
      </section>
    </div>

    <!-- ── 质检卡点 ── -->
    <section class="panel">
      <div class="panel-head">
        <h2 class="panel-title">质检卡点</h2>
        <span class="panel-hint">任一指标超阈值即打回重抽</span>
      </div>
      <div class="gate-grid">
        <div
          v-for="g in qualityGates"
          :key="g.key"
          class="gate-card"
          :class="g.passed ? 'gate-pass' : 'gate-fail'"
        >
          <div class="gate-head">
            <span class="gate-label">{{ g.label }}</span>
            <span class="gate-badge" :class="g.passed ? 'badge-pass' : 'badge-fail'">
              {{ g.passed ? "通过" : "打回" }}
            </span>
          </div>
          <p class="gate-value">
            {{ g.value }}<span class="gate-unit">%</span>
          </p>
          <div class="progress-track gate-track">
            <div
              class="progress-fill"
              :style="{
                width: gateBarWidth(g) + '%',
                background: g.passed ? '#00796b' : '#c62828',
              }"
            ></div>
          </div>
          <p class="gate-meta">
            阈值 {{ g.threshold }}% · 当前 {{ g.value }}%
            <span v-if="!g.passed" class="gate-action">→ 超出 {{ (g.value - g.threshold).toFixed(1) }} 个百分点，已打回重抽</span>
          </p>
          <p class="gate-desc">{{ g.desc }}</p>
        </div>
      </div>
    </section>

    <!-- ── 待复核清单 ── -->
    <section class="panel">
      <div class="panel-head">
        <h2 class="panel-title">待复核清单</h2>
        <span class="panel-hint">共 {{ REVIEW_ROWS.length }} 份文件待人工确认</span>
      </div>
      <div class="table-wrap">
        <table class="review-table" data-testid="etl-review-table">
          <thead>
            <tr>
              <th>文件</th>
              <th>doc_kind</th>
              <th>置信度</th>
              <th>原因</th>
              <th class="col-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in REVIEW_ROWS" :key="row.id">
              <td class="cell-file" :title="row.file">{{ row.file }}</td>
              <td>
                <span class="doc-badge" :class="'doc-' + row.doc_kind">
                  {{ DOC_KIND_LABELS[row.doc_kind] }}
                </span>
              </td>
              <td>
                <span class="conf" :class="confidenceLevel(row.confidence)">
                  {{ row.confidence.toFixed(2) }}
                </span>
              </td>
              <td class="cell-reason">{{ row.reason }}</td>
              <td class="col-action">
                <button class="btn-sm" type="button" @click="dispatch(row)">
                  派发标注
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ── 页脚说明 ── -->
    <p class="page-footer">
      三层兜底：<strong>缺失留空</strong> + <strong>校验拦截</strong> + <strong>低置信人工复核</strong>
      —— 抽取结果不猜测、不臆造，低置信一律进入待复核清单。
    </p>

    <!-- ── 全局提示 ── -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

/* ───────── 统计卡片 ───────── */
const STATS = [
  { key: "literature", label: "文献总数", value: 214, tone: "teal" },
  { key: "extracted", label: "已抽取", value: 186, tone: "teal" },
  { key: "pending", label: "待复核", value: 21, tone: "amber" },
  { key: "failed", label: "抽取失败", value: 7, tone: "red" },
  { key: "records", label: "病案记录", value: 132, tone: "teal" },
  { key: "graph", label: "图谱节点", value: 1580, extra: "图谱边 4312", tone: "teal" },
];

/* ───────── 抽取状态分布 ───────── */
const EXTRACT_STATUS = [
  { key: "extracted", label: "已抽取", pct: 87 },
  { key: "pending", label: "待复核", pct: 10 },
  { key: "failed", label: "失败", pct: 3 },
  { key: "idle", label: "未开始", pct: 0 },
];

/* ───────── 节点类型分布 ───────── */
const NODE_TYPES = [
  { key: "paper", count: 214, color: "#00796b" },
  { key: "record", count: 132, color: "#00897b" },
  { key: "keyword", count: 486, color: "#26a69a" },
  { key: "herb", count: 356, color: "#4db6ac" },
  { key: "formula", count: 242, color: "#80cbc4" },
  { key: "pattern", count: 150, color: "#b2dfdb" },
];

/* ───────── 边类型分布 ───────── */
const EDGE_TYPES = [
  { key: "ref", count: 980, color: "#004d40" },
  { key: "similar", count: 640, color: "#00695c" },
  { key: "MENTIONS", count: 1500, color: "#00796b" },
  { key: "CONTAINS", count: 420, color: "#00897b" },
  { key: "TREATS", count: 380, color: "#26a69a" },
  { key: "HAS_OUTCOME", count: 242, color: "#4db6ac" },
  { key: "CO_OCCURS", count: 150, color: "#80cbc4" },
];

const nodeTotal = computed(() => NODE_TYPES.reduce((n, i) => n + i.count, 0));
const edgeTotal = computed(() => EDGE_TYPES.reduce((n, i) => n + i.count, 0));

function barWidth(value, list) {
  const max = Math.max(...list.map((i) => i.count), 1);
  return Math.max(3, Math.round((value / max) * 100));
}

function shareOf(value, list) {
  const total = list.reduce((n, i) => n + i.count, 0) || 1;
  return ((value / total) * 100).toFixed(1);
}

/* ───────── 质检卡点 ───────── */
const GATES = [
  {
    key: "orphan",
    label: "孤点率",
    value: 18.4,
    threshold: 30,
    desc: "无任何连边的节点占全部节点的比例",
  },
  {
    key: "flagged",
    label: "flagged 率",
    value: 9.8,
    threshold: 20,
    desc: "抽取结果被标记为需人工确认的比例",
  },
];

const qualityGates = computed(() =>
  GATES.map((g) => ({ ...g, passed: g.value <= g.threshold }))
);

function gateBarWidth(gate) {
  return Math.min(100, Math.round((gate.value / gate.threshold) * 100));
}

/* ───────── 待复核清单 ───────── */
const DOC_KIND_LABELS = {
  literature: "文献",
  case_source: "病案",
  protocol_source: "方案",
};

const REVIEW_ROWS = [
  {
    id: 1,
    file: "卵巢储备功能减退中医证型分布研究_2021.pdf",
    doc_kind: "literature",
    confidence: 0.62,
    reason: "必填缺失（lit_8 诊断阈值依据为空）",
  },
  {
    id: 2,
    file: "DOR_针刺联合中药病案_037.docx",
    doc_kind: "case_source",
    confidence: 0.71,
    reason: "枚举不在字典（证型：肾虚湿热证）",
  },
  {
    id: 3,
    file: "早发性卵巢功能不全诊疗方案_v2.pdf",
    doc_kind: "protocol_source",
    confidence: 0.55,
    reason: "单位未识别（AMH 取值单位为 pmol/L）",
  },
  {
    id: 4,
    file: "腹腔镜术后卵巢储备随访_病例系列.pdf",
    doc_kind: "case_source",
    confidence: 0.68,
    reason: "实体无法归一（方剂：左归饮加减）",
  },
  {
    id: 5,
    file: "补肾填精方治疗DOR_RCT_2019.pdf",
    doc_kind: "literature",
    confidence: 0.83,
    reason: "必填缺失（lit_45 临床妊娠率未给出）",
  },
  {
    id: 6,
    file: "针灸周期疗法专家共识_2020.pdf",
    doc_kind: "protocol_source",
    confidence: 0.76,
    reason: "枚举不在字典（干预类型：温针灸）",
  },
  {
    id: 7,
    file: "中西医结合治疗DOR_回顾性队列.pdf",
    doc_kind: "literature",
    confidence: 0.59,
    reason: "单位未识别（FSH 单位 mIU/mL 未映射）",
  },
];

function confidenceLevel(value) {
  if (value >= 0.8) return "conf-high";
  if (value >= 0.65) return "conf-mid";
  return "conf-low";
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;

function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 3200);
}

function handleReextract() {
  showToast("已提交重新抽取任务：214 篇文献将按当前 prompt 版本重跑（mock）");
}

function dispatch(row) {
  showToast(`已派发「${row.file}」至标注队列（mock）`);
}
</script>

<style scoped>
.admin-page { width: 100%; min-height: 100%; padding: 24px 32px 40px; box-sizing: border-box; }

/* ── 页头 ── */
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.page-heading h1 { margin: 0; font-size: 22px; font-weight: 600; color: #1a1a2e; }
.page-subtitle { margin: 6px 0 0; font-size: 13px; color: #888; letter-spacing: 0.2px; }

.btn-primary {
  flex-shrink: 0;
  padding: 9px 20px;
  border: none;
  border-radius: 8px;
  background: #00796b;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}
.btn-primary:hover { background: #00695c; box-shadow: 0 3px 10px rgba(0, 121, 107, 0.28); }
.btn-primary:active { transform: translateY(1px); }

/* ── 统计卡片 ── */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 16px; }
.stat-card { border: 1px solid #e0e0e0; border-radius: 10px; background: #fff; padding: 14px 16px 12px; border-top: 3px solid #00796b; }
.stat-label { margin: 0 0 8px; font-size: 12px; color: #777; }
.stat-value { margin: 0; font-size: 24px; font-weight: 600; color: #00796b; line-height: 1.1; }
.stat-suffix { font-size: 12px; font-weight: 400; color: #999; margin-left: 4px; }
.stat-extra { margin: 6px 0 0; font-size: 12px; color: #999; }
.tone-amber { border-top-color: #f57f17; }
.tone-amber .stat-value { color: #ef6c00; }
.tone-red { border-top-color: #c62828; }
.tone-red .stat-value { color: #c62828; }

/* ── 面板通用 ── */
.panel { border: 1px solid #e0e0e0; border-radius: 10px; background: #fff; padding: 16px 18px 18px; margin-bottom: 16px; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.panel-title { margin: 0; font-size: 15px; font-weight: 600; color: #1a1a2e; }
.panel-hint { font-size: 12px; color: #999; }

/* ── CSS 进度条 ── */
.progress-track { height: 10px; border-radius: 999px; background: #eef1f0; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 999px; background: #00796b; transition: width 0.4s ease; }

/* ── 抽取状态分布 ── */
.status-list { display: flex; flex-direction: column; gap: 12px; }
.status-row { display: grid; grid-template-columns: 72px 1fr 52px; align-items: center; gap: 12px; }
.status-label { font-size: 13px; color: #444; }
.status-pct { font-size: 13px; font-weight: 600; color: #00796b; text-align: right; }
.fill-pending { background: #f9a825; }
.fill-failed { background: #c62828; }
.fill-idle { background: #cfd8d6; }
.pct-idle { color: #999; }

/* ── 节点 / 边 条形图 ── */
.dist-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.dist-grid .panel { margin-bottom: 16px; }
.bar-list { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 104px 1fr 52px 48px; align-items: center; gap: 10px; }
.bar-name { font-size: 12px; color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-name-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; color: #555; }
.bar-track { height: 12px; border-radius: 4px; background: #f2f4f3; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
.bar-value { font-size: 12px; font-weight: 600; color: #00796b; text-align: right; }
.bar-share { font-size: 11px; color: #999; text-align: right; }

/* ── 质检卡点 ── */
.gate-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.gate-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 16px; background: #fcfdfd; }
.gate-pass { border-left: 4px solid #00796b; }
.gate-fail { border-left: 4px solid #c62828; background: #fffafa; }
.gate-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.gate-label { font-size: 13px; color: #666; }
.gate-badge { padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.badge-pass { background: #e0f2f1; color: #00796b; }
.badge-fail { background: #ffebee; color: #c62828; }
.gate-value { margin: 0 0 10px; font-size: 26px; font-weight: 600; color: #00796b; line-height: 1.1; }
.gate-fail .gate-value { color: #c62828; }
.gate-unit { font-size: 14px; font-weight: 500; margin-left: 2px; }
.gate-track { height: 8px; }
.gate-meta { margin: 8px 0 0; font-size: 12px; color: #888; }
.gate-action { color: #c62828; font-weight: 600; }
.gate-desc { margin: 4px 0 0; font-size: 11px; color: #aaa; }

/* ── 待复核表格 ── */
.table-wrap { overflow-x: auto; }
.review-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.review-table th,
.review-table td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #ececec; vertical-align: middle; }
.review-table th { font-weight: 600; color: #666; background: #fafafa; white-space: nowrap; }
.review-table tbody tr:hover { background: #f6faf9; }
.review-table tbody tr:last-child td { border-bottom: none; }
.cell-file { color: #1a1a2e; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell-reason { color: #666; }
.col-action { text-align: right; white-space: nowrap; }

.doc-badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid transparent; }
.doc-literature { background: #e0f2f1; color: #00695c; border-color: #b2dfdb; }
.doc-case_source { background: #e8f1fb; color: #1565c0; border-color: #bbdefb; }
.doc-protocol_source { background: #f3e8fb; color: #6a1b9a; border-color: #e1bee7; }

.conf { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 600; }
.conf-high { color: #2e7d32; }
.conf-mid { color: #ef6c00; }
.conf-low { color: #c62828; }

.btn-sm { padding: 5px 12px; border: 1px solid #b2dfdb; border-radius: 6px; background: #fff; color: #00796b; font-size: 12px; cursor: pointer; transition: background 0.2s ease, border-color 0.2s ease; }
.btn-sm:hover { background: #e0f2f1; border-color: #00796b; }

/* ── 页脚 ── */
.page-footer { margin: 4px 0 0; padding: 12px 14px; border-left: 3px solid #b2dfdb; background: #f7fbfa; border-radius: 0 8px 8px 0; font-size: 12px; color: #888; line-height: 1.7; }
.page-footer strong { color: #00796b; font-weight: 600; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active,
.toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from,
.toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }

/* ── 响应式 ── */
@media (max-width: 720px) {
  .admin-page { padding: 16px; }
  .page-header { flex-direction: column; align-items: stretch; }
  .status-row { grid-template-columns: 60px 1fr 44px; }
  .bar-row { grid-template-columns: 84px 1fr 46px 44px; }
  .cell-file { max-width: 180px; }
}
</style>
