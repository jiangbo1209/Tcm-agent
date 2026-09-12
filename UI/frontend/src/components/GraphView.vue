<template>
  <div class="graph-container">
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
    <div v-if="errorMessage && !loading" class="graph-error" role="alert">
      <span>{{ errorMessage }}</span>
      <button type="button" @click="errorMessage = ''">关闭</button>
    </div>
    <div v-if="!loading && nodeCount === 0" class="graph-empty">
      <div class="empty-art"><span class="empty-ring"></span><span class="empty-dot"></span><span class="empty-wave"></span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { Graph, NodeEvent } from "@antv/g6";
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

const emit = defineEmits(["nodeClick"]);
const props = defineProps({ maxExpansions: { type: Number, default: 3 } });
const graphRef = ref(null);
const loading = ref(false);
const errorMessage = ref("");
const nodeCount = ref(0);
const visibleNodeList = ref([]);

let graph = null;
let activeSeedNodeId = null;
const nodeMap = new Map();
const edgeMap = new Map();
const inFlightSeeds = new Map();
const expandedSeeds = new Set();
const expansionHistory = [];
let visibleLimit = 3;
let graphGeneration = 0;
let layoutGeneration = 0;

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
function normalize(v, d) { const s = Number.isFinite(v) ? v : d[0]; return d[0] === d[1] ? 0.5 : (clamp(s, d[0], d[1]) - d[0]) / (d[1] - d[0]); }
function mapNodeSize(topK) { return Math.round(20 + normalize(topK, SIZE_DOMAIN) * 52); }
function truncateLabel(t, m) { const r = String(t || "").trim(); return r.length <= m ? r : `${r.slice(0, m - 1)}…`; }
function hexToRgb(h) { let n = String(h || "").replace("#", "").trim(); if (n.length === 3) n = n.split("").map(c => c + c).join(""); if (!/^[0-9a-fA-F]{6}$/.test(n)) return { r: 0, g: 0, b: 0 }; return { r: parseInt(n.slice(0, 2), 16), g: parseInt(n.slice(2, 4), 16), b: parseInt(n.slice(4, 6), 16) }; }
function mixColor(a, b, t) { const fa = hexToRgb(a), fb = hexToRgb(b), p = clamp(Number.isFinite(t) ? t : 0, 0, 1); return `rgb(${Math.round(fa.r + (fb.r - fa.r) * p)},${Math.round(fa.g + (fb.g - fa.g) * p)},${Math.round(fa.b + (fb.b - fa.b) * p)})`; }
function mapNodeColor(type, year, age) { return type === "paper" ? mixColor("#c9f4ee", "#00796b", normalize(year, YEAR_DOMAIN)) : mixColor("#fff2b3", "#b86a00", normalize(age, AGE_DOMAIN)); }
function mapDistance(s) { return Math.round(DISTANCE_RANGE[1] - clamp(Number(s) || 0, 0, 1) * (DISTANCE_RANGE[1] - DISTANCE_RANGE[0])); }
function mapEdgeOpacity(s) { return Number((0.25 + clamp(Number(s) || 0, 0, 1) * 0.65).toFixed(3)); }

/* ── v5 data mappers ────────────────────────────────────────── */

function mapNode(raw) {
  const nt = raw.node_type === "paper" ? "paper" : "record";
  const topK = Number(raw.top_k_value);
  const py = Number(raw.publish_year ?? raw.metric_value);
  const age = Number(raw.age ?? raw.metric_value);
  const size = mapNodeSize(topK);
  const full = raw.title || String(raw.id);
  const short = truncateLabel(full, LABEL_MAX_CHARS);

  const node = {
    id: String(raw.id),
    type: nt === "paper" ? "circle" : "rect",
    data: {
      id: String(raw.id),
      node_type: nt, title: raw.title || String(raw.id),
      full_label: full, short_label: short,
      metric_value: Number(raw.metric_value),
      publish_year: Number.isFinite(py) ? py : null,
      age: Number.isFinite(age) ? age : null,
      top_k_value: Number.isFinite(topK) ? topK : null,
    },
    style: {
      fill: mapNodeColor(nt, py, age),
      size: nt === "paper" ? size : [size, size],
      stroke: DEFAULT_NODE_STROKE,
      lineWidth: 1,
      cursor: "pointer",
      labelText: short,
      labelFill: "#153a47",
      labelFontSize: 11,
      labelFontWeight: 400,
      labelPlacement: "bottom",
      labelOffsetY: 7,
      labelBackground: true,
      labelBackgroundFill: "rgba(255,255,255,0.52)",
      labelBackgroundRadius: 4,
      labelBackgroundLineWidth: 0,
      labelPadding: [1, 2],
      opacity: 1,
    },
  };

  const x = Number(raw.x);
  const y = Number(raw.y);
  if (Number.isFinite(x)) node.style.x = x;
  if (Number.isFinite(y)) node.style.y = y;
  return node;
}

