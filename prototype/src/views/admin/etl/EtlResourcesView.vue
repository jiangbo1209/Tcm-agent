<template>
  <div class="resources-page">
    <section class="page-head">
      <div>
        <h2>资源管理</h2>
        <p class="desc">抽取资源全生命周期 · 待抽取 / 抽取中 / 抽取失败 / 已完成</p>
      </div>
    </section>

    <div class="toolbar">
      <select
        v-model="batchAction"
        class="filter-select batch-select"
        :disabled="selectedIds.size === 0"
        :title="selectedIds.size === 0 ? '请先勾选资源' : '批量操作'"
        @change="applyBatchAction"
      >
        <option value="" disabled hidden>{{ selectedIds.size > 0 ? `批量操作（${selectedIds.size}）` : "批量操作" }}</option>
        <option v-for="a in batchActions" :key="a.key" :value="a.key">{{ a.label }}</option>
      </select>
      <select v-model="stateFilter" class="filter-select">
        <option value="">全部状态（{{ countOf('all') }}）</option>
        <option v-for="s in stateOptions" :key="s.key" :value="s.key">{{ s.label }}（{{ countOf(s.key) }}）</option>
      </select>
      <select v-model="filterKind" class="filter-select">
        <option value="">全部类型</option>
        <option value="lit">文献</option>
        <option value="case">病案</option>
      </select>
      <input v-model="searchQuery" class="filter-input" placeholder="搜索文档 / 编号..." />
      <button v-if="searchQuery" class="btn-clear" type="button" @click="searchQuery = ''">清除</button>
      <span class="result-count">共 {{ filtered.length }} 条</span>
    </div>


    <div class="table-wrap">
      <table class="pool-table">
        <thead>
          <tr>
            <th class="col-check">
              <input type="checkbox" class="row-check" :checked="allSelected" :disabled="filtered.length === 0" @change="toggleAll" />
            </th>
            <th>文档</th>
            <th class="col-kind">类型</th>
            <th class="col-state">状态</th>
            <th class="col-conf">置信度</th>
            <th v-if="stateFilter === 'failed' || stateFilter === ''">失败原因</th>
            <th class="col-time">更新时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in paged" :key="doc.id" :class="{ 'row-selected': selectedIds.has(doc.id) }">
            <td class="col-check">
              <input type="checkbox" class="row-check" :checked="selectedIds.has(doc.id)" @change="toggleOne(doc.id)" />
            </td>
            <td>
              <div class="doc-cell">
                <span class="doc-id">{{ doc.id }}</span>
                <span class="doc-name" :title="doc.name">{{ doc.name }}</span>
              </div>
            </td>
            <td><span class="badge" :class="doc.kind === 'lit' ? 'badge-teal' : 'badge-warn'">{{ doc.kind === "lit" ? "文献" : "病案" }}</span></td>
            <td><span class="badge" :class="stateCls(doc.state)">{{ stateLabel(doc.state) }}</span></td>
            <td><span class="conf" :class="confCls(doc.confidence)">{{ Math.round(doc.confidence * 100) }}%</span></td>
            <td v-if="stateFilter === 'failed' || stateFilter === ''" class="cell-error">{{ doc.errors[0]?.message || "—" }}</td>
            <td class="muted">{{ doc.uploadedAt }}</td>
            <td class="col-actions">
              <button class="btn-sm" @click="openDetail(doc)">详情</button>
              <button
                v-for="a in actionsOf(doc.state)"
                :key="a.key"
                class="btn-sm"
                :class="{ teal: a.primary }"
                @click="runAction(a, [doc.id])"
              >
                {{ a.label }}
              </button>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td :colspan="columns" class="empty-row">暂无资源</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pager-bar">
      <div class="page-size">
        <span>每页</span>
        <select v-model.number="pageSize" class="filter-select">
          <option v-for="n in PAGE_SIZES" :key="n" :value="n">{{ n }}</option>
        </select>
        <span>条</span>
      </div>
      <span class="page-info">第 {{ page }} / {{ pageCount }} 页 · 共 {{ filtered.length }} 条</span>
      <div class="pager-btns">
        <button class="btn-sm" :disabled="page <= 1" @click="page--">上一页</button>
        <button class="btn-sm" :disabled="page >= pageCount" @click="page++">下一页</button>
      </div>
    </div>

    <transition name="toast"><div v-if="toast.visible" class="toast">{{ toast.message }}</div></transition>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { etlStore, ETL_STATE_MAP } from "../../../stores/etl";

