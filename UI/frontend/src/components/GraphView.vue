<template>
  <div class="graph-container" ref="containerRef">
    <div ref="graphRef" class="graph-canvas"></div>
    <div class="graph-overlay">
      <div class="zoom-controls">
        <button type="button" class="icon-btn" @click="zoomIn" title="放大">
          <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <button type="button" class="icon-btn" @click="zoomOut" title="缩小">
          <svg viewBox="0 0 24 24"><path d="M5 12h14" /></svg>
        </button>
        <button type="button" class="icon-btn" @click="fitView" title="适配视图">
          <svg viewBox="0 0 24 24"><path d="M8 4H4v4M16 4h4v4M20 16v4h-4M8 20H4v-4" /><path d="M9 9h6v6H9z" /></svg>
        </button>
      </div>
      <div class="year-legend">
        <div class="year-legend-labels"><span>1963</span><span>2024</span></div>
        <div class="year-bar"></div>
      </div>
    </div>
    <div v-if="loading" class="graph-loading">
      <div class="taiji-spinner"><span class="taiji-dot"></span></div>
      <div class="loading-text">正在演算中医关系网络...</div>
    </div>
    <div v-if="!loading && nodeCount === 0" class="graph-empty">
      <div class="empty-art"><span class="empty-ring"></span><span class="empty-dot"></span><span class="empty-wave"></span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import G6 from "@antv/g6";
import { expandGraph } from "../api/graph";

const YEAR_DOMAIN = [1963, 2024];
const AGE_DOMAIN = [18, 75];
const SIZE_DOMAIN = [0.8, 3.0];
const DISTANCE_RANGE = [60, 180];
const DEFAULT_NODE_STROKE = "#aeb7c2";
const SEED_NODE_STROKE = "#7e3af2";
const HOVER_NODE_STROKE = "#4f46e5";
const EDGE_BASE_COLOR = "#aeb7c2";
const LABEL_MAX_CHARS = 16;

const emit = defineEmits(["nodeClick", "nodeHover"]);
const props = defineProps({ maxExpansions: { type: Number, default: 3 } });
const containerRef = ref(null);
const graphRef = ref(null);
const loading = ref(false);
const nodeCount = ref(0);

let graph = null;
let activeSeedNodeId = null;
const nodeMap = new Map();
const edgeMap = new Map();
const inFlightSeeds = new Set();
const expansionHistory = [];

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
function normalize(v, d) { const s = Number.isFinite(v) ? v : d[0]; return d[0] === d[1] ? 0.5 : (clamp(s, d[0], d[1]) - d[0]) / (d[1] - d[0]); }
function mapNodeSize(topK) { return Math.round(20 + normalize(topK, SIZE_DOMAIN) * 52); }
function truncateLabel(t, m) { const r = String(t || "").trim(); return r.length <= m ? r : `${r.slice(0, m - 1)}…`; }
function hexToRgb(h) { let n = String(h || "").replace("#", "").trim(); if (n.length === 3) n = n.split("").map(c => c + c).join(""); if (!/^[0-9a-fA-F]{6}$/.test(n)) return { r: 0, g: 0, b: 0 }; return { r: parseInt(n.slice(0, 2), 16), g: parseInt(n.slice(2, 4), 16), b: parseInt(n.slice(4, 6), 16) }; }
function mixColor(a, b, t) { const fa = hexToRgb(a), fb = hexToRgb(b), p = clamp(Number.isFinite(t) ? t : 0, 0, 1); return `rgb(${Math.round(fa.r + (fb.r - fa.r) * p)},${Math.round(fa.g + (fb.g - fa.g) * p)},${Math.round(fa.b + (fb.b - fa.b) * p)})`; }
function mapNodeColor(type, year, age) { return type === "paper" ? mixColor("#c9f4ee", "#00796b", normalize(year, YEAR_DOMAIN)) : mixColor("#fff2b3", "#b86a00", normalize(age, AGE_DOMAIN)); }
function mapDistance(s) { return Math.round(DISTANCE_RANGE[1] - clamp(Number(s) || 0, 0, 1) * (DISTANCE_RANGE[1] - DISTANCE_RANGE[0])); }
function mapEdgeOpacity(s) { return Number((0.25 + clamp(Number(s) || 0, 0, 1) * 0.65).toFixed(3)); }

