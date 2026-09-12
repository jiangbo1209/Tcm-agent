<template>
  <div class="graph-page">
    <aside class="graph-sidebar" :style="{ width: `${nodeSidebarWidth}px`, minWidth: `${nodeSidebarWidth}px` }">
      <div class="graph-sidebar-header">
        <h2>节点列表</h2>
        <p class="graph-sidebar-sub">{{ graphRef?.nodeCount || 0 }} 个节点</p>
      </div>
      <div class="graph-search-wrap">
        <input v-model="searchQuery" class="input-field" placeholder="搜索关键词..." @keydown.enter="handleSearch" />
        <div v-if="searchError" class="search-error">{{ searchError }}</div>
        <div v-if="suggestItems.length" class="suggest-dropdown">
          <button v-for="item in suggestItems" :key="item.node_id" class="suggest-item" @click="handleSuggestClick(item)">
            <span class="suggest-title">{{ item.title || "未命名" }}</span>
            <span class="suggest-tag">{{ item.source_type === "record" ? "病案" : "文献" }}</span>
          </button>
        </div>
      </div>
      <div class="node-list">
        <div v-for="node in nodeList" :key="node.id" class="node-item" :class="{ active: selectedNodeId === node.id }" @click="handleNodeSelect(node)">
          <span class="node-type-chip" :class="node.node_type">{{ node.node_type === "record" ? "病案" : "文献" }}</span>
          <span class="node-title">{{ node.title || node.id }}</span>
        </div>
        <div v-if="nodeList.length === 0" class="node-empty">暂无节点</div>
      </div>
      <div class="graph-sidebar-resizer" @pointerdown="startNodeSidebarResize"></div>
    </aside>
    <section class="graph-main">
      <GraphView ref="graphRef" :maxExpansions="maxExpansions" @nodeClick="handleNodeClick" />
    </section>
    <aside class="graph-detail-panel">
      <div class="detail-controls">
        <label class="control-label">
          <span>保留扩展层数</span>
          <span class="control-value">{{ maxExpansions }}</span>
        </label>
        <input type="range" v-model.number="maxExpansions" min="0" max="10" step="1" class="slider" @input="onMaxExpansionsChange" />
        <div class="slider-labels"><span>0</span><span>5</span><span>10</span></div>
      </div>
      <NodeDetail :nodeId="selectedNodeId" />
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute } from "vue-router";
import GraphView from "../../../components/GraphView.vue";
import NodeDetail from "../../../components/NodeDetail.vue";
import { searchGraph } from "../../../api/graph";

const route = useRoute();
const graphRef = ref(null);
const searchQuery = ref("");
const suggestItems = ref([]);
const searchError = ref("");
const selectedNodeId = ref("");
const maxExpansions = ref(3);
const nodeSidebarWidth = ref(240);
let suggestTimer = null;
let resizeStartX = 0;
let resizeStartWidth = 240;
let suggestRequestId = 0;
let suppressNextSuggest = false;

const nodeList = computed(() => {
  if (!graphRef.value) return [];
  return [...(graphRef.value.visibleNodeList || [])].sort((a, b) => {
    if (a.node_type !== b.node_type) return a.node_type.localeCompare(b.node_type);
    return String(a.title || a.id).localeCompare(String(b.title || b.id));
  });
});

async function handleSearch() {
  const q = searchQuery.value.trim();
  if (!q) return;
  clearTimeout(suggestTimer);
  const requestId = ++suggestRequestId;
  suggestItems.value = [];
  searchError.value = "";
  try {
    const { data } = await searchGraph(q, 1, 1);
    if (requestId !== suggestRequestId) return;
    const match = data.items?.[0];
    if (!match?.node_id) {
      searchError.value = "没有找到匹配节点";
      return;
    }
    await openSearchResult(match, { replaceGraph: true });
  } catch (error) {
    if (requestId !== suggestRequestId) return;
    searchError.value = error?.response?.data?.detail || "搜索失败，请稍后重试";
  }
}

async function openSearchResult(item, { replaceGraph = false } = {}) {
  if (!graphRef.value || !item?.node_id) return;
  const nodeId = String(item.node_id);
  if (replaceGraph) graphRef.value.clearGraph();
  selectedNodeId.value = nodeId;
  const loaded = await graphRef.value.fetchAndExpand(nodeId);
  if (loaded) await graphRef.value.focusNode(nodeId);
}

async function handleSuggestClick(item) {
  clearTimeout(suggestTimer);
  suggestRequestId += 1;
  suggestItems.value = [];
  searchError.value = "";
  suppressNextSuggest = true;
  searchQuery.value = item.title || "";
  await openSearchResult(item, { replaceGraph: true });
}

function handleNodeClick(model) {
  selectedNodeId.value = String(model.id || "");
}

function handleNodeSelect(node) {
  selectedNodeId.value = node.id;
  if (graphRef.value) {
    graphRef.value.setSeedNode(node.id);
    graphRef.value.focusNode(node.id);
  }
}

