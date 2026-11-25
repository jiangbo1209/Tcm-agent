<template>
  <div class="admin-page">
    <div class="admin-header">
      <div>
        <h1>知识图谱</h1>
      </div>
      <div class="header-stats">
        <span class="stat-chip"><strong>{{ nodes.length }}</strong> 实体</span>
        <span class="stat-chip"><strong>{{ edges.length }}</strong> 关系</span>
      </div>
    </div>

    <!-- 边类型筛选 -->
    <div class="edge-filter card">
      <span class="filter-label">边类型</span>
      <label
        v-for="type in EDGE_META"
        :key="type.key"
        class="filter-chip"
        :class="{ off: !edgeTypeOn[type.key] }"
      >
        <input v-model="edgeTypeOn[type.key]" type="checkbox" />
        <svg class="chip-line" width="30" height="8" viewBox="0 0 30 8" aria-hidden="true">
          <line x1="1" y1="4" x2="29" y2="4" :stroke-dasharray="type.dash || undefined" />
        </svg>
        <span class="chip-name">{{ type.label }}</span>
      </label>
      <span class="filter-hint">已启用 {{ activeTypeCount }}/{{ EDGE_META.length }}</span>
    </div>

    <div class="graph-layout">
      <!-- 左侧图例 -->
      <aside class="legend card">
        <section class="legend-section">
          <h3>节点类型</h3>
          <ul class="legend-list">
            <li v-for="(meta, key) in NODE_META" :key="key">
              <span class="dot" :style="{ background: meta.color }"></span>
              <span class="legend-name">{{ meta.label }}</span>
              <code>{{ key }}</code>
            </li>
          </ul>
        </section>
        <section class="legend-section">
          <h3>边类型</h3>
          <ul class="legend-list edge-list">
            <li v-for="type in EDGE_META" :key="type.key">
              <svg class="edge-sample" width="32" height="8" viewBox="0 0 32 8" aria-hidden="true">
                <line x1="1" y1="4" x2="31" y2="4" :stroke-dasharray="type.dash || undefined" />
              </svg>
              <div class="edge-legend-text">
                <span class="legend-name">{{ type.desc }}</span>
                <code>{{ type.label }}</code>
              </div>
            </li>
          </ul>
        </section>
      </aside>

      <!-- 中间画布 -->
      <div class="canvas-wrap card">
        <svg class="graph-svg" viewBox="0 0 900 600" @click="selectedId = null">
          <defs>
            <pattern id="graph-grid" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#eef3f3" stroke-width="1" />
            </pattern>
          </defs>

          <rect width="900" height="600" fill="url(#graph-grid)" class="canvas-bg" />

          <g class="edges">
            <line
              v-for="edge in edgeLines"
              :key="edge.id"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              :stroke-dasharray="edgeDash(edge)"
              :stroke-width="edgeWidth(edge)"
              :style="{ opacity: edgeOpacity(edge) }"
              :class="{ 'edge-hot': isConnected(edge) }"
            />
          </g>

          <g class="nodes">
            <g
              v-for="node in nodes"
              :key="node.id"
              class="node-group"
              :class="{ selected: node.id === selectedId }"
              @click.stop="selectedId = node.id"
            >
              <circle
                :cx="node.x"
                :cy="node.y"
                r="28"
                :fill="NODE_META[node.type].color"
                class="node-circle"
              />
              <text class="node-glyph" :x="node.x" :y="node.y + 5">
                {{ NODE_META[node.type].glyph }}
              </text>
              <text class="node-label" :x="node.x" :y="node.y + 48">{{ node.label }}</text>
            </g>
          </g>
        </svg>
        <span class="canvas-tip">点击节点查看详情 · 点击空白处取消选中</span>
      </div>

      <!-- 右侧详情 -->
      <aside class="detail card">
        <template v-if="selectedNode">
          <div class="detail-head">
            <span class="dot lg" :style="{ background: nodeMeta(selectedNode.type).color }"></span>
            <div class="detail-title">
              <h2>{{ selectedNode.label }}</h2>
              <span
                class="type-tag"
                :style="{
                  color: nodeMeta(selectedNode.type).color,
                  borderColor: nodeMeta(selectedNode.type).color + '66',
                  background: nodeMeta(selectedNode.type).color + '14',
                }"
              >
                {{ nodeMeta(selectedNode.type).label }} · {{ selectedNode.type }}
              </span>
            </div>
          </div>

          <dl class="detail-stats">
            <div>
              <dt>连接数</dt>
              <dd>{{ degreeOf(selectedNode.id) }}</dd>
            </div>
            <div>
              <dt>关联文献</dt>
              <dd>{{ selectedNode.docs.length }}</dd>
            </div>
          </dl>

          <h3 class="section-title">关联文献</h3>
          <ul class="doc-list">
            <li v-for="doc in selectedNode.docs" :key="doc.id">
              <span class="doc-id">{{ doc.id }}</span>
              <p>{{ doc.title }}</p>
            </li>
          </ul>

          <h3 class="section-title">相邻实体</h3>
          <div class="neighbor-chips">
            <span v-for="nb in neighbors" :key="nb.id" class="neighbor-chip">
              <i :style="{ background: nodeMeta(nb.type).color }"></i>{{ nb.label }}
            </span>
          </div>
        </template>

        <div v-else class="detail-empty">
          <div class="empty-mark">◎</div>
          <p>未选中实体</p>
          <span>在左侧图谱中点击任意节点查看详细信息</span>
        </div>
      </aside>
    </div>

    <!-- 底部状态条 -->
    <div class="status-bar">
      <span>节点 {{ nodes.length }}</span>
      <i></i>
      <span>边 {{ edges.length }}</span>
      <i></i>
      <span>平均度 {{ avgDegree }}</span>
      <span class="status-right">图谱范围：DOR 文献与病案抽取结果（mock）</span>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

