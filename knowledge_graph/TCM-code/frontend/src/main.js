import { GraphStore } from "./store/graphStore.js";
import { createGraphView } from "./components/graphView.js";
import { createDetailPanel } from "./components/detailPanel.js";

const rawBaseUrl = String(window.APP_CONFIG?.API_BASE_URL || "").trim();
let resolvedBaseUrl = (rawBaseUrl && rawBaseUrl !== "auto")
  ? rawBaseUrl.replace(/\/$/, "")
  : window.location.origin;

if (!resolvedBaseUrl || resolvedBaseUrl === "null" || window.location.protocol === "file:") {
  resolvedBaseUrl = "http://127.0.0.1:8000";
}

const API_BASE_URL = resolvedBaseUrl;
const API_ENDPOINT = `${API_BASE_URL}/api/graph/expand`;
const DETAIL_ENDPOINT = `${API_BASE_URL}/api/graph/node-detail`;
const SEARCH_ENDPOINT = `${API_BASE_URL}/api/graph/search`;
const FILE_URL_ENDPOINT = `${API_BASE_URL}/api/graph/file-url`;

const seedInput = document.getElementById("seedInput");
const limitInput = document.getElementById("limitInput");
const depthInput = document.getElementById("depthInput");
const expandBtn = document.getElementById("expandBtn");
const clearBtn = document.getElementById("clearBtn");
const searchForm = document.getElementById("searchForm");
const clearSearchBtn = document.getElementById("clearSearchBtn");

const resultList = document.getElementById("resultList");
const suggestBox = document.getElementById("searchSuggest");
const graphLoading = document.getElementById("graphLoading");
const graphEmpty = document.getElementById("graphEmpty");

const detailPanel = createDetailPanel({
  detailTitle: document.getElementById("detailTitle"),
  detailMeta: document.getElementById("detailMeta"),
  detailBody: document.getElementById("detailBody")
});

let originNodeId = null;
let loadingCount = 0;
let suggestTimer = null;
let suggestAbort = null;
let lastSuggestQuery = "";
let toastTimer = null;

const store = new GraphStore();
const graphView = createGraphView(document.getElementById("graphContainer"), {
  store,
  onNodeHover: () => {},
  onNodeDetail: onNodeClick,
  fetchExpandData: (seedId) => fetchExpand(seedId),
  onExpandStart: (seedId) => {
    setGraphLoading(true);
  },
  onExpandError: (seedId, error) => {
    setGraphLoading(false);
    updateEmptyState();
  },
  onExpandSuccess: (seedId, merged) => {
    setGraphLoading(false);
    updateCounter();
  }
});

function ensureToastContainer() {
  let toast = document.getElementById("appToast");
  if (toast) {
    return toast;
  }
  toast = document.createElement("div");
  toast.id = "appToast";
  toast.className = "app-toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  document.body.appendChild(toast);
  return toast;
}

function showToast(message) {
  const toast = ensureToastContainer();
  toast.textContent = String(message || "操作失败");
  toast.classList.add("show");

  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 2200);
}

function setGraphLoading(isLoading) {
  if (!graphLoading) {
    return;
  }
  if (isLoading) {
    loadingCount += 1;
  } else {
    loadingCount = Math.max(0, loadingCount - 1);
  }
  const shouldShow = loadingCount > 0;
  graphLoading.classList.toggle("is-hidden", !shouldShow);
  if (shouldShow) {
    graphEmpty?.classList.add("is-hidden");
  }
}

function updateEmptyState() {
  if (!graphEmpty) {
    return;
  }
  const shouldShow = store.nodeMap.size === 0 && loadingCount === 0;
  graphEmpty.classList.toggle("is-hidden", !shouldShow);
}

function updateCounter() {
  renderResultList();
  updateEmptyState();
}

function updateClearButton() {
  if (!clearSearchBtn) {
    return;
  }
  const hasValue = String(seedInput.value || "").trim().length > 0;
  clearSearchBtn.classList.toggle("is-hidden", !hasValue);
}