function mapNode(raw) {
  const nt = raw.node_type === "paper" ? "paper" : "record";
  const topK = Number(raw.top_k_value);
  const py = Number(raw.publish_year ?? raw.metric_value);
  const age = Number(raw.age ?? raw.metric_value);
  const size = mapNodeSize(topK);
  const full = raw.title || String(raw.id);
  const node = {
    id: String(raw.id), node_type: nt, title: raw.title || String(raw.id),
    label: truncateLabel(full, LABEL_MAX_CHARS), full_label: full, short_label: truncateLabel(full, LABEL_MAX_CHARS),
    metric_value: Number(raw.metric_value), publish_year: Number.isFinite(py) ? py : null,
    age: Number.isFinite(age) ? age : null, top_k_value: Number.isFinite(topK) ? topK : null,
    type: nt === "paper" ? "circle" : "rect", size: nt === "paper" ? size : [size, size],
    style: { fill: mapNodeColor(nt, py, age), stroke: DEFAULT_NODE_STROKE, lineWidth: 1, cursor: "pointer" },
    labelCfg: { style: { fill: "#153a47", fontSize: 11, fontWeight: 400, background: { fill: "rgba(255,255,255,0.52)", radius: 4, padding: [1, 2] } }, position: "bottom", offset: 7 },
  };
  const x = Number(raw.x);
  const y = Number(raw.y);
  if (Number.isFinite(x)) node.x = x;
  if (Number.isFinite(y)) node.y = y;
  return node;
}

function mapEdge(raw) {
  const et = String(raw.edge_type || "paper-paper") === "record-paper" ? "paper-record" : String(raw.edge_type || "paper-paper");
  const score = clamp(Number(raw.similarity_score) || 0, 0, 1);
  const op = mapEdgeOpacity(score);
  let style;
  if (et === "paper-record") style = { stroke: EDGE_BASE_COLOR, lineWidth: 3.4 + score * 1.4, lineDash: null, opacity: op, endArrow: false };
  else if (et === "record-record") style = { stroke: EDGE_BASE_COLOR, lineWidth: 1.5 + score * 0.7, lineDash: [7, 5], opacity: op, endArrow: false };
  else style = { stroke: EDGE_BASE_COLOR, lineWidth: 1 + score * 0.6, lineDash: null, opacity: op, endArrow: false };
  return { id: String(raw.id || `${raw.source}->${raw.target}|${et}`), source: String(raw.source), target: String(raw.target), edge_type: et, similarity_score: score, base_opacity: op, type: "line", style };
}

function applyNodeBaseStyle(item) {
  const m = item.getModel();
  if (activeSeedNodeId && m.id === activeSeedNodeId) {
    graph.updateItem(item, { style: { stroke: SEED_NODE_STROKE, lineWidth: 4, opacity: 1 }, label: m.full_label || m.label, labelCfg: { style: { opacity: 1 } } });
  } else {
    graph.updateItem(item, { style: { stroke: DEFAULT_NODE_STROKE, lineWidth: 1, opacity: 1 }, label: m.short_label || m.label, labelCfg: { style: { opacity: 0.9 } } });
  }
}

function applyEdgeBaseStyle(item) {
  const m = item.getModel();
  graph.updateItem(item, { style: { stroke: EDGE_BASE_COLOR, opacity: Number.isFinite(m.base_opacity) ? m.base_opacity : 0.5 } });
}

function resetHover() { graph.getNodes().forEach(applyNodeBaseStyle); graph.getEdges().forEach(applyEdgeBaseStyle); }