function mapEdge(raw) {
  const rawType = String(raw.edge_type || "paper-paper");
  const et = rawType === "record-paper" || rawType === "ref" ? "paper-record" : rawType;
  const score = clamp(Number(raw.similarity_score) || 0, 0, 1);
  const op = mapEdgeOpacity(score);
  let lw, ld;
  if (et === "paper-record") { lw = 3.4 + score * 1.4; ld = null; }
  else if (et === "record-record") { lw = 1.5 + score * 0.7; ld = [7, 5]; }
  else { lw = 1 + score * 0.6; ld = null; }
  return {
    id: String(raw.id || `${raw.source}->${raw.target}|${et}`),
    source: String(raw.source),
    target: String(raw.target),
    data: { edge_type: et, similarity_score: score, base_opacity: op },
    style: { stroke: EDGE_BASE_COLOR, lineWidth: lw, lineDash: ld, opacity: op, endArrow: false },
  };
}

/* ── v5 style helpers (operate on data, not DOM items) ────── */

function applyNodeBaseStyle(nodeData) {
  const d = nodeData.data || {};
  const isSeed = activeSeedNodeId && nodeData.id === activeSeedNodeId;
  const updates = {
    id: nodeData.id,
    style: {
      stroke: isSeed ? SEED_NODE_STROKE : DEFAULT_NODE_STROKE,
      lineWidth: isSeed ? 4 : 1,
      opacity: 1,
      labelText: isSeed ? (d.full_label || nodeData.style?.labelText) : (d.short_label || nodeData.style?.labelText),
    },
  };
  return updates;
}

function applyEdgeBaseStyle(edgeData) {
  const d = edgeData.data || {};
  return {
    id: edgeData.id,
    style: {
      stroke: EDGE_BASE_COLOR,
      opacity: Number.isFinite(d.base_opacity) ? d.base_opacity : 0.5,
    },
  };
}

function resetHover() {
  if (!graph) return;
  const allNodes = graph.getNodeData();
  const allEdges = graph.getEdgeData();
  const nodeUpdates = allNodes.map(n => applyNodeBaseStyle(n));
  const edgeUpdates = allEdges.map(e => applyEdgeBaseStyle(e));
  if (nodeUpdates.length) graph.updateNodeData(nodeUpdates);
  if (edgeUpdates.length) graph.updateEdgeData(edgeUpdates);
  if (nodeUpdates.length || edgeUpdates.length) graph.draw();
}

function applyHover(focusNodeId) {
  if (!focusNodeId || !graph) { resetHover(); return; }
  const allNodes = graph.getNodeData();
  const allEdges = graph.getEdgeData();

  // Collect related node IDs from edges
  const related = new Set([focusNodeId]);
  const relatedEdgeIds = new Set();
  for (const e of allEdges) {
    if (e.source === focusNodeId || e.target === focusNodeId) {
      relatedEdgeIds.add(e.id);
      related.add(e.source);
      related.add(e.target);
    }
  }

  const nodeUpdates = allNodes.map(n => {
    const id = n.id;
    if (!related.has(id)) {
      return { id, style: { opacity: 0.1, labelText: n.style?.labelText } };
    }
    const d = n.data || {};
    const isSeed = activeSeedNodeId && id === activeSeedNodeId;
    if (isSeed) {
      return { id, style: { stroke: SEED_NODE_STROKE, lineWidth: 4, opacity: 1, labelText: d.full_label || n.style?.labelText } };
    }
    return { id, style: { stroke: HOVER_NODE_STROKE, lineWidth: id === focusNodeId ? 3 : 2, opacity: 1, labelText: d.full_label || n.style?.labelText } };
  });

  const edgeUpdates = allEdges.map(e => {
    const d = e.data || {};
    const base = Number.isFinite(d.base_opacity) ? d.base_opacity : 0.5;
    const connected = relatedEdgeIds.has(e.id);
    return { id: e.id, style: { stroke: EDGE_BASE_COLOR, opacity: connected ? Math.min(1, base + 0.18) : Math.max(0.04, base * 0.2) } };
  });

  if (nodeUpdates.length) graph.updateNodeData(nodeUpdates);
  if (edgeUpdates.length) graph.updateEdgeData(edgeUpdates);
  if (nodeUpdates.length || edgeUpdates.length) graph.draw();
}