function renderResultList() {
  if (!resultList) {
    return;
  }

  const nodes = Array.from(store.nodeMap.values());
  if (nodes.length === 0) {
    resultList.innerHTML = "<div class=\"result-item\">暂无节点</div>";
    return;
  }

  nodes.sort((a, b) => {
    if (originNodeId) {
      if (a.id === originNodeId) {
        return -1;
      }
      if (b.id === originNodeId) {
        return 1;
      }
    }
    if (a.node_type !== b.node_type) {
      return a.node_type.localeCompare(b.node_type);
    }
    return String(a.title || a.id).localeCompare(String(b.title || b.id));
  });

  resultList.innerHTML = "";
  nodes.forEach((node) => {
    const isOrigin = node.id === originNodeId;
    const typeLabel = node.node_type === "record" ? "Record" : "Paper";
    const displayTitle = node.node_type === "record"
      ? `病案：${node.title || node.id}`
      : (node.title || node.id);
    const authorOrDiagnosis = node.node_type === "record"
      ? (node.tcm_diagnosis || node.western_diagnosis || "-")
      : (node.authors || "-");
    const yearText = node.publish_year ? String(node.publish_year) : "-";

    const item = document.createElement("div");
    item.className = `result-item ${isOrigin ? "origin" : ""}`.trim();
    item.innerHTML = `
      <div class="result-head">
        <span class="type-chip ${node.node_type}">${typeLabel}</span>
        ${isOrigin ? '<span class="origin-pill">起始点</span>' : ""}
      </div>
      <div class="result-title">${displayTitle}</div>
      <div class="result-meta">
        <span>${node.node_type === "record" ? "诊断" : "作者"}：${authorOrDiagnosis}</span>
        <span>年份：${yearText}</span>
      </div>
    `;

    item.addEventListener("click", () => {
      graphView.setSeedNode(node.id);
      graphView.focusNode(node.id);
      onNodeClick({ id: node.id });
    });

    resultList.appendChild(item);
  });
}

async function requestExpand(options = {}) {
  const resetGraph = options.resetGraph === true;
  const seedId = String(seedInput.value || "").trim();
  if (!seedId) {
    return;
  }

  if (store.inFlightSeeds.has(seedId)) {
    return;
  }

  try {
    if (resetGraph) {
      graphView.clear();
      detailPanel.clear();
      originNodeId = null;
      updateCounter();
    }
    setGraphLoading(true);

    const payload = await fetchExpand(seedId);
    const merged = graphView.mergeGraph(payload);
    originNodeId = seedId;
    graphView.setSeedNode(seedId);
    graphView.focusNode(seedId);
    updateCounter();
  } catch (error) {
    showToast("加载失败，请重试");
  } finally {
    setGraphLoading(false);
    updateEmptyState();
  }
}

async function requestExpandWithSeed(seedId, displayTitle, options = {}) {
  const normalizedSeed = String(seedId || "").trim();
  if (!normalizedSeed) {
    return;
  }
  if (displayTitle) {
    seedInput.value = displayTitle;
    updateClearButton();
  }
  const resetGraph = options.resetGraph === true;

  try {
    if (resetGraph) {
      graphView.clear();
      detailPanel.clear();
      originNodeId = null;
      updateCounter();
    }
    setGraphLoading(true);

    const payload = await fetchExpand(normalizedSeed);
    const merged = graphView.mergeGraph(payload);
    originNodeId = normalizedSeed;
    graphView.setSeedNode(normalizedSeed);
    graphView.focusNode(normalizedSeed);
    updateCounter();
  } catch (error) {
    showToast("加载失败，请重试");
  } finally {
    setGraphLoading(false);
    updateEmptyState();
  }
}

