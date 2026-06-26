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

  async function search(query, type = "both", pageNum = 1, size = 10) {
    loading.value = true;
    searchType.value = type;
    page.value = pageNum;
    try {
      const { data } = await smartSearch(query, type, pageNum, size);
      results.value = data.items || [];
      total.value = data.total || 0;
      totalPages.value = data.total_pages || 0;
      page.value = data.page || 1;
    } finally {
      loading.value = false;
    }
  }

  async function fetchHistory() {
    const { data } = await getSearchHistory();
    history.value = data.items || [];
  }

  return { results, total, totalPages, page, loading, searchType, history, search, fetchHistory };
});