function markSeed(id) {
  if (!graph) return;
  const normalizedId = String(id);
  const previousSeedId = activeSeedNodeId;
  activeSeedNodeId = normalizedId;

  // Clear old seed style
  if (previousSeedId && previousSeedId !== normalizedId && graph.hasNode(previousSeedId)) {
    const prevData = graph.getNodeData(previousSeedId);
    if (prevData) {
      const updates = applyNodeBaseStyle(prevData);
      graph.updateNodeData([updates]);
    }
  }

  // Apply seed style
  const curData = graph.hasNode(normalizedId) ? graph.getNodeData(normalizedId) : null;
  if (curData) {
    const updates = applyNodeBaseStyle(curData);
    graph.updateNodeData([updates]);
    graph.draw();
  }
}

/* ── data merge & render ─────────────────────────────────── */

function mergeGraph(payload) {
  const inN = Array.isArray(payload.nodes) ? payload.nodes.map(mapNode) : [];
  const inE = Array.isArray(payload.edges) ? payload.edges.map(mapEdge) : [];
  inN.forEach(n => {
    const existing = nodeMap.get(n.id);
    if (existing) {
      if (n.style && existing.style) {
        if (!Number.isFinite(n.style.x) && Number.isFinite(existing.style.x)) n.style.x = existing.style.x;
        if (!Number.isFinite(n.style.y) && Number.isFinite(existing.style.y)) n.style.y = existing.style.y;
      }
    }
    nodeMap.set(n.id, n);
  });
  const validE = inE.filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));
  validE.forEach(e => edgeMap.set(e.id, e));

  return {
    nodeIds: inN.map(n => n.id),
    edgeIds: validE.map(e => e.id),
  };
}

function syncNodePositions() {
  if (!graph) return;
  const allNodes = graph.getNodeData();
  for (const nd of allNodes) {
    const node = nodeMap.get(String(nd.id));
    if (!node) continue;
    const x = Number(nd.style?.x);
    const y = Number(nd.style?.y);
    if (Number.isFinite(x) && node.style) node.style.x = x;
    if (Number.isFinite(y) && node.style) node.style.y = y;
  }
}

function getVisibleIds(limit) {
  if (limit <= 0 || expansionHistory.length === 0) {
    return { nodeIds: new Set(), edgeIds: new Set() };
  }
  const limited = expansionHistory.slice(-limit);
  const nodeIds = new Set();
  const edgeIds = new Set();
  for (const exp of limited) {
    exp.nodeIds.forEach(id => nodeIds.add(id));
    exp.edgeIds.forEach(id => edgeIds.add(id));
  }
  if (activeSeedNodeId) nodeIds.add(activeSeedNodeId);
  return { nodeIds, edgeIds };
}