async function fetchExpand(seedId) {
  const limitValue = limitInput ? String(limitInput.value || "10") : "10";
  const depthValue = depthInput ? String(depthInput.value || "1") : "1";
  const params = new URLSearchParams({
    seed_id: seedId,
    limit: limitValue,
    depth: depthValue
  });

  const response = await fetch(`${API_ENDPOINT}?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "扩展失败");
  }
  return payload;
}

async function onNodeClick(nodeModel) {
  if (!nodeModel || !nodeModel.id) {
    return;
  }

  try {
    detailPanel.setLoading(nodeModel);
    const params = new URLSearchParams({ node_id: nodeModel.id });
    const response = await fetch(`${DETAIL_ENDPOINT}?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "详情加载失败");
    }

    detailPanel.render(payload);
  } catch (error) {
    detailPanel.renderError(error.message || "详情加载失败");
  }
}

async function fetchFileUrl(nodeId, mode) {
  const params = new URLSearchParams({ mode });
  const response = await fetch(`${FILE_URL_ENDPOINT}/${encodeURIComponent(nodeId)}?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok || !payload?.url) {
    throw new Error(payload?.error || "获取链接失败");
  }
  return payload;
}

function triggerDownload(url, fileName) {
  const anchor = document.createElement("a");
  anchor.href = url;
  if (fileName) {
    anchor.download = fileName;
  }
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

async function onDetailAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button || button.disabled) {
    return;
  }

  const action = String(button.dataset.action || "").trim();
  const nodeId = String(button.dataset.nodeId || "").trim();
  if (!nodeId || !action) {
    return;
  }

  if (action === "view") {
    try {
      const payload = await fetchFileUrl(nodeId, "view");
      window.open(payload.url, "_blank", "noopener");
    } catch (error) {
      showToast("暂未挂载原始文献文件");
    }
    return;
  }

  if (action === "download") {
    try {
      const payload = await fetchFileUrl(nodeId, "download");
      triggerDownload(payload.url, payload.file_name);
    } catch (error) {
      showToast("暂未挂载原始文献文件");
    }
    return;
  }
}

function clearGraph() {
  graphView.clear();
  detailPanel.clear();
  originNodeId = null;
  updateCounter();
  updateEmptyState();
}

async function autoExpandSeed(seedId, seedType) {
  if (!seedId) {
    return;
  }

  if (store.inFlightSeeds.has(seedId)) {
    return;
  }

  const typeHint = seedType ? ` (${seedType})` : "";
  try {
    store.inFlightSeeds.add(seedId);
    setGraphLoading(true);

    const payload = await fetchExpand(seedId);
    const merged = graphView.mergeGraph(payload);
    originNodeId = seedId;
    graphView.setSeedNode(seedId);
    graphView.focusNode(seedId);
    updateCounter();
  } catch (error) {
    showToast("加载失败，请重试");
  } finally {
    setGraphLoading(false);
    updateEmptyState();
    store.inFlightSeeds.delete(seedId);
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function hideSuggest() {
  if (!suggestBox) {
    return;
  }
  suggestBox.classList.add("is-hidden");
  suggestBox.innerHTML = "";
}

function renderSuggest(items, query) {
  if (!suggestBox) {
    return;
  }

  if (!Array.isArray(items) || items.length === 0) {
    hideSuggest();
    return;
  }

  const unique = new Map();
  for (const item of items) {
    const title = String(item?.title || "").trim();
    if (!title || unique.has(title)) {
      continue;
    }
    unique.set(title, item);
    if (unique.size >= 6) {
      break;
    }
  }

  if (unique.size === 0) {
    hideSuggest();
    return;
  }

  const html = Array.from(unique.values())
    .map((item) => {
      const title = escapeHtml(item.title || "未命名");
      const typeLabel = item.source_type === "record" ? "病案" : "文献";
      const meta = item.source_type === "record"
        ? (item.tcm_diagnosis || item.western_diagnosis || "")
        : (item.authors || "");
      const year = item.publish_year ? String(item.publish_year) : "";
      const seedId = escapeHtml(item.node_id || item.title || "");
      const displayTitle = escapeHtml(item.title || "");
      const metaText = escapeHtml(meta || "暂无更多信息");
      const yearText = year ? ` · ${escapeHtml(year)}` : "";
      return `
        <button class="suggest-item" type="button" data-seed-id="${seedId}" data-display-title="${displayTitle}">
          <span class="suggest-title">${title}</span>
          <span class="suggest-meta">
            <span class="suggest-tag">${typeLabel}</span>
            <span>${metaText}${yearText}</span>
          </span>
        </button>
      `;
    })
    .join("");

  suggestBox.innerHTML = html;
  suggestBox.classList.remove("is-hidden");
  lastSuggestQuery = query;
}

async function fetchSuggest(query) {
  const trimmed = String(query || "").trim();
  if (!trimmed) {
    hideSuggest();
    return;
  }

  if (suggestAbort) {
    suggestAbort.abort();
  }

  const controller = new AbortController();
  suggestAbort = controller;
  const params = new URLSearchParams({
    q: trimmed,
    page: "1",
    size: "6"
  });

  try {
    const response = await fetch(`${SEARCH_ENDPOINT}?${params.toString()}`, {
      signal: controller.signal
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "联想失败");
    }
    if (String(seedInput.value || "").trim() !== trimmed) {
      return;
    }
    renderSuggest(payload.items || [], trimmed);
  } catch (error) {
    if (error?.name === "AbortError") {
      return;
    }
    hideSuggest();
  }
}

function scheduleSuggest() {
  const query = String(seedInput.value || "").trim();
  if (query.length < 2) {
    lastSuggestQuery = "";
    hideSuggest();
    return;
  }

  if (query === lastSuggestQuery && suggestBox && !suggestBox.classList.contains("is-hidden")) {
    return;
  }

  if (suggestTimer) {
    window.clearTimeout(suggestTimer);
  }
  suggestTimer = window.setTimeout(() => {
    fetchSuggest(query);
  }, 280);
}

if (searchForm) {
  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    hideSuggest();
    requestExpand({ resetGraph: true });
  });
} else {
  expandBtn?.addEventListener("click", requestExpand);
}
clearBtn.addEventListener("click", clearGraph);
seedInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    hideSuggest();
    requestExpand({ resetGraph: true });
  }
  if (event.key === "Escape") {
    hideSuggest();
  }
});

seedInput.addEventListener("input", () => {
  updateClearButton();
  scheduleSuggest();
});
seedInput.addEventListener("focus", () => {
  if (String(seedInput.value || "").trim().length >= 2) {
    scheduleSuggest();
  }
});
seedInput.addEventListener("blur", () => {
  window.setTimeout(() => {
    hideSuggest();
  }, 160);
});

suggestBox?.addEventListener("click", (event) => {
  const target = event.target.closest(".suggest-item");
  if (!target) {
    return;
  }
  const seedId = target.dataset.seedId;
  const displayTitle = target.dataset.displayTitle;
  hideSuggest();
  requestExpandWithSeed(seedId, displayTitle, { resetGraph: true });
});

document.addEventListener("click", (event) => {
  if (!searchForm?.contains(event.target)) {
    hideSuggest();
  }
});

document.getElementById("detailBody")?.addEventListener("click", onDetailAction);

clearSearchBtn?.addEventListener("click", () => {
  seedInput.value = "";
  seedInput.focus();
  hideSuggest();
  lastSuggestQuery = "";
  updateClearButton();
});

updateCounter();
detailPanel.clear();

const pageParams = new URLSearchParams(window.location.search);
const querySeedId = String(pageParams.get("seed_id") || "").trim();
const querySeedType = String(pageParams.get("type") || "").trim();
if (querySeedId) {
  seedInput.value = querySeedId;
  updateClearButton();
  autoExpandSeed(querySeedId, querySeedType);
}
