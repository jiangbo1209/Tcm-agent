<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>数据管理</h1>
    </div>

    <div class="table-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTable === tab.key }"
        @click="switchTable(tab.key)"
      >
        {{ tab.label }}
        <span class="tab-count" v-if="tab.count !== null">({{ tab.count }})</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          :placeholder="searchPlaceholder"
          @keyup.enter="doSearch"
        />
        <button class="btn-search" @click="doSearch">搜索</button>
        <button v-if="searchQuery" class="btn-clear" @click="clearSearch">清除</button>
      </div>
      <div class="toolbar-info" v-if="total > 0">
        共 {{ total }} 条记录
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="records.length === 0" class="empty">
      {{ searchQuery ? '没有匹配的记录' : '暂无数据' }}
    </div>

    <div v-else class="record-list">
      <div
        v-for="record in records"
        :key="record.id"
        class="record-card"
        :class="{ expanded: expandedId === record.id }"
      >
        <div class="record-summary" @click="toggleExpand(record.id)">
          <div class="record-title">
            <span class="record-id">#{{ record.id }}</span>
            {{ getRecordTitle(record) }}
          </div>
          <div class="record-meta">
            <span class="meta-tag" v-if="record.source_site">{{ record.source_site }}</span>
            <span class="meta-tag" v-if="record.pub_year">{{ record.pub_year }}</span>
            <span class="meta-tag" v-if="record.crawl_status">{{ record.crawl_status }}</span>
          </div>
          <button class="btn-edit" @click.stop="startEdit(record)">编辑</button>
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
      <button :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>

    <div v-if="editingRecord" class="modal-overlay" @click.self="cancelEdit">
      <div class="modal-content">
        <div class="modal-header">
          <h2>编辑记录 #{{ editingRecord.id }}</h2>
          <button class="modal-close" @click="cancelEdit">&times;</button>
        </div>
        <div class="modal-body">
          <div class="edit-field" v-for="field in editableFields" :key="field">
            <label>{{ field }}</label>
            <template v-if="isJsonField(field)">
              <textarea
                v-model="editForm[field]"
                rows="3"
                class="field-textarea"
                :class="{ error: fieldErrors[field] }"
              ></textarea>
              <span class="field-hint" :class="{ error: fieldErrors[field] }">
                {{ fieldErrors[field] || 'JSON 格式，如 ["值1", "值2"]' }}
              </span>
            </template>
            <template v-else-if="field === 'abstract' || field === 'ai_summary' || field === 'commentary' || field.length > 20">
              <textarea
                v-model="editForm[field]"
                rows="4"
                class="field-textarea"
              ></textarea>
            </template>
            <template v-else-if="field === 'is_exact_match'">
              <select v-model="editForm[field]" class="field-select">
                <option :value="true">是</option>
                <option :value="false">否</option>
              </select>
            </template>
            <template v-else>
              <input
                v-model="editForm[field]"
                type="text"
                class="field-input"
              />
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <span class="save-status" v-if="saveStatus">{{ saveStatus }}</span>
          <button class="btn-cancel" @click="cancelEdit" :disabled="saving">取消</button>
          <button class="btn-save" @click="saveEdit" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { fetchAdminList, fetchAdminRecord, updateAdminRecord } from "../api/admin";

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

const editingRecord = ref(null);
const editForm = ref({});
const saving = ref(false);
const saveStatus = ref("");
const fieldErrors = ref({});

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

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
  return Object.keys(record)
    .filter(k => !exclude.includes(k))
    .map(k => ({ key: k, label: k }));
});

