<template>
  <div class="results-page">
    <aside class="results-filter-panel">
      <div class="filter-panel-header">
        <h2>筛选</h2>
        <button v-if="activeFilterCount" type="button" class="filter-clear" @click="clearFilters">清空</button>
      </div>

      <div v-for="group in filterGroups" :key="group.key" class="filter-group">
        <h3>{{ group.label }}</h3>
        <label v-for="option in visibleFilterOptions(group)" :key="`${group.key}-${option.value}`" class="filter-option">
          <input
            type="checkbox"
            :checked="isFilterSelected(group.key, option.value)"
            @change="toggleFilter(group.key, option.value)"
          />
          <span class="filter-option-label">{{ formatOptionLabel(group.key, option.label || option.value) }}</span>
          <span class="filter-option-count">{{ option.count }}</span>
        </label>
        <button v-if="isFilterCollapsible(group)" type="button" class="filter-more" @click="toggleFilterGroup(group.key)">
          {{ expandedFilterGroups[group.key] ? "收起" : `展开 ${group.options.length - 2} 项` }}
        </button>
        <div v-if="group.options.length === 0" class="filter-empty">暂无选项</div>
      </div>
    </aside>

    <section class="results-main">
      <div class="results-header">
        <button class="btn-ghost" @click="$router.push('/search')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          返回
        </button>
        <div class="results-meta">
          <span class="results-query">「{{ $route.query.q }}」</span>
          <span class="results-count">共 {{ searchStore.total }} 条结果</span>
        </div>
      </div>

      <div v-if="searchStore.loading" class="results-loading">搜索中...</div>

      <div v-else class="results-list">
        <component
          :is="item.node_id || item.file_uuid ? 'a' : 'div'"
          v-for="item in searchStore.results"
          :key="`${item.source_type}-${item.node_id || item.file_uuid || item.title}`"
          :href="item.node_id ? detailHref(item) : (item.file_uuid ? fileDetailHref(item) : undefined)"
          :target="item.node_id || item.file_uuid ? '_blank' : undefined"
          :rel="item.node_id || item.file_uuid ? 'noopener noreferrer' : undefined"
          class="result-card"
          :class="{ disabled: !item.node_id && !item.file_uuid }"
        >
          <div class="result-type-badge" :class="item.source_type">
            {{ item.source_type === "record" ? "病案" : "文献" }}
          </div>
          <h3 class="result-title">{{ item.title || "未命名" }}</h3>
          <p class="result-meta-text">
            <template v-if="item.source_type === 'paper'">
              {{ item.authors || "未知作者" }}
              <span v-if="item.journal"> · {{ item.journal }}</span>
              <span v-if="item.publish_year"> · {{ item.publish_year }}</span>
            </template>
            <template v-else>
              {{ item.tcm_diagnosis || item.western_diagnosis || "暂无诊断信息" }}
            </template>
          </p>
          <p v-if="item.abstract" class="result-abstract">{{ item.abstract }}</p>
          <div v-if="item.keywords" class="result-keywords">
            <span v-for="kw in splitKeywords(item.keywords)" :key="kw" class="keyword-tag">{{ kw }}</span>
          </div>
        </component>

        <div v-if="searchStore.error" class="results-empty error">
          {{ searchStore.error }}
        </div>

        <div v-else-if="searchStore.results.length === 0" class="results-empty">
          未找到相关结果
        </div>
      </div>

      <div v-if="searchStore.totalPages > 1" class="results-pagination">
        <button class="btn-ghost" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <span class="page-info">第 {{ currentPage }} 页 / 共 {{ searchStore.totalPages }} 页</span>
        <form class="page-jump" @submit.prevent="jumpToPage">
          <input v-model.number="jumpPage" type="number" min="1" :max="searchStore.totalPages" class="page-input" />
          <button type="submit" class="btn-ghost">跳转</button>
        </form>
        <button class="btn-ghost" :disabled="currentPage >= searchStore.totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSearchStore } from "../stores/search";

const route = useRoute();
const router = useRouter();
const searchStore = useSearchStore();

const searchType = ref(route.query.type || "both");
const currentPage = ref(1);
const jumpPage = ref(1);
const selectedFilters = reactive({
  source_types: [],
  paper_types: [],
  topics: [],
  years: [],
  journals: [],
});
const expandedFilterGroups = reactive({});