function applyHover(focusItem) {
  if (!focusItem) { resetHover(); return; }
  const focusId = focusItem.getModel().id;
  const related = new Set([focusId]);
  const relatedEdges = new Set();
  (focusItem.getEdges?.() || []).forEach(e => { relatedEdges.add(e.getModel().id); related.add(e.getSource().getModel().id); related.add(e.getTarget().getModel().id); });
  graph.getNodes().forEach(n => {
    const id = n.getModel().id;
    if (!related.has(id)) { graph.updateItem(n, { style: { opacity: 0.1 }, labelCfg: { style: { opacity: 0.1 } } }); return; }
    if (activeSeedNodeId && id === activeSeedNodeId) { graph.updateItem(n, { style: { stroke: SEED_NODE_STROKE, lineWidth: 4, opacity: 1 }, label: n.getModel().full_label || n.getModel().label, labelCfg: { style: { opacity: 1 } } }); return; }
    graph.updateItem(n, { style: { stroke: HOVER_NODE_STROKE, lineWidth: id === focusId ? 3 : 2, opacity: 1 }, label: n.getModel().full_label || n.getModel().label, labelCfg: { style: { opacity: 1 } } });
  });
  graph.getEdges().forEach(e => { const m = e.getModel(); const base = Number.isFinite(m.base_opacity) ? m.base_opacity : 0.5; graph.updateItem(e, { style: { stroke: EDGE_BASE_COLOR, opacity: relatedEdges.has(m.id) ? Math.min(1, base + 0.18) : Math.max(0.04, base * 0.2) } }); });
}

function markSeed(id) {
  if (activeSeedNodeId && activeSeedNodeId !== id) { const prev = graph.findById(activeSeedNodeId); if (prev) applyNodeBaseStyle(prev); }
  activeSeedNodeId = id;
  const cur = graph.findById(id); if (cur) applyNodeBaseStyle(cur);
}

function mergeGraph(payload) {
  const inN = Array.isArray(payload.nodes) ? payload.nodes.map(mapNode) : [];
  const inE = Array.isArray(payload.edges) ? payload.edges.map(mapEdge) : [];
  const newN = inN.filter(n => !nodeMap.has(n.id));
  inN.forEach(n => {
    const existing = nodeMap.get(n.id);
    if (existing) {
      if (!Number.isFinite(n.x) && Number.isFinite(existing.x)) n.x = existing.x;
      if (!Number.isFinite(n.y) && Number.isFinite(existing.y)) n.y = existing.y;
    }
    nodeMap.set(n.id, n);
  });
  const validE = inE.filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));
  const newE = validE.filter(e => !edgeMap.has(e.id));
  validE.forEach(e => edgeMap.set(e.id, e));
  newN.forEach(n => graph.addItem("node", n));
  newE.forEach(e => graph.addItem("edge", e));
  nodeCount.value = nodeMap.size;
  return {
    nodeIds: inN.map(n => n.id),
    edgeIds: validE.map(e => e.id),
  };
}

function syncNodePositions() {
  if (!graph) return;
  graph.getNodes().forEach(item => {
    const model = item.getModel();
    const node = nodeMap.get(String(model.id));
    if (!node) return;
    const x = Number(model.x);
    const y = Number(model.y);
    if (Number.isFinite(x)) node.x = x;
    if (Number.isFinite(y)) node.y = y;
  });
}

function renderCurrentGraph() {
  if (!graph) return;
  syncNodePositions();
  const edges = Array.from(edgeMap.values()).filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));
  graph.changeData({ nodes: Array.from(nodeMap.values()), edges });
  nodeCount.value = nodeMap.size;
  if (activeSeedNodeId && nodeMap.has(activeSeedNodeId)) {
    const item = graph.findById(activeSeedNodeId);
    if (item) applyNodeBaseStyle(item);
  }
}

function trimExpansions({ relayout = false } = {}) {
  const limit = Math.max(0, Number(props.maxExpansions) || 0);
  if (limit <= 0 || expansionHistory.length <= limit) return;

  expansionHistory.splice(0, expansionHistory.length - limit);

  // Keep the union of the latest complete expansion payloads, then derive
  // visible nodes from the remaining edges so stale isolated nodes disappear.
  const keptEdgeIds = new Set();
  for (const exp of expansionHistory) {
    exp.edgeIds.forEach(id => keptEdgeIds.add(id));
  }

  for (const [eid, edge] of Array.from(edgeMap.entries())) {
    if (!keptEdgeIds.has(eid) || !nodeMap.has(edge.source) || !nodeMap.has(edge.target)) {
      edgeMap.delete(eid);
    }
  }

  const connectedNodeIds = new Set();
  for (const edge of edgeMap.values()) {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  }

  if (edgeMap.size === 0 && activeSeedNodeId && nodeMap.has(activeSeedNodeId)) {
    connectedNodeIds.add(activeSeedNodeId);
  }

  for (const nid of Array.from(nodeMap.keys())) {
    if (!connectedNodeIds.has(nid)) nodeMap.delete(nid);
  }

  if (activeSeedNodeId && !nodeMap.has(activeSeedNodeId)) activeSeedNodeId = null;
  renderCurrentGraph();
  if (relayout) graph.layout();
}