const router = useRouter();
const ETL_STATES_KEYS = ["pending", "extracting", "failed", "graphed"];

const stateOptions = ETL_STATES_KEYS.map((k) => ({ key: k, label: ETL_STATE_MAP[k].label }));

const stateFilter = ref("");
const filterKind = ref("");
const searchQuery = ref("");
const selectedIds = ref(new Set());
const batchAction = ref("");
const page = ref(1);
const pageSize = ref(10);
const PAGE_SIZES = [10, 20, 50, 100];

const toast = reactive({ visible: false, message: "" });
let timer = null;
function showToast(msg) {
  toast.message = msg;
  toast.visible = true;
  clearTimeout(timer);
  timer = setTimeout(() => (toast.visible = false), 2400);
}

const ACTIONS = {
  pending: [{ key: "start", label: "开始抽取", primary: true, from: ["pending"] }],
  extracting: [{ key: "cancel", label: "取消抽取", from: ["extracting"] }],
  failed: [
    { key: "retry", label: "重试", primary: true, from: ["failed"] },
    { key: "ignore", label: "忽略", from: ["failed"] },
  ],
  graphed: [{ key: "reextract", label: "重新抽取", from: ["graphed"] }],
};

const ACTIONS_BY_KEY = Object.values(ACTIONS).flat().reduce((acc, a) => {
  acc[a.key] = a;
  return acc;
}, {});

function actionsOf(state) {
  return ACTIONS[state] || [];
}

const selectedDocs = computed(() => etlStore.docs.filter((d) => selectedIds.value.has(d.id)));
const batchActions = computed(() => {
  if (selectedDocs.value.length === 0) return [];
  const states = [...new Set(selectedDocs.value.map((d) => d.state))];
  if (states.length === 1) return ACTIONS[states[0]] || [];
  const keys = new Set();
  states.forEach((st) => (ACTIONS[st] || []).forEach((a) => keys.add(a.key)));
  return [...keys].map((k) => ACTIONS_BY_KEY[k]);
});

const countOf = (key) => {
  if (key === "all") return ETL_STATES_KEYS.reduce((n, k) => n + (etlStore.counts.value[k] || 0), 0);
  return etlStore.counts.value[key] || 0;
};

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  const states = stateFilter.value ? [stateFilter.value] : ETL_STATES_KEYS;
  return etlStore.docs.filter((d) => {
    if (!states.includes(d.state)) return false;
    if (filterKind.value && d.kind !== filterKind.value) return false;
    if (q && !`${d.id} ${d.name}`.toLowerCase().includes(q)) return false;
    return true;
  });
});

const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)));
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filtered.value.slice(start, start + pageSize.value);
});
const allSelected = computed(
  () => paged.value.length > 0 && paged.value.every((d) => selectedIds.value.has(d.id)),
);
const columns = computed(() => {
  const showError = stateFilter.value === "failed" || stateFilter.value === "";
  return showError ? 7 : 6;
});

watch([stateFilter, filterKind, searchQuery, pageSize], () => {
  page.value = 1;
  selectedIds.value = new Set();
  batchAction.value = "";
});
watch(selectedIds, () => {
  batchAction.value = "";
});
watch(pageCount, (n) => {
  if (page.value > n) page.value = n;
});

function toggleOne(id) {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectedIds.value = next;
}
function toggleAll() {
  const next = new Set(selectedIds.value);
  const all = allSelected.value;
  for (const d of paged.value) {
    if (all) next.delete(d.id);
    else next.add(d.id);
  }
  selectedIds.value = next;
}