const NODE_META = {
  paper: { label: "文献", color: "#00796b", glyph: "文" },
  record: { label: "病案", color: "#8d6e63", glyph: "案" },
  keyword: { label: "关键词", color: "#5c6bc0", glyph: "词" },
  herb: { label: "药物", color: "#2e7d32", glyph: "药" },
  formula: { label: "方剂", color: "#ef6c00", glyph: "方" },
  pattern: { label: "证型", color: "#ad1457", glyph: "证" },
};

const EDGE_META = [
  { key: "ref", label: "ref", desc: "文献引用", dash: null },
  { key: "similar", label: "similar", desc: "相似文献/病案", dash: "7 4" },
  { key: "MENTIONS", label: "MENTIONS", desc: "提及关键词", dash: "2 4" },
  { key: "CONTAINS", label: "CONTAINS", desc: "方剂包含药物", dash: "10 4" },
  { key: "TREATS", label: "TREATS", desc: "方剂治疗证型", dash: "4 4" },
  { key: "HAS_OUTCOME", label: "HAS_OUTCOME", desc: "报告临床结局", dash: "12 3 2 3" },
  { key: "CO_OCCURS", label: "CO_OCCURS", desc: "药物共现", dash: "1 5" },
];

const DOC = {
  sys: { id: "LIT-2024-018", title: "补肾填精法治疗卵巢储备功能减退的系统评价" },
  rct: { id: "LIT-2023-045", title: "左归丸联合西药治疗 DOR 的随机对照试验" },
  case: { id: "CASE-2026-031", title: "肾虚肝郁型 DOR 病案一例（随访 12 个月）" },
  review: { id: "LIT-2022-007", title: "中医药治疗 DOR 用药规律的数据挖掘研究" },
};

const nodes = [
  { id: "p1", type: "paper", label: "系统评价", x: 85, y: 105, docs: [DOC.sys, DOC.review] },
  { id: "p2", type: "paper", label: "RCT 研究", x: 85, y: 265, docs: [DOC.rct] },
  { id: "r1", type: "record", label: "肾虚肝郁案", x: 85, y: 420, docs: [DOC.case, DOC.sys] },
  { id: "r2", type: "record", label: "脾肾阳虚案", x: 85, y: 545, docs: [DOC.case, DOC.review] },
  { id: "k1", type: "keyword", label: "卵巢储备减退", x: 270, y: 105, docs: [DOC.sys, DOC.review] },
  { id: "k2", type: "keyword", label: "补肾填精", x: 270, y: 265, docs: [DOC.sys, DOC.rct] },
  { id: "k3", type: "keyword", label: "妊娠结局", x: 270, y: 420, docs: [DOC.rct, DOC.case] },
  { id: "f1", type: "formula", label: "左归丸", x: 455, y: 105, docs: [DOC.rct, DOC.sys] },
  { id: "f2", type: "formula", label: "毓麟珠", x: 455, y: 420, docs: [DOC.review, DOC.case] },
  { id: "pat1", type: "pattern", label: "肾虚肝郁证", x: 825, y: 290, docs: [DOC.case, DOC.sys] },
  { id: "pat2", type: "pattern", label: "脾肾阳虚证", x: 825, y: 545, docs: [DOC.case, DOC.review] },
  { id: "h1", type: "herb", label: "熟地黄", x: 640, y: 105, docs: [DOC.rct, DOC.review] },
  { id: "h2", type: "herb", label: "菟丝子", x: 640, y: 265, docs: [DOC.sys, DOC.rct] },
  { id: "h3", type: "herb", label: "淫羊藿", x: 640, y: 420, docs: [DOC.review, DOC.case] },
];