async function fetchAndExpand(seedId) {
  if (inFlightSeeds.has(seedId)) return;
  try {
    inFlightSeeds.add(seedId);
    loading.value = true;
    const { data } = await expandGraph(seedId);

    const centerX = graphRef.value?.clientWidth / 2 || 400;
    const centerY = graphRef.value?.clientHeight / 2 || 300;

    // 给新节点设置初始位置（围绕种子节点散开）
    const existingCount = nodeMap.size;
    const inN = Array.isArray(data.nodes) ? data.nodes : [];
    inN.forEach((raw, i) => {
      if (!nodeMap.has(String(raw.id))) {
        const angle = (2 * Math.PI * (existingCount + i)) / Math.max(inN.length, 6);
        const radius = 80 + Math.random() * 60;
        raw.x = centerX + radius * Math.cos(angle);
        raw.y = centerY + radius * Math.sin(angle);
      }
    });

    const { nodeIds, edgeIds } = mergeGraph(data);

    // 记录本次接口返回的完整子图，而不是只记录新增节点/边。
    expansionHistory.push({ seedId: String(seedId), nodeIds: new Set(nodeIds), edgeIds: new Set(edgeIds) });

    // 种子节点放中心
    const seedNode = nodeMap.get(seedId);
    if (seedNode) {
      seedNode.x = centerX;
      seedNode.y = centerY;
    }
    const item = graph.findById(seedId);
    if (item) graph.updateItem(item, { x: centerX, y: centerY });

    // 裁剪超出限制的旧扩展
    trimExpansions();

    // 运行一次性布局
    graph.layout();
    if (nodeMap.has(String(seedId))) markSeed(String(seedId));

    // 布局完成后适配视图
    setTimeout(() => graph.fitView(40), 500);
  } finally {
    inFlightSeeds.delete(seedId);
    loading.value = false;
  }
}

function zoomIn() { graph?.zoom(1.12); }
function zoomOut() { graph?.zoom(0.9); }
function fitView() { graph?.fitView(20); }
function focusNode(id) { const item = graph?.findById(id); if (item && graph.focusItem) graph.focusItem(item, true, { easing: "easeCubic", duration: 400 }); }
function clearGraph() { activeSeedNodeId = null; nodeMap.clear(); edgeMap.clear(); inFlightSeeds.clear(); expansionHistory.length = 0; nodeCount.value = 0; graph?.changeData({ nodes: [], edges: [] }); }

function applyMaxExpansions() { trimExpansions({ relayout: true }); }

onMounted(() => {
  const container = graphRef.value;
  if (!container) return;
  graph = new G6.Graph({
    container,
    width: container.clientWidth,
    height: container.clientHeight,
    modes: { default: ["drag-canvas", "zoom-canvas", "drag-node"] },
    defaultNode: { type: "circle", size: 26, style: { lineWidth: 1, stroke: DEFAULT_NODE_STROKE, fill: "#e6edf5" } },
    defaultEdge: { style: { stroke: EDGE_BASE_COLOR, opacity: 0.5 } },
    layout: {
      type: "force",
      preventOverlap: true,
      linkDistance: (edge) => mapDistance(edge.similarity_score),
      nodeStrength: -80,
      edgeStrength: 0.6,
      collideStrength: 0.8,
      alphaDecay: 0.05,
      alphaMin: 0.01,
    },
  });
  graph.data({ nodes: [], edges: [] });
  graph.render();

  graph.on("node:click", async (ev) => {
    const model = ev.item.getModel();
    if (!model?.id) return;
    markSeed(model.id);
    emit("nodeClick", model);
    await fetchAndExpand(model.id);
  });
  graph.on("node:mouseenter", (ev) => { applyHover(ev.item); emit("nodeHover", ev.item.getModel()); });
  graph.on("node:mouseleave", () => { resetHover(); emit("nodeHover", null); });

  window.addEventListener("resize", () => { if (graph && container) graph.changeSize(container.clientWidth, container.clientHeight); });
});

