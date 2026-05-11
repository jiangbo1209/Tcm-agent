const form = document.getElementById("searchForm");
const input = document.getElementById("seedInput");
const hint = document.getElementById("hintText");
const tryChips = document.querySelectorAll(".try-chip");
const exampleCards = document.querySelectorAll(".example-card");
const resultsPanel = document.getElementById("resultsPanel");
const resultsList = document.getElementById("resultsList");
const resultsMeta = document.getElementById("resultsMeta");
const loadingBadge = document.getElementById("loadingBadge");
const prevPageBtn = document.getElementById("prevPage");
const nextPageBtn = document.getElementById("nextPage");
const pageInfo = document.getElementById("pageInfo");
const tryRow = document.getElementById("tryRow");
const examplesSection = document.getElementById("examplesSection");

const PAGE_SIZE = 8;
let currentQuery = "";
let currentPage = 1;
let totalPages = 1;

const rawBaseUrl = String(window.APP_CONFIG?.API_BASE_URL || "").trim();
let resolvedBaseUrl = rawBaseUrl && rawBaseUrl !== "auto"
  ? rawBaseUrl.replace(/\/$/, "")
  : window.location.origin;

if (!resolvedBaseUrl || resolvedBaseUrl === "null" || window.location.protocol === "file:") {
  resolvedBaseUrl = "http://127.0.0.1:8000";
}

const API_BASE_URL = resolvedBaseUrl;
const SEARCH_ENDPOINT = `${API_BASE_URL}/api/graph/search`;
const DEMO_GRAPH_MAP = {
  infertility: {
    seedId: "paper:157c057c97e7dbfa",
    type: "paper"
  },
  cases: {
    seedId: "record:e763cba76e2386bc",
    type: "record"
  }
};

function goToGraph(seedId) {
  const params = new URLSearchParams({ seed_id: seedId });
  window.location.href = `./index.html?${params.toString()}`;
}

function goToGraphWithType(seedId, type) {
  const params = new URLSearchParams({ seed_id: seedId, type });
  window.location.href = `./index.html?${params.toString()}`;
}

function showDemoToast(message) {
  let toast = document.querySelector(".demo-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "demo-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");

  window.clearTimeout(showDemoToast._timer);
  showDemoToast._timer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 2600);
}

function toggleResults(show) {
  if (show) {
    resultsPanel.classList.remove("hidden");
    tryRow?.classList.add("fade-out");
    examplesSection?.classList.add("fade-out");
  } else {
    resultsPanel.classList.add("hidden");
    tryRow?.classList.remove("fade-out");
    examplesSection?.classList.remove("fade-out");
  }
}

function setLoading(isLoading) {
  if (isLoading) {
    loadingBadge.classList.remove("hidden");
  } else {
    loadingBadge.classList.add("hidden");
  }
}

function renderResults(items) {
  resultsList.innerHTML = "";
  if (!items || items.length === 0) {
    resultsList.innerHTML = "<div class=\"result-item\">未找到相关结果</div>";
    return;
  }

  items.forEach((item) => {
    const typeLabel = item.source_type === "record" ? "病案" : "文献";
    const title = item.title || "未命名";
    const metaPrimary = item.source_type === "paper"
      ? (item.keywords || item.abstract || "暂无摘要")
      : (item.tcm_diagnosis || item.western_diagnosis || "暂无诊断信息");
    const year = item.publish_year ? `年份: ${item.publish_year}` : "年份: -";

    const card = document.createElement("div");
    card.className = "result-item";
    card.dataset.seedId = item.node_id || title;
    card.dataset.type = item.source_type;
    card.innerHTML = `
      <div class="result-type">${typeLabel}</div>
      <div class="result-title">${title}</div>
      <div class="result-meta">
        <span>${metaPrimary}</span>
        <span>${year}</span>
      </div>
    `;

    card.addEventListener("click", () => {
      const seedId = card.dataset.seedId;
      const type = card.dataset.type;
      goToGraphWithType(seedId, type);
    });

    resultsList.appendChild(card);
  });
}

async function fetchResults(query, page) {
  const params = new URLSearchParams({
    q: query,
    page: String(page),
    size: String(PAGE_SIZE)
  });
  const response = await fetch(`${SEARCH_ENDPOINT}?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "搜索失败");
  }
  return payload;
}

async function runSearch(page = 1) {
  const query = String(input.value || "").trim();
  if (!query) {
    hint.textContent = "请输入关键词后再搜索";
    hint.style.color = "#9b2f2f";
    input.focus();
    return;
  }

  currentQuery = query;
  currentPage = page;
  toggleResults(true);
  setLoading(true);

  try {
    const payload = await fetchResults(currentQuery, currentPage);
    totalPages = payload.total_pages || 1;
    resultsMeta.textContent = `共 ${payload.total || 0} 条结果`;
    pageInfo.textContent = `第 ${payload.page} 页 / 共 ${totalPages} 页`;
    renderResults(payload.items || []);
    prevPageBtn.disabled = payload.page <= 1;
    nextPageBtn.disabled = payload.page >= totalPages;
  } catch (error) {
    resultsMeta.textContent = error.message || "搜索失败";
    renderResults([]);
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  runSearch(1);
});

tryChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const seedId = String(chip.dataset.seed || "").trim();
    if (!seedId) {
      return;
    }
    input.value = seedId;
    runSearch(1);
  });
});

exampleCards.forEach((card) => {
  card.addEventListener("click", () => {
    const demoKey = String(card.dataset.demo || "").trim();
    if (!demoKey) {
      return;
    }

    if (demoKey === "formula") {
      showDemoToast("正在处理 10 万级方剂拓扑数据，该演示模块即将上线...");
      return;
    }

    const mapped = DEMO_GRAPH_MAP[demoKey];
    if (!mapped?.seedId || !mapped?.type) {
      showDemoToast("该演示图谱暂不可用，请稍后重试");
      return;
    }

    goToGraphWithType(mapped.seedId, mapped.type);
  });
});

prevPageBtn.addEventListener("click", () => {
  if (currentPage > 1) {
    runSearch(currentPage - 1);
  }
});

nextPageBtn.addEventListener("click", () => {
  if (currentPage < totalPages) {
    runSearch(currentPage + 1);
  }
});

window.addEventListener("DOMContentLoaded", () => {
  input.focus();
  toggleResults(false);
});