const edges = [
  { id: "e1", source: "p1", target: "p2", type: "ref" },
  { id: "e2", source: "p1", target: "k1", type: "MENTIONS" },
  { id: "e3", source: "p2", target: "k2", type: "MENTIONS" },
  { id: "e4", source: "p2", target: "r1", type: "similar" },
  { id: "e5", source: "r1", target: "k3", type: "HAS_OUTCOME" },
  { id: "e6", source: "r2", target: "k3", type: "HAS_OUTCOME" },
  { id: "e7", source: "f1", target: "h1", type: "CONTAINS" },
  { id: "e8", source: "f1", target: "h2", type: "CONTAINS" },
  { id: "e9", source: "f2", target: "h3", type: "CONTAINS" },
  { id: "e10", source: "h2", target: "h3", type: "CO_OCCURS" },
  { id: "e11", source: "f1", target: "pat1", type: "TREATS" },
  { id: "e12", source: "f2", target: "pat2", type: "TREATS" },
];

const nodeMap = Object.fromEntries(nodes.map((node) => [node.id, node]));

const edgeTypeOn = reactive(
  Object.fromEntries(EDGE_META.map((type) => [type.key, true])),
);

const selectedId = ref(null);

const selectedNode = computed(() => nodes.find((node) => node.id === selectedId.value) || null);

const edgeLines = computed(() =>
  edges.map((edge) => {
    const source = nodeMap[edge.source];
    const target = nodeMap[edge.target];
    return { ...edge, x1: source.x, y1: source.y, x2: target.x, y2: target.y };
  }),
);

const activeTypeCount = computed(() => Object.values(edgeTypeOn).filter(Boolean).length);

const avgDegree = computed(() => ((edges.length * 2) / nodes.length).toFixed(1));

const neighbors = computed(() => {
  if (!selectedNode.value) return [];
  const ids = new Set();
  edges.forEach((edge) => {
    if (edge.source === selectedNode.value.id) ids.add(edge.target);
    if (edge.target === selectedNode.value.id) ids.add(edge.source);
  });
  return nodes.filter((node) => ids.has(node.id));
});

function nodeMeta(type) {
  return NODE_META[type];
}

function degreeOf(id) {
  return edges.filter((edge) => edge.source === id || edge.target === id).length;
}

function isConnected(edge) {
  return Boolean(
    selectedId.value && (edge.source === selectedId.value || edge.target === selectedId.value),
  );
}

function edgeDash(edge) {
  return EDGE_META.find((type) => type.key === edge.type)?.dash || undefined;
}

function edgeOpacity(edge) {
  if (!edgeTypeOn[edge.type]) return 0.12;
  return isConnected(edge) ? 1 : 0.7;
}

function edgeWidth(edge) {
  return isConnected(edge) ? 2.6 : 1.4;
}
</script>

<style scoped>
.header-stats {
  display: flex;
  gap: 8px;
  align-items: center;
}

.stat-chip {
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  color: var(--ink-500);
}

.stat-chip strong {
  font-size: 14px;
  color: var(--teal-dark);
  margin-right: 2px;
}

.edge-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
}

.filter-label {
  font-size: 12px;
  color: var(--ink-500);
  margin-right: 2px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fafbfb;
  font-size: 12px;
  color: var(--ink-700);
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s, opacity 0.15s;
}

.filter-chip:hover {
  border-color: var(--teal-border);
}

.filter-chip.off {
  opacity: 0.5;
}

.filter-chip input {
  width: 12px;
  height: 12px;
  margin: 0;
  accent-color: var(--teal);
}

.chip-line line {
  stroke: #7b8794;
  stroke-width: 1.6;
  stroke-linecap: round;
}

.filter-chip.off .chip-line line {
  stroke: #c3cbd3;
}

.chip-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.2px;
}

