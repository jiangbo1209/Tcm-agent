<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>数据管理</h1>
    </div>

    <div class="table-tabs">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTable === tab.key }" @click="switchTable(tab.key)">
        {{ tab.label }}
        <span class="tab-count" v-if="tab.count !== null">({{ tab.count }})</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="search-bar">
        <input v-model="searchQuery" type="text" class="search-input" :placeholder="searchPlaceholder" @keyup.enter="doSearch" />
        <button class="btn-search" @click="doSearch">搜索</button>
        <button v-if="searchQuery" class="btn-clear" @click="clearSearch">清除</button>
      </div>
      <button v-if="totalPages > 1" class="btn-random" @click="randomPage" title="随机跳转到其他页面，避免多人同时修改同一条记录">
        随机跳转
      </button>
    </div>

    <div class="filters" v-if="activeTable !== 'case'">
      <div class="filter-group">
        <label>数据状态</label>
        <select v-model="filterCrawlStatus" class="filter-select" @change="doSearch">
          <option value="">全部</option>
          <option value="success">success</option>
          <option value="partial">partial</option>
          <option value="failed">failed</option>
        </select>
      </div>
      <div class="filter-group filter-year-group">
        <label>年份</label>
        <span class="year-label">{{ yearSliderMin }} — {{ yearSliderMax }}</span>
        <div class="range-slider" ref="sliderTrack">
          <div class="range-fill" :style="rangeFillStyle"></div>
          <input
            type="range"
            class="range-thumb range-thumb-min"
            :min="yearRange.minYear || 1900"
            :max="yearRange.maxYear || 2100"
            v-model.number="yearSliderMin"
            @input="onYearSliderChange"
          />
          <input
            type="range"
            class="range-thumb range-thumb-max"
            :min="yearRange.minYear || 1900"
            :max="yearRange.maxYear || 2100"
            v-model.number="yearSliderMax"
            @input="onYearSliderChange"
          />
        </div>
        <button
          v-if="yearSliderDirty"
          class="btn-reset-year"
          @click="resetYearFilter"
          title="重置年份筛选"
        >重置</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="records.length === 0" class="empty">暂无数据</div>

    <div v-else class="record-list">
      <div
        v-for="record in records" :key="record.id"
        class="record-card"
        :class="{ expanded: expandedId === record.id }"
      >
        <div class="record-summary" @click="toggleExpand(record.id)">
          <div class="record-title">
            <span class="record-id">#{{ record.id }}</span>
            <span class="flag-dot" v-if="record.crawl_status === 'partial'" :title="record.error_message || '数据状态不完整'">⬤</span>
            {{ getRecordTitle(record) }}
          </div>
          <div class="record-meta">
            <span class="meta-tag" v-if="record.source_site">{{ record.source_site }}</span>
            <span class="meta-tag" v-if="record.pub_year">{{ record.pub_year }}</span>
            <span class="meta-tag status-tag" :class="'status-' + record.crawl_status" v-if="record.crawl_status">
              {{ record.crawl_status }}
            </span>
          </div>
          <button class="btn-edit" @click.stop="startEdit(record)">编辑</button>
          <button class="btn-delete" @click.stop="handleDelete(record)">删除</button>
        </div>
        <div v-if="record.crawl_status === 'partial' && record.error_message" class="record-error">
          {{ record.error_message }}
        </div>

        <div v-if="expandedId === record.id" class="record-detail">
          <table class="field-table">
            <tr v-for="field in displayFields" :key="field.key">
              <td class="field-label">{{ field.label }}</td>
              <td class="field-value">
                <template v-if="field.key === 'ai_summary' && record[field.key]">
                  <div class="ai-summary-text">{{ record[field.key] }}</div>
                </template>
                <template v-else>
                  {{ formatFieldValue(record[field.key]) }}
                </template>
              </td>
            </tr>
          </table>
        </div>
      </div>
    </div>

    <div class="pagination" v-if="total > pageSize">
      <button :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
      <div class="page-jump">
        <input v-model.number="jumpToPage" type="number" min="1" :max="totalPages" class="page-jump-input" placeholder="页码" @keyup.enter="goPage(jumpToPage)" />
        <button class="btn-jump" @click="goPage(jumpToPage)">跳转</button>
      </div>
      <button :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>

    <div v-if="editingRecord" class="split-overlay">
      <div class="split-pane">
        <div class="split-left" :style="{ width: leftWidth + '%' }">
          <div class="pane-header">
            <span>PDF 预览 — {{ editingRecord.original_name }}</span>
            <button class="pane-close" @click="handleCloseEdit">&times;</button>
          </div>
          <div class="pdf-container">
            <iframe v-if="pdfUrl" :src="pdfUrl" class="pdf-frame" frameborder="0"></iframe>
            <div v-else-if="pdfLoading" class="pdf-loading">加载 PDF...</div>
            <div v-else class="pdf-error" v-text="pdfError || '无法加载 PDF'"></div>
          </div>
        </div>
        <div class="resize-handle" @mousedown="startResize"></div>
        <div class="split-right">
          <div class="pane-header">
            <span>编辑 — #{{ editingRecord.id }}</span>
            <div class="pane-actions">
              <span v-if="saveStatus" class="save-inline">{{ saveStatus }}</span>
              <button class="btn-cancel-pane" @click="handleCloseEdit">取消</button>
              <button class="btn-save-pane" :disabled="saving" @click="saveEdit">
                {{ saving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
          <div class="edit-body">
            <div class="edit-field" v-for="field in editableFields" :key="field">
              <label>{{ field }}</label>
              <template v-if="isJsonField(field)">
                <textarea v-model="editForm[field]" rows="2" class="field-textarea"></textarea>
                <span class="field-hint">多个值用英文逗号分隔，如：张三, 李四</span>
              </template>
              <template v-else-if="field === 'abstract' || field === 'ai_summary'">
                <textarea v-model="editForm[field]" rows="8" class="field-textarea field-textarea-lg"></textarea>
              </template>
              <template v-else-if="field === 'commentary' || field.length > 20">
                <textarea v-model="editForm[field]" rows="4" class="field-textarea"></textarea>
              </template>
              <template v-else>
                <input v-model="editForm[field]" type="text" class="field-input" />
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { fetchAdminList, updateAdminRecord, deleteAdminRecord, fetchFileUrl } from "../api/admin";

const tabs = [
  { key: "lit", label: "文献元数据 (lit_metadata)", count: null },
  { key: "case", label: "病案元数据 (case_metadata)", count: null },
  { key: "guideline", label: "指南元数据 (guideline_metadata)", count: null },
];

const activeTable = ref("lit");
const records = ref([]);
const editableFields = ref([]);
const loading = ref(false);
const searchQuery = ref("");
const page = ref(1);
const total = ref(0);
const pageSize = 20;
const expandedId = ref(null);
const jumpToPage = ref(null);
const yearRange = ref({ minYear: null, maxYear: null });

const filterCrawlStatus = ref("");
const yearSliderMin = ref(0);
const yearSliderMax = ref(0);
const yearSliderDirty = ref(false);
let yearSliderTimer = null;

const editingRecord = ref(null);
const editForm = ref({});
const editFormOriginal = ref({});
const editUpdatedAt = ref("");
const saving = ref(false);
const saveStatus = ref("");
const fieldErrors = ref({});
const pdfUrl = ref("");
const pdfLoading = ref(false);
const pdfError = ref("");

const leftWidth = ref((5 / 7) * 100); // 默认 PDF:编辑栏 = 5:2
const resizing = ref(false);
let dragOverlay = null;

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const rangeFillStyle = computed(() => {
  const r = yearRange.value;
  const total = (r.maxYear || 2100) - (r.minYear || 1900);
  if (total <= 0) return { left: "0%", width: "100%" };
  const left = ((yearSliderMin.value - (r.minYear || 1900)) / total) * 100;
  const right = ((yearSliderMax.value - (r.minYear || 1900)) / total) * 100;
  return { left: left + "%", width: (right - left) + "%" };
});

const searchPlaceholder = computed(() => {
  switch (activeTable.value) {
    case "case": return "搜索诊断、方剂...";
    default: return "搜索标题、作者、摘要...";
  }
});

const displayFields = computed(() => {
  const record = records.value.find(r => r.id === expandedId.value);
  if (!record) return [];
  const exclude = ["id", "created_at", "updated_at"];
  return Object.keys(record).filter(k => !exclude.includes(k)).map(k => ({ key: k, label: k }));
});

function getRecordTitle(record) {
  if (activeTable.value === "case") {
    return record.tcm_diagnosis || record.western_diagnosis || record.original_name || `#${record.id}`;
  }
  return record.title || record.original_name || `#${record.id}`;
}

function formatFieldValue(val) {
  if (val === null || val === undefined) return "—";
  if (val === true) return "是";
  if (val === false) return "否";
  if (typeof val === "object") return JSON.stringify(val, null, 2);
  return String(val);
}

function isJsonField(key) {
  return ["authors", "keywords"].includes(key);
}

function onYearSliderChange() {
  if (yearSliderMin.value > yearSliderMax.value) {
    const tmp = yearSliderMin.value;
    yearSliderMin.value = yearSliderMax.value;
    yearSliderMax.value = tmp;
  }
  yearSliderDirty.value = true;
  clearTimeout(yearSliderTimer);
  yearSliderTimer = setTimeout(() => doSearch(), 500);
}

function resetYearFilter() {
  yearSliderMin.value = yearRange.value.minYear || 1900;
  yearSliderMax.value = yearRange.value.maxYear || 2100;
  yearSliderDirty.value = false;
  page.value = 1;
  loadData();
}

function hasUnsavedChanges() {
  if (!editingRecord.value) return false;
  for (const key of Object.keys(editForm.value)) {
    if (editForm.value[key] !== editFormOriginal.value[key]) return true;
  }
  return false;
}

async function loadPdf(fileUuid) {
  pdfUrl.value = "";
  pdfLoading.value = true;
  pdfError.value = "";
  try {
    const res = await fetchFileUrl(fileUuid);
    pdfUrl.value = res.data.url || "";
    if (!pdfUrl.value) pdfError.value = "获取文件地址为空";
  } catch (e) {
    pdfError.value = "获取 PDF 预览失败: " + (e.response?.data?.detail || e.message);
  } finally {
    pdfLoading.value = false;
  }
}

async function loadData() {
  loading.value = true;
  try {
    const params = { page: page.value, q: searchQuery.value };
    if (filterCrawlStatus.value) params.crawlStatus = filterCrawlStatus.value;
    if (yearSliderDirty.value) {
      params.yearMin = yearSliderMin.value;
      params.yearMax = yearSliderMax.value;
    }

    const res = await fetchAdminList(activeTable.value, params);
    records.value = res.data.records;
    total.value = res.data.total;
    editableFields.value = res.data.editable_fields || [];
    yearRange.value = { minYear: res.data.year_min, maxYear: res.data.year_max };
    if (!yearSliderDirty.value && yearRange.value.minYear) {
      yearSliderMin.value = yearRange.value.minYear;
      yearSliderMax.value = yearRange.value.maxYear;
    }
    tabs.find(t => t.key === activeTable.value).count = res.data.total;
  } catch (e) {
    console.error("Failed to load records:", e);
  } finally {
    loading.value = false;
  }
}

function switchTable(key) {
  activeTable.value = key;
  expandedId.value = null;
  page.value = 1;
  records.value = [];
  total.value = 0;
  filterCrawlStatus.value = "";
  yearSliderDirty.value = false;
  yearSliderMin.value = 0;
  yearSliderMax.value = 0;
  loadData();
}

function doSearch() {
  page.value = 1;
  loadData();
}

function clearSearch() {
  searchQuery.value = "";
  page.value = 1;
  loadData();
}

function randomPage() {
  if (totalPages.value <= 1) return;
  let target;
  if (totalPages.value === 2) {
    target = page.value === 1 ? 2 : 1;
  } else {
    do {
      target = Math.floor(Math.random() * totalPages.value) + 1;
    } while (target === page.value);
  }
  page.value = target;
  loadData();
  expandedId.value = null;
}

function goPage(p) {
  const num = Math.max(1, Math.min(totalPages.value, Number(p) || 1));
  page.value = num;
  jumpToPage.value = null;
  loadData();
  expandedId.value = null;
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id;
}

function startEdit(record) {
  editingRecord.value = record;
  editForm.value = {};
  editFormOriginal.value = {};
  editUpdatedAt.value = record.updated_at || "";
  fieldErrors.value = {};
  for (const field of editableFields.value) {
    let val = record[field];
    if (isJsonField(field) && Array.isArray(val)) {
      const str = val.join(", ");
      editForm.value[field] = str;
      editFormOriginal.value[field] = str;
    } else {
      const str = val ?? "";
      editForm.value[field] = str;
      editFormOriginal.value[field] = str;
    }
  }
  saveStatus.value = "";
  loadPdf(record.file_uuid);
}

function handleCloseEdit() {
  if (hasUnsavedChanges()) {
    if (!confirm("有未保存的修改，确定关闭吗？")) return;
  }
  editingRecord.value = null;
  editForm.value = {};
  editFormOriginal.value = {};
  editUpdatedAt.value = "";
  fieldErrors.value = {};
  saveStatus.value = "";
  pdfUrl.value = "";
  leftWidth.value = (5 / 7) * 100;
}

function startResize(e) {
  if (resizing.value) return;
  e.preventDefault();
  resizing.value = true;

  // 创建一个透明全屏遮罩，覆盖在 iframe 之上，确保鼠标事件不被 iframe 吞掉
  dragOverlay = document.createElement("div");
  dragOverlay.style.cssText =
    "position:fixed;inset:0;z-index:2147483647;cursor:col-resize;background:transparent;";
  dragOverlay.addEventListener("mousemove", onResize);
  dragOverlay.addEventListener("mouseup", stopResize);
  dragOverlay.addEventListener("mouseleave", stopResize);
  document.body.appendChild(dragOverlay);
}

function stopResize() {
  if (!resizing.value) return;
  resizing.value = false;
  if (dragOverlay) {
    dragOverlay.removeEventListener("mousemove", onResize);
    dragOverlay.removeEventListener("mouseup", stopResize);
    dragOverlay.removeEventListener("mouseleave", stopResize);
    document.body.removeChild(dragOverlay);
    dragOverlay = null;
  }
}

function onResize(e) {
  if (!resizing.value) return;
  const pct = (e.clientX / window.innerWidth) * 100;
  leftWidth.value = Math.max(20, Math.min(80, pct));
}

onBeforeUnmount(stopResize);

async function handleDelete(record) {
  const label = activeTable.value === "lit" ? "文献" : "病案";
  const msg = activeTable.value === "lit"
    ? `确定删除文献「${getRecordTitle(record)}」？\n将同时删除关联的病案及存储文件，此操作不可恢复！`
    : `确定删除病案「${getRecordTitle(record)}」？\n仅删除病案记录，不影响文献，此操作不可恢复！`;
  if (!confirm(msg)) return;
  try {
    await deleteAdminRecord(activeTable.value, record.id);
    records.value = records.value.filter(r => r.id !== record.id);
    total.value -= 1;
    const tab = tabs.find(t => t.key === activeTable.value);
    if (tab) tab.count = (tab.count || 1) - 1;
  } catch (e) {
    alert("删除失败: " + (e.response?.data?.detail || e.message));
  }
}

async function saveEdit() {
  const fields = {};
  fieldErrors.value = {};

  for (const [key, value] of Object.entries(editForm.value)) {
    if (isJsonField(key)) {
      const strVal = (value || "").replaceAll("，", ",").trim();
      if (strVal === "") { fields[key] = []; continue; }
      fields[key] = strVal.split(",").map(s => s.trim()).filter(s => s.length > 0);
    } else {
      fields[key] = value === "" ? null : value;
    }
  }

  if (Object.keys(fieldErrors.value).length > 0) return;

  saving.value = true;
  saveStatus.value = "";
  try {
    const res = await updateAdminRecord(activeTable.value, editingRecord.value.id, fields, editUpdatedAt.value);
    const updated = res.data.record;
    const idx = records.value.findIndex(r => r.id === updated.id);
    if (idx >= 0) Object.assign(records.value[idx], updated);
    editFormOriginal.value = { ...editForm.value };
    editUpdatedAt.value = updated.updated_at || "";
    saveStatus.value = "已保存";
    setTimeout(() => { saveStatus.value = ""; handleCloseEdit(); }, 1500);
  } catch (e) {
    if (e.response?.status === 409) {
      saveStatus.value = "冲突：该记录已被其他人修改，请关闭后刷新重试";
    } else {
      saveStatus.value = "保存失败: " + (e.response?.data?.detail || e.message);
    }
  } finally {
    saving.value = false;
  }
}

function handleKeydown(e) {
  if (e.key === "Escape" && editingRecord.value) {
    handleCloseEdit();
  }
}

onMounted(() => {
  loadData();
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; }
.admin-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0 0 4px; }

.table-tabs { display: flex; gap: 4px; margin: 20px 0 12px; border-bottom: 2px solid #e8e8e8; }
.tab-btn { padding: 8px 16px; border: none; background: transparent; font-size: 13px; color: #666; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: color 0.2s, border-color 0.2s; }
.tab-btn:hover { color: #1a1a2e; }
.tab-btn.active { color: #1a1a2e; font-weight: 600; border-bottom-color: #00796b; }
.tab-count { font-weight: 400; color: #999; font-size: 12px; }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.btn-random { padding: 8px 16px; border: 1px dashed #00796b; border-radius: 6px; background: #fff; color: #00796b; font-size: 13px; cursor: pointer; white-space: nowrap; }
.btn-random:hover { background: #e0f2f1; }
.search-bar { display: flex; gap: 8px; flex: 1; max-width: 480px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; transition: border-color 0.2s; }
.search-input:focus { border-color: #00796b; }
.btn-search { padding: 8px 16px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-search:hover { background: #00695c; }
.btn-clear { padding: 8px 12px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; color: #666; }

.filters { display: flex; align-items: center; gap: 20px; padding: 10px 0; margin-bottom: 12px; border-bottom: 1px solid #eee; flex-wrap: wrap; }
.filter-group { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #666; }
.filter-group label { white-space: nowrap; font-weight: 500; }
.filter-select { padding: 4px 8px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; outline: none; }
.filter-year { width: 70px; padding: 4px 8px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; outline: none; }
.filter-year-group { gap: 10px; }
.year-label { font-size: 12px; color: #333; font-weight: 600; min-width: 70px; white-space: nowrap; }
.range-slider { position: relative; width: 180px; height: 24px; display: flex; align-items: center; }
.range-fill { position: absolute; height: 4px; background: #00796b; border-radius: 2px; pointer-events: none; }
.range-thumb { position: absolute; width: 180px; height: 4px; background: transparent; pointer-events: none; -webkit-appearance: none; appearance: none; outline: none; }
.range-thumb::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 16px; height: 16px; border-radius: 50%; background: #00796b; border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.3); cursor: pointer; pointer-events: all; }
.range-thumb::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: #00796b; border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.3); cursor: pointer; pointer-events: all; }
.range-thumb-max::-webkit-slider-thumb { z-index: 2; }
.range-thumb-min::-webkit-slider-thumb { z-index: 2; }
.btn-reset-year { padding: 2px 8px; border: 1px solid #d0d0d0; border-radius: 4px; background: #fff; font-size: 11px; color: #e65100; cursor: pointer; white-space: nowrap; }
.btn-reset-year:hover { background: #fff3e0; border-color: #e65100; }
.filter-check { display: flex; align-items: center; gap: 4px; cursor: pointer; }
.filter-check input { margin: 0; }
.filter-hint { color: #aaa; font-size: 11px; }

.loading, .empty { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

.record-list { display: flex; flex-direction: column; gap: 8px; }
.record-card { border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden; transition: border-color 0.2s; }
.record-card:hover { border-color: #b0b0b0; }
.record-summary { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; }
.record-error { padding: 0 16px 10px 16px; font-size: 12px; color: #e65100; line-height: 1.5; }
.record-title { flex: 1; font-size: 14px; color: #1a1a2e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 6px; }
.record-id { color: #999; font-size: 12px; }
.flag-dot { font-size: 8px; color: #ef6c00; flex-shrink: 0; }
.flag-dot.bad { color: #e53935; }
.record-meta { display: flex; gap: 6px; flex-shrink: 0; align-items: center; }
.meta-tag { padding: 2px 8px; background: #f0f0f0; border-radius: 4px; font-size: 11px; color: #666; white-space: nowrap; }
.status-tag.status-partial { background: #fff3e0; color: #e65100; }
.status-tag.status-failed { background: #ffebee; color: #c62828; }
.btn-edit { padding: 4px 12px; border: 1px solid #d0d0d0; border-radius: 4px; background: #fff; font-size: 12px; color: #00796b; cursor: pointer; flex-shrink: 0; }
.btn-edit:hover { background: #e0f2f1; }
.btn-delete { padding: 4px 12px; border: 1px solid #e53935; border-radius: 4px; background: #fff; font-size: 12px; color: #e53935; cursor: pointer; flex-shrink: 0; }
.btn-delete:hover { background: #ffebee; }

.record-detail { border-top: 1px solid #e8e8e8; padding: 16px; background: #fafafa; }
.field-table { width: 100%; border-collapse: collapse; }
.field-table tr { border-bottom: 1px solid #e8e8e8; }
.field-table tr:last-child { border-bottom: none; }
.field-label { padding: 6px 12px 6px 0; font-size: 12px; color: #888; white-space: nowrap; vertical-align: top; width: 140px; font-weight: 500; }
.field-value { padding: 6px 0; font-size: 13px; color: #333; word-break: break-all; white-space: pre-wrap; }
.ai-summary-text { max-height: 160px; overflow-y: auto; line-height: 1.6; }

.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 24px; padding-bottom: 32px; }
.pagination button { padding: 6px 16px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; }
.pagination button:disabled { color: #ccc; cursor: default; }
.pagination button:hover:not(:disabled) { border-color: #00796b; color: #00796b; }
.page-jump { display: flex; align-items: center; gap: 4px; }
.page-jump-input { width: 60px; padding: 5px 8px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; text-align: center; outline: none; }
.page-jump-input:focus { border-color: #00796b; }
.btn-jump { padding: 6px 12px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; }
.btn-jump:hover { border-color: #00796b; color: #00796b; }
.page-info { font-size: 13px; color: #666; }

.split-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; }
.split-pane { width: 100%; height: 100%; background: #fff; display: flex; overflow: hidden; }
.split-left { display: flex; flex-direction: column; min-width: 200px; }
.split-right { flex: 1; display: flex; flex-direction: column; min-width: 300px; }
.resize-handle { width: 5px; cursor: col-resize; background: #e0e0e0; flex-shrink: 0; transition: background 0.15s; }
.resize-handle:hover { background: #00796b; }
.pane-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-bottom: 1px solid #e8e8e8; font-size: 13px; font-weight: 500; color: #333; background: #fafafa; flex-shrink: 0; }
.pane-close { width: 32px; height: 32px; border: none; background: #00796b; font-size: 22px; color: #fff; cursor: pointer; border-radius: 6px; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
.pane-close:hover { background: #00695c; }
.pane-actions { display: flex; align-items: center; gap: 8px; }
.pdf-container { flex: 1; background: #525659; overflow: hidden; position: relative; }
.pdf-frame { width: 100%; height: 100%; border: none; }
.pdf-loading, .pdf-error { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #ccc; font-size: 14px; }

.edit-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.edit-field { margin-bottom: 14px; }
.edit-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.field-input, .field-textarea, .field-select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; font-family: inherit; box-sizing: border-box; }
.field-input:focus, .field-textarea:focus, .field-select:focus { border-color: #00796b; }
.field-input.error, .field-textarea.error { border-color: #e53935; }
.field-hint { display: block; font-size: 11px; color: #999; margin-top: 2px; }
.field-hint.error { color: #e53935; }
.field-textarea { resize: vertical; min-height: 60px; }
.field-textarea-lg { min-height: 140px; }
.field-select { width: auto; min-width: 100px; }

.save-inline { font-size: 12px; color: #2e7d32; margin-right: 8px; }
.btn-cancel-pane, .btn-save-pane { padding: 6px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; }
.btn-cancel-pane { border: 1px solid #d0d0d0; background: #fff; color: #666; }
.btn-cancel-pane:hover { background: #f0f0f0; }
.btn-save-pane { border: none; background: #00796b; color: #fff; margin-left: 0; }
.btn-save-pane:hover { background: #00695c; }
.btn-save-pane:disabled { opacity: 0.6; cursor: default; }
</style>
