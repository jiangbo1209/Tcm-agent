<template>
  <div class="search-page">
    <div class="search-container">
      <div class="search-hero">
        <h1>智能搜索</h1>
        <p>搜索中医文献与病案，支持分类检索</p>
      </div>

      <form class="search-form" @submit.prevent="handleSearch">
        <div class="search-box">
          <input
            v-model="query"
            type="text"
            class="search-input"
            placeholder="输入关键词、论文标题、中医诊断..."
            required
          />
          <button type="submit" class="btn-primary search-btn" :disabled="loading">
            {{ loading ? "搜索中..." : "搜索" }}
          </button>
        </div>

        <div class="search-filters">
          <label class="filter-chip" :class="{ active: searchType === 'both' }">
            <input type="radio" v-model="searchType" value="both" hidden />
            全部
          </label>
          <label class="filter-chip" :class="{ active: searchType === 'literature' }">
            <input type="radio" v-model="searchType" value="literature" hidden />
            搜索文献
          </label>
          <label class="filter-chip" :class="{ active: searchType === 'case' }">
            <input type="radio" v-model="searchType" value="case" hidden />
            搜索病案
          </label>
        </div>
      </form>

      <div v-if="searchStore.history.length > 0" class="search-history">
        <h3>搜索历史</h3>
        <div class="history-tags">
          <span
            v-for="item in searchStore.history"
            :key="item.id"
            class="history-tag"
            @click="query = item.query; handleSearch()"
          >
            {{ item.query }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useSearchStore } from "../stores/search";

const router = useRouter();
const searchStore = useSearchStore();

const query = ref("");
const searchType = ref("both");
const loading = ref(false);

onMounted(() => {
  searchStore.fetchHistory();
});

async function handleSearch() {
  if (!query.value.trim()) return;
  loading.value = true;
  try {
    await searchStore.search(query.value, searchType.value);
    router.push({
      path: "/search/results",
      query: { q: query.value, type: searchType.value },
    });
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.search-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.search-container {
  max-width: 680px;
  width: 100%;
}

.search-hero {
  text-align: center;
  margin-bottom: 32px;
}

.search-hero h1 {
  font-size: 32px;
  font-weight: 600;
  color: var(--ink-900);
  margin-bottom: 8px;
}

.search-hero p {
  font-size: 15px;
  color: var(--ink-500);
}

.search-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-box {
  display: flex;
  gap: 10px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 6px 6px 20px;
  box-shadow: var(--shadow-lg);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.search-box:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 4px var(--teal-soft);
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  color: var(--ink-900);
  background: transparent;
}

.search-input::placeholder {
  color: var(--ink-500);
}

.search-btn {
  border-radius: 999px;
  padding: 10px 24px;
  font-size: 14px;
}

.search-filters {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.filter-chip {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--ink-700);
  background: var(--panel);
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-chip:hover {
  border-color: var(--teal);
  color: var(--teal);
}

.filter-chip.active {
  background: var(--teal);
  border-color: var(--teal);
  color: #fff;
}

.search-history {
  margin-top: 40px;
}

.search-history h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-700);
  margin-bottom: 12px;
}

.history-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.history-tag {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--ink-600);
  cursor: pointer;
  transition: all 0.2s ease;
}

.history-tag:hover {
  border-color: var(--teal);
  color: var(--teal);
  background: var(--teal-hover);
}
</style>