.filter-hint {
  margin-left: auto;
  font-size: 12px;
  color: var(--ink-400);
}

.graph-layout {
  display: grid;
  grid-template-columns: 212px minmax(0, 1fr) 268px;
  gap: 14px;
  align-items: stretch;
  height: calc(100vh - 240px);
  min-height: 520px;
}

.legend {
  padding: 16px;
  min-width: 0;
}

.legend-section h3 {
  margin: 0 0 10px;
  padding-left: 8px;
  border-left: 3px solid var(--teal);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700);
}

.legend-section + .legend-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--line);
}

.legend-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.legend-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot.lg {
  width: 13px;
  height: 13px;
  margin-top: 4px;
}

.legend-name {
  color: var(--ink-700);
  white-space: nowrap;
}

.legend-list code {
  margin-left: auto;
  padding: 1px 5px;
  border-radius: 3px;
  background: #f3f5f5;
  font-size: 10px;
  color: var(--ink-400);
  white-space: nowrap;
}

.edge-list li {
  align-items: flex-start;
  gap: 8px;
}

.edge-sample {
  flex-shrink: 0;
  margin-top: 4px;
}

.edge-sample line {
  stroke: #8a97a5;
  stroke-width: 1.5;
  stroke-linecap: round;
}

.edge-legend-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.edge-legend-text code {
  margin-left: 0;
  align-self: flex-start;
  font-size: 9px;
}

.canvas-wrap {
  position: relative;
  padding: 8px;
  overflow: hidden;
  min-width: 0;
}

.graph-svg {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 8px;
}

.canvas-bg {
  cursor: default;
}

.edges line {
  stroke: #94a3b8;
  stroke-linecap: round;
  transition: opacity 0.2s ease, stroke 0.2s ease;
}

.edges line.edge-hot {
  stroke: var(--teal);
}

.node-group {
  cursor: pointer;
  transform-box: fill-box;
  transform-origin: center;
  transition: transform 0.18s ease;
}

.node-group:hover {
  transform: scale(1.12);
}

.node-circle {
  stroke: #ffffff;
  stroke-width: 3;
  transition: stroke 0.15s ease;
}

.node-group.selected .node-circle {
  stroke: var(--ink-900);
  stroke-width: 3.5;
}

.node-glyph {
  fill: #fff;
  font-size: 14px;
  font-weight: 700;
  text-anchor: middle;
  pointer-events: none;
  user-select: none;
}

.node-label {
  fill: var(--ink-700);
  font-size: 12px;
  font-weight: 500;
  text-anchor: middle;
  pointer-events: none;
  user-select: none;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 3px;
  stroke-linejoin: round;
}

.node-group.selected .node-label {
  fill: var(--teal-dark);
  font-weight: 700;
}

.canvas-tip {
  position: absolute;
  right: 16px;
  bottom: 12px;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  font-size: 11px;
  color: var(--ink-400);
  pointer-events: none;
}

.detail {
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.detail-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.detail-title {
  min-width: 0;
}

.detail-title h2 {
  margin: 0 0 5px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
  line-height: 1.35;
}

.type-tag {
  display: inline-block;
  padding: 1px 8px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 10px;
  line-height: 1.6;
}

.detail-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 12px 0 0;
}

.detail-stats div {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f7f9f9;
}

.detail-stats dt {
  margin-bottom: 3px;
  font-size: 11px;
  color: var(--ink-400);
}

.detail-stats dd {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-900);
  line-height: 1.2;
}

.section-title {
  margin: 16px 0 8px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.3px;
  color: var(--ink-400);
}

.doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-list li {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
}

.doc-id {
  font-size: 10px;
  color: var(--teal-dark);
}

.doc-list p {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--ink-700);
}

.neighbor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.neighbor-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f3f5f5;
  font-size: 11px;
  color: var(--ink-700);
}

.neighbor-chip i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.detail-empty {
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  text-align: center;
  color: var(--ink-400);
}

.empty-mark {
  font-size: 30px;
  color: #cfd8dc;
}

.detail-empty p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}

.detail-empty span {
  font-size: 11px;
  line-height: 1.5;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  font-size: 12px;
  color: var(--ink-500);
}

.status-bar i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c3cbd3;
}

.status-right {
  margin-left: auto;
  color: var(--ink-400);
}

@media (max-width: 1280px) {
  .graph-layout {
    grid-template-columns: 188px minmax(0, 1fr);
  }

  .detail {
    grid-column: 1 / -1;
  }
}
</style>
