<template>
  <div class="results-page">
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
      <div class="results-filters">
        <label class="filter-chip" :class="{ active: searchType === 'both' }">
          <input type="radio" v-model="searchType" value="both" hidden @change="handleFilter" />
          全部
        </label>
        <label class="filter-chip" :class="{ active: searchType === 'literature' }">
          <input type="radio" v-model="searchType" value="literature" hidden @change="handleFilter" />
          文献
        </label>
        <label class="filter-chip" :class="{ active: searchType === 'case' }">
          <input type="radio" v-model="searchType" value="case" hidden @change="handleFilter" />
          病案
        </label>
      </div>
    </div>

    <div v-if="searchStore.loading" class="results-loading">搜索中...</div>

    <div v-else class="results-list">
      <component
        :is="item.node_id ? 'a' : 'div'"
        v-for="item in searchStore.results"
        :key="`${item.source_type}-${item.node_id || item.title}`"
        :href="item.node_id ? detailHref(item) : undefined"
        :target="item.node_id ? '_blank' : undefined"
        :rel="item.node_id ? 'noopener noreferrer' : undefined"
        class="result-card"
        :class="{ disabled: !item.node_id }"
      >
        <div class="result-type-badge" :class="item.source_type">
          {{ item.source_type === "record" ? "病案" : "文献" }}
        </div>
        <h3 class="result-title">{{ item.title || "未命名" }}</h3>
        <p class="result-meta-text">
          <template v-if="item.source_type === 'paper'">
            {{ item.authors || "未知作者" }}
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
      <button class="btn-ghost" :disabled="currentPage >= searchStore.totalPages" @click="changePage(currentPage + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSearchStore } from "../stores/search";

const route = useRoute();
const router = useRouter();
const searchStore = useSearchStore();

const searchType = ref(route.query.type || "both");
const currentPage = ref(1);

onMounted(runSearchFromRoute);

watch(
  () => [route.query.q, route.query.type],
  () => {
    searchType.value = route.query.type || "both";
    currentPage.value = 1;
    runSearchFromRoute();
  }
);

function runSearchFromRoute() {
  if (route.query.q) {
    searchStore.search(route.query.q, searchType.value, currentPage.value);
  }
}

function splitKeywords(keywords) {
  if (!keywords) return [];
  return String(keywords).split(/[、,，;；\s]+/).filter(Boolean).slice(0, 5);
}

async function handleFilter() {
  currentPage.value = 1;
  await searchStore.search(route.query.q, searchType.value, 1);
}

async function changePage(page) {
  currentPage.value = page;
  await searchStore.search(route.query.q, searchType.value, page);
}

function detailHref(item) {
  if (!item.node_id) return "";
  return router.resolve({ name: "Detail", params: { nodeId: item.node_id } }).href;
}
</script>

<style scoped>
.results-page { flex: 1; overflow-y: auto; padding: 24px; max-width: 900px; margin: 0 auto; width: 100%; }
.results-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.results-meta { flex: 1; }
.results-query { font-size: 18px; font-weight: 600; color: var(--ink-900); }
.results-count { margin-left: 10px; font-size: 13px; color: var(--ink-500); }
.results-filters { display: flex; gap: 6px; }
.filter-chip { padding: 5px 12px; border: 1px solid var(--border); border-radius: 999px; font-size: 12px; color: var(--ink-700); background: var(--panel); cursor: pointer; transition: all 0.2s ease; }
.filter-chip:hover { border-color: var(--teal); color: var(--teal); }
.filter-chip.active { background: var(--teal); border-color: var(--teal); color: #fff; }
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
.results-pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 24px; padding: 16px 0; }
.page-info { font-size: 13px; color: var(--ink-500); }
</style>