function stateLabel(s) {
  return ETL_STATE_MAP[s]?.label || s;
}
function stateCls(s) {
  if (s === "graphed") return "badge-ok";
  if (s === "failed") return "badge-danger";
  if (s === "pending") return "badge-muted";
  if (s === "extracting") return "badge-warn";
  return "badge-muted";
}
function confCls(v) {
  if (v >= 0.85) return "conf-high";
  if (v >= 0.65) return "conf-mid";
  return "conf-low";
}

function runAction(action, ids) {
  if (!ids.length) return;
  const allowed = new Set(action.from || []);
  const targetIds = ids.filter((id) => {
    const d = etlStore.get(id);
    return d && allowed.has(d.state);
  });
  if (!targetIds.length) return;
  const map = {
    start: () => { etlStore.startExtraction(targetIds); showToast(`已开始抽取 ${targetIds.length} 份`); },
    cancel: () => { etlStore.setState(targetIds, "pending", "取消抽取"); showToast("已取消抽取"); },
    retry: () => { etlStore.retry(targetIds); showToast(`已重试 ${targetIds.length} 份`); },
    ignore: () => { etlStore.ignore(targetIds); showToast(`已忽略 ${targetIds.length} 份`); },
    reextract: () => { etlStore.reextract(targetIds); showToast(`已加入重抽队列 ${targetIds.length} 份`); },
  };
  map[action.key]?.();
  selectedIds.value = new Set();
}

function applyBatchAction() {
  const action = batchActions.value.find((a) => a.key === batchAction.value);
  if (action) runAction(action, [...selectedIds.value]);
  batchAction.value = "";
}

function openDetail(doc) {
  const kind = doc.kind === "lit" ? "literature" : "case";
  router.push(`/admin/data?kind=${kind}&record=${doc.id}`);
}
</script>

<style scoped>
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.page-head h2 { margin: 0 0 4px; font-size: 16px; }
.desc { margin: 0; font-size: 12px; color: var(--ink-400); }

.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.btn-clear { padding: 7px 12px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; color: var(--ink-500); font-size: 12px; cursor: pointer; }
.btn-clear:hover { background: #f5f5f5; }
.result-count { font-size: 12px; color: var(--ink-400); margin-left: auto; white-space: nowrap; }

.batch-select { width: 132px; cursor: pointer; font-variant-numeric: tabular-nums; }
.batch-select:disabled { background: #f3f4f4; border-color: #e0e0e0; color: #9ca3af; cursor: not-allowed; }

.col-check { width: 40px; text-align: center; }
.row-check { width: 15px; height: 15px; accent-color: var(--teal); cursor: pointer; }
.row-selected td { background: #f0f7f6; }
.col-kind { width: 70px; }
.col-state { width: 90px; }
.col-conf { width: 80px; }
.col-time { width: 140px; color: var(--ink-400); font-size: 12px; }
.col-actions { width: 210px; white-space: nowrap; }
.doc-cell { display: flex; flex-direction: column; gap: 2px; min-width: 240px; }
.doc-id { font-size: 11px; color: var(--ink-400); font-family: ui-monospace, Consolas, monospace; }
.doc-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 440px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.muted { color: var(--ink-400); font-size: 12px; }
.cell-error { max-width: 240px; font-size: 12px; color: var(--danger); }
.conf { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.conf-high { background: #e8f5e9; color: var(--ok); }
.conf-mid { background: #fff8e1; color: var(--warn); }
.conf-low { background: #ffebee; color: var(--danger); }

.pager-bar { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
.page-size { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-500); }
.page-size .filter-select { padding: 4px 8px; }
.page-info { font-size: 12px; color: var(--ink-400); margin-left: auto; }
.pager-btns { display: flex; gap: 8px; }
.pager-btns .btn-sm:disabled { opacity: 0.45; cursor: not-allowed; }

.toast { position: fixed; top: 24px; right: 24px; z-index: 200; background: var(--teal); color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 13px; }
.toast-enter-active, .toast-leave-active { transition: opacity 0.2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; }
</style>