// Debounced suggest
function scheduleSuggest() {
  const q = searchQuery.value.trim();
  if (q.length < 2) { suggestItems.value = []; return; }
  clearTimeout(suggestTimer);
  const requestId = ++suggestRequestId;
  suggestTimer = setTimeout(async () => {
    try {
      const { data } = await searchGraph(q, 1, 6);
      if (requestId === suggestRequestId && q === searchQuery.value.trim()) {
        suggestItems.value = data.items || [];
      }
    } catch {
      if (requestId === suggestRequestId) suggestItems.value = [];
    }
  }, 280);
}

function onMaxExpansionsChange() {
  if (graphRef.value) graphRef.value.applyMaxExpansions();
}

function clampWidth(value) {
  return Math.max(180, Math.min(420, value));
}

function refreshGraphSize() {
  requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
}

function onNodeSidebarResize(event) {
  nodeSidebarWidth.value = clampWidth(resizeStartWidth + event.clientX - resizeStartX);
  refreshGraphSize();
}

function stopNodeSidebarResize() {
  window.removeEventListener("pointermove", onNodeSidebarResize);
  window.removeEventListener("pointerup", stopNodeSidebarResize);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
}

function startNodeSidebarResize(event) {
  resizeStartX = event.clientX;
  resizeStartWidth = nodeSidebarWidth.value;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("pointermove", onNodeSidebarResize);
  window.addEventListener("pointerup", stopNodeSidebarResize);
}

// Watch searchQuery for suggest
watch(searchQuery, () => {
  searchError.value = "";
  if (suppressNextSuggest) {
    suppressNextSuggest = false;
    return;
  }
  scheduleSuggest();
});

// Auto-expand from route query seed
onMounted(() => {
  const seed = route.query.seed;
  if (seed && graphRef.value) {
    selectedNodeId.value = seed;
    graphRef.value.fetchAndExpand(seed);
  }
});

watch(() => route.query.seed, (seed) => {
  if (seed && graphRef.value) {
    selectedNodeId.value = seed;
    graphRef.value.fetchAndExpand(seed);
  }
});

onBeforeUnmount(() => {
  clearTimeout(suggestTimer);
  suggestRequestId += 1;
  stopNodeSidebarResize();
});
</script>

<style scoped>
.graph-page { display: flex; height: 100%; overflow: hidden; }
.graph-sidebar { position: relative; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
.graph-sidebar-resizer { position: absolute; top: 0; right: -4px; width: 8px; height: 100%; cursor: col-resize; z-index: 10; }
.graph-sidebar-resizer:hover { background: rgba(0,121,107,0.12); }
.graph-sidebar-header { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.graph-sidebar-header h2 { margin: 0; font-size: 14px; color: var(--ink-900); }
.graph-sidebar-sub { margin: 4px 0 0; font-size: 12px; color: var(--ink-500); }
.graph-search-wrap { padding: 10px 12px; position: relative; }
.graph-search-wrap .input-field { font-size: 13px; padding: 8px 12px; }
.search-error { margin-top: 6px; padding: 0 2px; color: #b42318; font-size: 12px; }
.suggest-dropdown { position: absolute; left: 12px; right: 12px; top: 100%; z-index: 20; background: var(--panel); border: 1px solid var(--border); border-radius: 10px; box-shadow: 0 8px 20px rgba(15,25,22,0.12); padding: 4px; }
.suggest-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none; background: transparent; text-align: left; cursor: pointer; border-radius: 8px; font-size: 13px; }
.suggest-item:hover { background: rgba(0,121,107,0.08); }
.suggest-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.suggest-tag { font-size: 11px; font-weight: 600; color: var(--teal); background: rgba(0,121,107,0.1); padding: 1px 6px; border-radius: 999px; }
.node-list { flex: 1; overflow-y: auto; padding: 8px; }
.node-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--ink-700); transition: background-color 0.2s; }
.node-item:hover { background: rgba(0,121,107,0.06); }
.node-item.active { background: rgba(0,121,107,0.15); color: var(--teal); }
.node-type-chip { font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 999px; }
.node-type-chip.paper { background: rgba(0,121,107,0.1); color: var(--teal); }
.node-type-chip.record { background: rgba(199,124,2,0.15); color: #b06a00; }
.node-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-empty { padding: 20px; text-align: center; font-size: 13px; color: var(--ink-500); }
.graph-main { flex: 1; min-width: 0; }
.graph-detail-panel { width: 320px; min-width: 320px; background: var(--panel); border-left: 1px solid var(--border); display: flex; flex-direction: column; }
.detail-controls { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.control-label { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--ink-700); font-weight: 500; margin-bottom: 8px; }
.control-value { font-weight: 600; color: var(--teal); }
.slider { width: 100%; height: 6px; -webkit-appearance: none; appearance: none; background: var(--border); border-radius: 999px; outline: none; cursor: pointer; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%; background: var(--teal); cursor: pointer; box-shadow: 0 2px 6px rgba(0,121,107,0.3); }
.slider::-moz-range-thumb { width: 18px; height: 18px; border-radius: 50%; background: var(--teal); cursor: pointer; border: none; }
.slider-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-500); margin-top: 4px; }
</style>