onBeforeUnmount(() => { graph?.destroy(); graph = null; });

defineExpose({ fetchAndExpand, focusNode, clearGraph, setSeedNode: markSeed, applyMaxExpansions, nodeMap, nodeCount });
</script>

<style scoped>
.graph-container { position: relative; width: 100%; height: 100%; background: #f8f9fa; }
.graph-canvas { width: 100%; height: 100%; }
.graph-overlay { position: absolute; inset: 0; pointer-events: none; z-index: 5; }
.graph-overlay > * { pointer-events: auto; }
.zoom-controls { position: absolute; right: 16px; bottom: 16px; display: grid; gap: 8px; justify-items: center; background: rgba(255,255,255,0.56); border: 1px solid rgba(255,255,255,0.62); border-radius: 14px; padding: 8px; backdrop-filter: blur(5px); box-shadow: 0 8px 22px rgba(19,43,41,0.14); }
.zoom-controls .icon-btn { width: 34px; height: 34px; border-radius: 10px; border: 0; background: rgba(255,255,255,0.78); cursor: pointer; color: #30474e; display: flex; align-items: center; justify-content: center; transition: transform 0.16s, background-color 0.2s, box-shadow 0.2s; }
.zoom-controls .icon-btn:hover { transform: translateY(-1px); background: rgba(0,121,107,0.14); box-shadow: 0 4px 12px rgba(0,121,107,0.2); }
.zoom-controls .icon-btn svg { width: 16px; height: 16px; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; fill: none; }
.year-legend { position: absolute; left: 16px; bottom: 16px; width: 200px; }
.year-legend-labels { display: flex; justify-content: space-between; font-size: 10px; color: #4b5b62; }
.year-bar { width: 100%; height: 4px; border-radius: 999px; background: linear-gradient(90deg, #c9f4ee, #00796b); }
.graph-loading, .graph-empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; pointer-events: none; }
.graph-loading { background: rgba(248,249,250,0.78); }
.taiji-spinner { position: relative; width: 56px; height: 56px; border-radius: 50%; background: linear-gradient(90deg, #0f2f2a 50%, #f4f0e6 50%); box-shadow: 0 10px 20px rgba(15,25,22,0.18); animation: taiji-spin 1.6s linear infinite; }
.taiji-spinner::before, .taiji-spinner::after { content: ""; position: absolute; left: 50%; width: 28px; height: 28px; border-radius: 50%; transform: translateX(-50%); }
.taiji-spinner::before { top: 0; background: #f4f0e6; }
.taiji-spinner::after { bottom: 0; background: #0f2f2a; }
.taiji-dot { position: absolute; top: 14px; left: 50%; width: 8px; height: 8px; border-radius: 50%; background: #0f2f2a; transform: translateX(-50%); box-shadow: 0 20px 0 0 #f4f0e6; }
.loading-text { font-size: 12px; color: #50636a; }
.graph-empty { background: linear-gradient(180deg, rgba(255,255,255,0.8), rgba(255,255,255,0.95)); }
.empty-art { position: relative; width: 84px; height: 84px; }
.empty-ring { position: absolute; inset: 0; border-radius: 50%; border: 1px dashed rgba(0,121,107,0.35); }
.empty-dot { position: absolute; width: 14px; height: 14px; border-radius: 50%; background: rgba(0,121,107,0.55); top: 14px; left: 18px; box-shadow: 32px 36px 0 rgba(126,58,242,0.35); }
.empty-wave { position: absolute; left: 10px; right: 10px; bottom: 18px; height: 16px; border-radius: 999px; background: linear-gradient(90deg, rgba(0,121,107,0.05), rgba(0,121,107,0.2), rgba(0,121,107,0.05)); }
@keyframes taiji-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
