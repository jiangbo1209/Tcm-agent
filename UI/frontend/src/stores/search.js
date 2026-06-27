import { defineStore } from "pinia";
import { ref } from "vue";
import { smartSearch, getSearchHistory } from "../api/search";

export const useSearchStore = defineStore("search", () => {
  const results = ref([]);
  const total = ref(0);
  const totalPages = ref(0);
  const page = ref(1);
  const loading = ref(false);
  const searchType = ref("both");
  const history = ref([]);
  const error = ref("");
  const facets = ref({});

  async function search(query, type = "both", pageNum = 1, size = 10, filters = {}) {
    loading.value = true;
    error.value = "";
    searchType.value = type;
    page.value = pageNum;
    try {
      const { data } = await smartSearch(query, type, pageNum, size, filters);
      results.value = data.items || [];
      total.value = data.total || 0;
      totalPages.value = data.total_pages || 0;
      page.value = data.page || 1;
      facets.value = data.facets || {};
    } catch (err) {
      results.value = [];
      total.value = 0;
      totalPages.value = 0;
      facets.value = {};
      error.value = err.response?.data?.error || err.response?.data?.detail || "搜索失败，请稍后重试";
    } finally {
      loading.value = false;
    }
  }

  async function fetchHistory() {
    try {
      const { data } = await getSearchHistory();
      history.value = data.items || [];
    } catch {
      history.value = [];
    }
  }

  return { results, total, totalPages, page, loading, searchType, history, error, facets, search, fetchHistory };
});