async function renderCurrentGraph({ relayout = false } = {}) {
  if (!graph) return;
  syncNodePositions();

  const { nodeIds, edgeIds } = getVisibleIds(visibleLimit);
  const visibleNodes = Array.from(nodeMap.values()).filter(n => nodeIds.has(n.id));
  const visibleEdges = Array.from(edgeMap.values()).filter(e =>
    edgeIds.has(e.id) && nodeIds.has(e.source) && nodeIds.has(e.target)
  );

  // v5: setData + draw instead of changeData
  graph.setData({ nodes: visibleNodes, edges: visibleEdges });
  await graph.draw();
  nodeCount.value = visibleNodes.length;
  visibleNodeList.value = visibleNodes.map((node) => ({
    id: node.id,
    ...(node.data || {}),
  }));

  if (activeSeedNodeId && graph.hasNode(activeSeedNodeId)) {
    const nd = graph.getNodeData(activeSeedNodeId);
    if (nd) {
      const updates = applyNodeBaseStyle(nd);
      graph.updateNodeData([updates]);
      await graph.draw();
    }
  }
  if (relayout) await runLayout();
}

async function applyExpansionLimit({ relayout = false } = {}) {
  visibleLimit = Math.max(0, Number(props.maxExpansions) || 0);
  await renderCurrentGraph({ relayout });
}

async function fetchAndExpand(seedId) {
  const normalizedSeedId = String(seedId || "").trim();
  if (!normalizedSeedId || expandedSeeds.has(normalizedSeedId)) return true;
  if (inFlightSeeds.has(normalizedSeedId)) return inFlightSeeds.get(normalizedSeedId).promise;

  const requestGeneration = graphGeneration;
  const requestToken = Symbol(normalizedSeedId);
  let resolveRequest;
  const requestPromise = new Promise(resolve => { resolveRequest = resolve; });
  inFlightSeeds.set(normalizedSeedId, { token: requestToken, promise: requestPromise });
  loading.value = inFlightSeeds.size > 0;
  errorMessage.value = "";

  let succeeded = false;
  try {
    const { data } = await expandGraph(normalizedSeedId);
    if (requestGeneration !== graphGeneration || !graph) return false;

    const centerX = graphRef.value?.clientWidth / 2 || 400;
    const centerY = graphRef.value?.clientHeight / 2 || 300;

    // Give new nodes initial positions around the seed
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

    expansionHistory.push({ seedId: String(seedId), nodeIds: new Set(nodeIds), edgeIds: new Set(edgeIds) });

    // Place seed node at center
    const seedNode = nodeMap.get(normalizedSeedId);
    if (seedNode && seedNode.style) {
      seedNode.style.x = centerX;
      seedNode.style.y = centerY;
    }

    await applyExpansionLimit();
    if (requestGeneration !== graphGeneration || !graph) return false;

    // Run one settled layout. Duplicate clicks do not restart the simulation.
    await runLayout();
    if (requestGeneration !== graphGeneration || !graph) return false;
    if (nodeMap.has(normalizedSeedId)) markSeed(normalizedSeedId);

    await graph.fitView({ when: "always", direction: "both" }, { easing: "easeCubic", duration: 260 });
    expandedSeeds.add(normalizedSeedId);
    succeeded = true;
    return true;
  } catch (error) {
    console.error("Failed to expand graph", error);
    if (requestGeneration === graphGeneration) {
      errorMessage.value = error?.response?.data?.detail || "图谱加载失败，请稍后重试";
    }
    return false;
  } finally {
    const currentRequest = inFlightSeeds.get(normalizedSeedId);
    if (currentRequest?.token === requestToken) inFlightSeeds.delete(normalizedSeedId);
    loading.value = inFlightSeeds.size > 0;
    resolveRequest(succeeded);
  }
}

async function runLayout() {
  if (!graph || graph.getNodeData().length === 0) return;
  const currentLayoutGeneration = ++layoutGeneration;
  graph.stopLayout();
  await graph.layout();
  if (currentLayoutGeneration === layoutGeneration) syncNodePositions();
}