const filterDefinitions = [
  { key: "source_types", label: "来源类别" },
  { key: "paper_types", label: "文献类型" },
  { key: "topics", label: "主题" },
  { key: "years", label: "年度" },
  { key: "journals", label: "期刊" },
];

const sourceLabels = { paper: "文献", record: "病案" }; 
const paperTypeLabels = { "期刊论文": "期刊论文", "学位论文": "学位论文" };

const activeFilterCount = computed(() =>
  Object.values(selectedFilters).reduce((sum, values) => sum + values.length, 0)
);

const filterGroups = computed(() =>
  filterDefinitions.map(def => {
    if (def.key === "source_types") {
      const counts = Object.fromEntries((searchStore.facets.source_types || []).map(option => [option.value, option.count]));
      return {
        ...def,
        options: [
          { value: "paper", label: "paper", count: counts.paper || 0 },
          { value: "record", label: "record", count: counts.record || 0 },
        ],
      };
    }
    if (def.key === "paper_types") {
      return {
        ...def,
        options: (searchStore.facets.paper_types || []).filter(option => option.value),
      };
    }
    return {
      ...def,
      options: (searchStore.facets[def.key] || []).filter(option => option.value),
    };
  })
);

onMounted(() => {
  resetFiltersFromRoute();
  runSearchFromRoute();
});

watch(
  () => [route.query.q, route.query.type],
  () => {
    searchType.value = route.query.type || "both";
    currentPage.value = 1;
    jumpPage.value = 1;
    resetFiltersFromRoute();
    runSearchFromRoute();
  }
);

function runSearchFromRoute() {
  if (route.query.q) {
    executeSearch(currentPage.value);
  }
}

function splitKeywords(keywords) {
  if (!keywords) return [];
  return String(keywords).split(/[、,，;；\s]+/).filter(Boolean).slice(0, 5);
}

function resetFiltersFromRoute() {
  Object.keys(selectedFilters).forEach(key => selectedFilters[key].splice(0));
  if (route.query.type === "literature") selectedFilters.source_types.push("paper");
  if (route.query.type === "case") selectedFilters.source_types.push("record");
}

function filtersForRequest() {
  return Object.fromEntries(
    Object.entries(selectedFilters).filter(([, values]) => values.length > 0)
  );
}

function effectiveSearchType() {
  const sources = selectedFilters.source_types;
  if (sources.length === 1 && sources[0] === "paper") return "literature";
  if (sources.length === 1 && sources[0] === "record") return "case";
  return "both";
}

async function executeSearch(page) {
  const query = route.query.q;
  if (!query) return;
  const totalPages = searchStore.totalPages || 1;
  const safePage = Math.max(1, Math.min(Number(page) || 1, totalPages || 1));
  currentPage.value = safePage;
  jumpPage.value = safePage;
  searchType.value = effectiveSearchType();
  await searchStore.search(query, searchType.value, safePage, 10, filtersForRequest());
  currentPage.value = searchStore.page || safePage;
  jumpPage.value = currentPage.value;
}

function isFilterSelected(key, value) {
  return selectedFilters[key]?.includes(value);
}

function isFilterCollapsible(group) {
  return group.options.length > 10;
}

function visibleFilterOptions(group) {
  if (!isFilterCollapsible(group) || expandedFilterGroups[group.key]) return group.options;
  return group.options.slice(0, 2);
}

function toggleFilterGroup(key) {
  expandedFilterGroups[key] = !expandedFilterGroups[key];
}

function toggleFilter(key, value) {
  const values = selectedFilters[key];
  const index = values.indexOf(value);
  if (index >= 0) values.splice(index, 1);
  else values.push(value);
  currentPage.value = 1;
  jumpPage.value = 1;
  executeSearch(1);
}

function clearFilters() {
  Object.keys(selectedFilters).forEach(key => selectedFilters[key].splice(0));
  currentPage.value = 1;
  jumpPage.value = 1;
  executeSearch(1);
}

async function changePage(page) {
  const totalPages = searchStore.totalPages || 1;
  await executeSearch(Math.max(1, Math.min(Number(page) || 1, totalPages)));
}

function jumpToPage() {
  changePage(jumpPage.value);
}