function getRecordTitle(record) {
  if (activeTable.value === "case") {
    return record.tcm_diagnosis || record.western_diagnosis || record.original_name || `记录 #${record.id}`;
  }
  return record.title || record.original_name || `记录 #${record.id}`;
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

async function loadData() {
  loading.value = true;
  try {
    const res = await fetchAdminList(activeTable.value, page.value, searchQuery.value);
    records.value = res.data.records;
    total.value = res.data.total;
    editableFields.value = res.data.editable_fields || [];
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

function goPage(p) {
  page.value = p;
  loadData();
  expandedId.value = null;
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id;
}

function startEdit(record) {
  editingRecord.value = record;
  editForm.value = {};
  fieldErrors.value = {};
  for (const field of editableFields.value) {
    let val = record[field];
    if (isJsonField(field) && (typeof val === "object" || Array.isArray(val))) {
      editForm.value[field] = JSON.stringify(val, null, 2);
    } else {
      editForm.value[field] = val ?? "";
    }
  }
  saveStatus.value = "";
}

function cancelEdit() {
  editingRecord.value = null;
  editForm.value = {};
  fieldErrors.value = {};
  saveStatus.value = "";
}

async function saveEdit() {
  const fields = {};
  fieldErrors.value = {};

  for (const [key, value] of Object.entries(editForm.value)) {
    if (isJsonField(key)) {
      const strVal = (value || "").trim();
      if (strVal === "" || strVal === "[]") {
        fields[key] = [];
        continue;
      }
      try {
        fields[key] = JSON.parse(strVal);
      } catch {
        fieldErrors.value[key] = "JSON 格式错误";
      }
    } else if (key === "is_exact_match") {
      fields[key] = value;
    } else {
      fields[key] = value === "" ? null : value;
    }
  }

  if (Object.keys(fieldErrors.value).length > 0) return;

  saving.value = true;
  saveStatus.value = "";
  try {
    const res = await updateAdminRecord(activeTable.value, editingRecord.value.id, fields);
    const updated = res.data.record;
    const idx = records.value.findIndex(r => r.id === updated.id);
    if (idx >= 0) {
      records.value[idx] = { ...records.value[idx], ...updated };
    }
    editingRecord.value = null;
    editForm.value = {};
    saveStatus.value = "";
  } catch (e) {
    saveStatus.value = "保存失败: " + (e.response?.data?.detail || e.message);
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.admin-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 32px;
  height: 100vh;
  overflow-y: auto;
}

.admin-header h1 {
  font-size: 22px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 4px;
}

.table-tabs {
  display: flex;
  gap: 4px;
  margin: 20px 0 16px;
  border-bottom: 2px solid #e8e8e8;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.2s, border-color 0.2s;
}

.tab-btn:hover {
  color: #1a1a2e;
}

.tab-btn.active {
  color: #1a1a2e;
  font-weight: 600;
  border-bottom-color: #00796b;
}

.tab-count {
  font-weight: 400;
  color: #999;
  font-size: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.search-bar {
  display: flex;
  gap: 8px;
  flex: 1;
  max-width: 480px;
}

.search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: #00796b;
}

.btn-search {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: #00796b;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.btn-search:hover {
  background: #00695c;
}

.btn-clear {
  padding: 8px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: #666;
}

.toolbar-info {
  font-size: 13px;
  color: #888;
}

.loading, .empty {
  text-align: center;
  padding: 48px 0;
  color: #999;
  font-size: 14px;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-card {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.record-card:hover {
  border-color: #b0b0b0;
}

.record-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
}

.record-title {
  flex: 1;
  font-size: 14px;
  color: #1a1a2e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-id {
  color: #999;
  font-size: 12px;
  margin-right: 8px;
}

.record-meta {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.meta-tag {
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 4px;
  font-size: 11px;
  color: #666;
  white-space: nowrap;
}

.btn-edit {
  padding: 4px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  color: #00796b;
  cursor: pointer;
  flex-shrink: 0;
}

.btn-edit:hover {
  background: #e0f2f1;
}

.record-detail {
  border-top: 1px solid #e8e8e8;
  padding: 16px;
  background: #fafafa;
}

.field-table {
  width: 100%;
  border-collapse: collapse;
}

.field-table tr {
  border-bottom: 1px solid #e8e8e8;
}

.field-table tr:last-child {
  border-bottom: none;
}

.field-label {
  padding: 6px 12px 6px 0;
  font-size: 12px;
  color: #888;
  white-space: nowrap;
  vertical-align: top;
  width: 140px;
  font-weight: 500;
}

.field-value {
  padding: 6px 0;
  font-size: 13px;
  color: #333;
  word-break: break-all;
  white-space: pre-wrap;
}

.ai-summary-text {
  max-height: 160px;
  overflow-y: auto;
  line-height: 1.6;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding-bottom: 32px;
}

.pagination button {
  padding: 6px 16px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.pagination button:disabled {
  color: #ccc;
  cursor: default;
}

.pagination button:hover:not(:disabled) {
  border-color: #00796b;
  color: #00796b;
}

.page-info {
  font-size: 13px;
  color: #666;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  border-radius: 12px;
  width: 680px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
}

.modal-header h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #1a1a2e;
}

.modal-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  border-radius: 4px;
}

.modal-close:hover {
  background: #f0f0f0;
  color: #333;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.edit-field {
  margin-bottom: 14px;
}

.edit-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #666;
  margin-bottom: 4px;
}

.field-input, .field-textarea, .field-select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.field-input:focus, .field-textarea:focus, .field-select:focus {
  border-color: #00796b;
}

.field-input.error, .field-textarea.error {
  border-color: #e53935;
}

.field-hint {
  display: block;
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.field-hint.error {
  color: #e53935;
}

.field-textarea {
  resize: vertical;
  min-height: 60px;
}

.field-select {
  width: auto;
  min-width: 100px;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #e8e8e8;
}

.save-status {
  flex: 1;
  font-size: 12px;
  color: #e53935;
}

.btn-cancel, .btn-save {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.btn-cancel {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #666;
}

.btn-cancel:hover {
  background: #f0f0f0;
}

.btn-save {
  border: none;
  background: #00796b;
  color: #fff;
}

.btn-save:hover {
  background: #00695c;
}

.btn-save:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