function zoomIn() { return graph?.zoomBy(1.12, { easing: "easeCubic", duration: 160 }); }
function zoomOut() { return graph?.zoomBy(0.9, { easing: "easeCubic", duration: 160 }); }
function fitView() { return graph?.fitView({ when: "always", direction: "both" }, { easing: "easeCubic", duration: 220 }); }
async function focusNode(id) {
  const normalizedId = String(id || "").trim();
  if (!graph || !normalizedId || !graph.hasNode(normalizedId)) return false;
  await graph.focusElement(normalizedId, { easing: "easeCubic", duration: 300 });
  return true;
}
function clearGraph() {
  graphGeneration += 1;
  layoutGeneration += 1;
  graph?.stopLayout();
  activeSeedNodeId = null;
  nodeMap.clear();
  edgeMap.clear();
  inFlightSeeds.clear();
  expandedSeeds.clear();
  expansionHistory.length = 0;
  nodeCount.value = 0;
  visibleNodeList.value = [];
  visibleLimit = Math.max(0, Number(props.maxExpansions) || 0);
  errorMessage.value = "";
  if (graph) {
    graph.setData({ nodes: [], edges: [] });
    void graph.draw();
  }
}
function applyMaxExpansions() { return applyExpansionLimit({ relayout: true }); }
function handleWindowResize() { if (graph) graph.resize(); }

/* ── lifecycle ────────────────────────────────────────────── */

onMounted(async () => {
  const container = graphRef.value;
  if (!container) return;

  graph = new Graph({
    container,
    data: { nodes: [], edges: [] },
    node: {
      style: {
        labelText: (d) => d.data?.short_label || d.data?.title || d.id,
        labelFill: "#153a47",
        labelFontSize: 11,
        labelFontWeight: 400,
        labelPlacement: "bottom",
        labelOffsetY: 7,
        labelBackground: true,
        labelBackgroundFill: "rgba(255,255,255,0.52)",
        labelBackgroundRadius: 4,
        labelBackgroundLineWidth: 0,
        labelPadding: [1, 2],
        fill: "#e6edf5",
        stroke: DEFAULT_NODE_STROKE,
        lineWidth: 1,
        cursor: "pointer",
      },
    },
    edge: {
      style: {
        stroke: EDGE_BASE_COLOR,
        opacity: 0.5,
      },
    },
    behaviors: ["zoom-canvas", "drag-canvas", "drag-element"],
    layout: {
      type: "force",
      animation: false,
      iterations: 220,
      preventOverlap: true,
      linkDistance: (edge) => mapDistance(edge.data?.similarity_score),
      nodeSize: (node) => {
        const size = node.style?.size;
        return Array.isArray(size) ? Math.max(...size) : Number(size) || 30;
      },
      nodeStrength: 800,
      edgeStrength: 50,
      collideStrength: 0.8,
      damping: 0.82,
      minMovement: 0.8,
    },
  });

  await graph.render();

  // v5 events: NodeEvent.CLICK replaces "node:click"
  graph.on(NodeEvent.CLICK, (evt) => {
    const { target } = evt;
    const nodeId = target?.id;
    if (!nodeId) return;
    const nodeData = graph.getNodeData(nodeId);
    if (!nodeData) return;
    markSeed(nodeId);
    emit("nodeClick", { id: nodeData.id, ...(nodeData.data || {}) });
    void fetchAndExpand(nodeId);
  });

  graph.on(NodeEvent.POINTER_ENTER, (evt) => {
    const { target } = evt;
    const nodeId = target?.id;
    if (!nodeId) return;
    applyHover(nodeId);
  });

  graph.on(NodeEvent.POINTER_LEAVE, () => {
    resetHover();
  });

  // v5: resize() instead of changeSize()
  window.addEventListener("resize", handleWindowResize);
});

onBeforeUnmount(() => {
  graphGeneration += 1;
  layoutGeneration += 1;
  window.removeEventListener("resize", handleWindowResize);
  graph?.stopLayout();
  graph?.destroy();
  graph = null;
});

defineExpose({ fetchAndExpand, focusNode, clearGraph, setSeedNode: markSeed, applyMaxExpansions, nodeCount, visibleNodeList });
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
.graph-error { position: absolute; left: 50%; top: 16px; z-index: 8; transform: translateX(-50%); display: flex; align-items: center; gap: 12px; max-width: min(520px, calc(100% - 32px)); padding: 9px 12px; border: 1px solid rgba(185,28,28,0.2); border-radius: 10px; background: rgba(255,247,247,0.96); color: #991b1b; font-size: 12px; box-shadow: 0 8px 20px rgba(80,20,20,0.12); }
.graph-error button { border: 0; background: transparent; color: inherit; cursor: pointer; font-size: 12px; }
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