function detailHref(item) {
  if (!item.node_id) return "";
  return router.resolve({ name: "Detail", params: { nodeId: item.node_id } }).href;
}

function fileDetailHref(item) {
  if (!item.file_uuid) return "";
  return router.resolve({
    name: "DetailByFile",
    params: { fileUuid: item.file_uuid },
    query: { source_type: item.source_type },
  }).href;
}

function formatOptionLabel(key, value) {
  if (key === "source_types") return sourceLabels[value] || value;
  if (key === "paper_types") return paperTypeLabels[value] || value;
  return value;
}
</script>

<style scoped>
.results-page { flex: 1; display: flex; min-height: 0; overflow: hidden; width: 100%; }
.results-filter-panel { width: 260px; min-width: 260px; overflow-y: auto; background: var(--panel); border-right: 1px solid var(--border); padding: 16px 14px; }
.filter-panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.filter-panel-header h2 { margin: 0; font-size: 15px; color: var(--ink-900); }
.filter-clear { border: none; background: transparent; color: var(--teal); font-size: 12px; cursor: pointer; }
.filter-group { padding: 14px 0; border-top: 1px solid var(--border); }
.filter-group h3 { margin: 0 0 10px; font-size: 12px; color: var(--ink-600); font-weight: 600; }
.filter-option { display: flex; align-items: center; gap: 8px; min-height: 30px; font-size: 13px; color: var(--ink-700); cursor: pointer; }
.filter-option input { width: 14px; height: 14px; accent-color: var(--teal); flex: 0 0 auto; }
.filter-option-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.filter-option-count { flex: 0 0 auto; min-width: 22px; text-align: right; color: var(--ink-500); font-size: 11px; }
.filter-more { margin-top: 6px; border: none; background: transparent; color: var(--teal); font-size: 12px; cursor: pointer; padding: 2px 0; }
.filter-more:hover { color: var(--teal-deep); }
.filter-empty { font-size: 12px; color: var(--ink-500); padding: 4px 0; }
.results-main { flex: 1; min-width: 0; overflow-y: auto; padding: 24px; }
.results-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.results-meta { flex: 1; }
.results-query { font-size: 18px; font-weight: 600; color: var(--ink-900); }
.results-count { margin-left: 10px; font-size: 13px; color: var(--ink-500); }
.results-loading { text-align: center; padding: 40px; color: var(--ink-500); }
.results-list { display: flex; flex-direction: column; gap: 12px; }
.result-card { display: block; padding: 16px 20px; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-lg); color: inherit; text-decoration: none; cursor: pointer; transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease; }
.result-card:hover { border-color: rgba(0, 121, 107, 0.35); box-shadow: var(--shadow); transform: translateY(-1px); }
.result-card.disabled { cursor: default; opacity: 0.72; }
.result-card.disabled:hover { border-color: var(--border); box-shadow: none; transform: none; }
.result-type-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; margin-bottom: 8px; }
.result-type-badge.paper { background: rgba(0, 121, 107, 0.1); color: var(--teal); }
.result-type-badge.record { background: rgba(199, 124, 2, 0.15); color: #b06a00; }
.result-title { font-size: 16px; font-weight: 600; color: var(--ink-900); margin-bottom: 6px; }
.result-meta-text { font-size: 13px; color: var(--ink-500); margin-bottom: 8px; }
.result-abstract { font-size: 13px; color: var(--ink-600); line-height: 1.6; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.result-keywords { display: flex; flex-wrap: wrap; gap: 6px; }
.keyword-tag { padding: 2px 8px; border-radius: 999px; font-size: 11px; color: var(--teal); background: var(--teal-soft); }
.results-empty { text-align: center; padding: 40px; color: var(--ink-500); }
.results-empty.error { color: var(--danger); }
.results-pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 24px; padding: 16px 0; flex-wrap: wrap; }
.page-info { font-size: 13px; color: var(--ink-500); }
.page-jump { display: inline-flex; align-items: center; gap: 6px; }
.page-input { width: 72px; height: 34px; border: 1px solid var(--border); border-radius: var(--radius); padding: 0 8px; font-size: 13px; color: var(--ink-900); outline: none; }
.page-input:focus { border-color: var(--teal); box-shadow: 0 0 0 3px var(--teal-soft); }
</style>
