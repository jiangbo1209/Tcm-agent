<template>
  <div class="graph-page">
    <aside class="graph-sidebar">
      <div class="graph-sidebar-header">
        <h2>节点列表</h2>
        <p class="graph-sidebar-sub">{{ graphRef?.nodeCount || 0 }} 个节点</p>
      </div>
      <div class="graph-search-wrap">
        <input v-model="searchQuery" class="input-field" placeholder="搜索关键词..." @keydown.enter="handleSearch" />
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
    </aside>
    <section class="graph-main">
      <GraphView ref="graphRef" @nodeClick="handleNodeClick" @nodeHover="handleNodeHover" />
    </section>
    <aside class="graph-detail-panel">
      <NodeDetail :nodeId="selectedNodeId" />
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import GraphView from "../components/GraphView.vue";
import NodeDetail from "../components/NodeDetail.vue";
import { searchGraph } from "../api/graph";

const route = useRoute();
const graphRef = ref(null);
const searchQuery = ref("");
const suggestItems = ref([]);
const selectedNodeId = ref("");
let suggestTimer = null;

const nodeList = computed(() => {
  if (!graphRef.value) return [];
  const map = graphRef.value.nodeMap || new Map();
  return Array.from(map.values()).sort((a, b) => {
    if (a.node_type !== b.node_type) return a.node_type.localeCompare(b.node_type);
    return String(a.title || a.id).localeCompare(String(b.title || b.id));
  });
});

async function handleSearch() {
  const q = searchQuery.value.trim();
  if (!q) return;
  suggestItems.value = [];
  if (graphRef.value) {
    graphRef.value.clearGraph();
    await graphRef.value.fetchAndExpand(q);
  }
}

function handleSuggestClick(item) {
  suggestItems.value = [];
  searchQuery.value = item.title || "";
  if (graphRef.value && item.node_id) {
    graphRef.value.fetchAndExpand(item.node_id);
    graphRef.value.focusNode(item.node_id);
    selectedNodeId.value = item.node_id;
  }
}

function handleNodeClick(model) {
  selectedNodeId.value = model.id;
}

function handleNodeHover(model) {
  // Could add hover preview if needed
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
  suggestTimer = setTimeout(async () => {
    try {
      const { data } = await searchGraph(q, 1, 6);
      suggestItems.value = data.items || [];
    } catch { suggestItems.value = []; }
  }, 280);
}

function onSearchInput() {
  scheduleSuggest();
}

// Watch searchQuery for suggest
watch(searchQuery, () => onSearchInput());

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
</script>

<style scoped>
.graph-page { display: flex; height: 100%; overflow: hidden; }
.graph-sidebar { width: 240px; min-width: 240px; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
.graph-sidebar-header { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.graph-sidebar-header h2 { margin: 0; font-size: 14px; color: var(--ink-900); }
.graph-sidebar-sub { margin: 4px 0 0; font-size: 12px; color: var(--ink-500); }
.graph-search-wrap { padding: 10px 12px; position: relative; }
.graph-search-wrap .input-field { font-size: 13px; padding: 8px 12px; }
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
.graph-detail-panel { width: 320px; min-width: 320px; background: var(--panel); border-left: 1px solid var(--border); }
</style>
