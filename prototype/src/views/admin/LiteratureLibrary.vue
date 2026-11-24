<template>
  <div class="admin-page" :class="{ 'is-embedded': embedded }">
    <div v-if="!embedded" class="admin-header">
      <div class="header-text">
        <h1>文献库</h1>
        <p class="header-sub">DOR 文献母版 · {{ LIT_FIELD_COUNT }} 字段 · {{ LIT_GROUPS.length }} 分组</p>
      </div>
    </div>

    <div class="toolbar">
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索题名、作者或编号..."
        />
        <button v-if="searchQuery" class="btn-clear" @click="searchQuery = ''">清除</button>
      </div>
      <div class="filters">
        <div class="filter-group">
          <label>研究类型</label>
          <select v-model="filterType" class="filter-select">
            <option value="">全部</option>
            <option v-for="opt in studyTypeOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label>证型</label>
          <select v-model="filterSyndrome" class="filter-select">
            <option value="">全部</option>
            <option v-for="opt in syndromeOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label>状态</label>
          <select v-model="filterStatus" class="filter-select">
            <option value="">全部</option>
            <option v-for="(meta, key) in DOR_STATUS_META" :key="key" :value="key">{{ meta.label }}</option>
          </select>
        </div>
        <span class="result-count">共 {{ filteredRecords.length }} 条</span>
      </div>
    </div>

    <div class="table-wrap">
      <table class="pool-table">
        <thead>
          <tr>
            <th class="col-id">ID</th>
            <th class="col-title">题名</th>
            <th class="col-author">作者</th>
            <th class="col-num">年份</th>
            <th class="col-type">研究类型</th>
            <th class="col-syndrome">证型</th>
            <th class="col-type">干预类型</th>
            <th class="col-conf">置信度</th>
            <th class="col-status">状态</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in pagedList" :key="record.id" class="row-clickable" @click="openEditor(record)">
            <td class="cell-id">{{ record.id }}</td>
            <td class="cell-title" :title="record.values.lit_1">{{ record.values.lit_1 || "—" }}</td>
            <td class="cell-author" :title="record.values.lit_2">{{ record.values.lit_2 || "—" }}</td>
            <td class="cell-num">{{ record.values.lit_3 || "—" }}</td>
            <td class="cell-type">{{ record.values.lit_4 || "—" }}</td>
            <td>
              <span v-if="record.values.lit_15" class="badge badge-syndrome">{{ record.values.lit_15 }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="cell-type">{{ record.values.lit_18 || "—" }}</td>
            <td>
              <span class="conf" :class="confClass(record.confidence)">{{ formatPct(record.confidence) }}</span>
            </td>
            <td>
              <span class="badge" :class="statusMeta(record.status).cls">{{ statusMeta(record.status).label }}</span>
            </td>
            <td class="cell-actions">
              <button class="btn-sm btn-view" @click.stop="openEditor(record)">编辑</button>
            </td>
          </tr>
          <tr v-if="filteredRecords.length === 0">
            <td colspan="10" class="empty-row">暂无文献记录</td>
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
        <span class="page-info">第 {{ page }} / {{ pageCount }} 页 · 共 {{ filteredRecords.length }} 条</span>
        <div class="pager-btns">
          <button class="btn-sm" :disabled="page <= 1" @click="page--">上一页</button>
          <button class="btn-sm" :disabled="page >= pageCount" @click="page++">下一页</button>
        </div>
      </div>


    <!-- 原文 / 字段分栏编辑器 -->
    <transition name="editor-fade">
      <div v-if="editingRecord" class="editor-overlay">
        <header class="editor-top">
          <div class="editor-top-main">
            <span class="editor-id">{{ editingRecord.id }}</span>
            <span class="badge" :class="statusMeta(editingRecord.status).cls">
              {{ statusMeta(editingRecord.status).label }}
            </span>
            <span class="editor-meta">
              置信度
              <span class="conf" :class="confClass(editingRecord.confidence)">
                {{ formatPct(editingRecord.confidence) }}
              </span>
            </span>
            <span class="editor-meta">更新于 {{ editingRecord.updated_at }}</span>
          </div>
          <button class="editor-close" title="关闭" @click="closeEditor">&times;</button>
        </header>

        <div ref="editorBodyRef" class="editor-body">
          <section class="editor-pane editor-source" :style="{ width: sourceWidth + '%' }">
            <div class="pane-head">
              <span class="pane-label">原文</span>
              <span v-if="original" class="pane-hint">{{ original.source }}</span>
            </div>
            <div class="pane-scroll">
              <template v-if="original">
                <p class="source-title">{{ original.title }}</p>
                <pre class="source-body">{{ original.body }}</pre>
              </template>
              <p v-else class="source-empty">暂无原文</p>
            </div>
          </section>

          <div
            class="editor-splitter"
            :class="{ dragging: resizing }"
            title="拖动调整宽度"
            @pointerdown.prevent="startResize"
          ></div>

          <section class="editor-pane editor-fields">
            <div class="pane-head">
              <span class="pane-label">字段编辑</span>
              <span class="pane-hint">{{ LIT_FIELD_COUNT }} 字段 · {{ LIT_GROUPS.length }} 分组</span>
            </div>
            <div class="pane-scroll form-scroll">
              <div v-for="group in LIT_GROUPS" :key="group.label" class="field-group">
                <h3 class="group-title">
                  {{ group.label }}
                  <span class="group-count">{{ group.fields.length }}</span>
                </h3>
                <div class="field-grid">
                  <div
                    v-for="field in group.fields"
                    :key="field.key"
                    class="field-item"
                    :class="{ 'field-item-wide': isMultiline(field) }"
                  >
                    <label class="field-label" :title="field.desc">
                      {{ field.label }}<span v-if="field.required" class="required">*</span>
                    </label>
                    <select
                      v-if="field.options"
                      v-model="editValues[field.key]"
                      class="field-control"
                      :title="field.desc"
                    >
                      <option value="">— 请选择 —</option>
                      <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                    <textarea
                      v-else-if="isMultiline(field)"
                      v-model="editValues[field.key]"
                      rows="2"
                      class="field-control"
                      :placeholder="field.desc"
                      :title="field.desc"
                    ></textarea>
                    <input
                      v-else
                      v-model="editValues[field.key]"
                      type="text"
                      class="field-control"
                      :placeholder="field.desc"
                      :title="field.desc"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <footer class="editor-footer">
          <button class="btn-cancel" @click="closeEditor">取消</button>
          <button class="btn-primary" @click="handleSave">保存</button>
        </footer>
      </div>
    </transition>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount , watch} from "vue";
import {
  LIT_GROUPS,
  LIT_FIELD_COUNT,
  flattenGroups,
} from "../../constants/dorFields";
import { LIT_RECORDS, DOR_STATUS_META } from "../../data/dorMock";
import { ORIGINALS } from "../../data/originals";

const props = defineProps({
  embedded: { type: Boolean, default: false },
  initialRecordId: { type: String, default: "" },
});

const fields = flattenGroups(LIT_GROUPS);

function optionsOf(key) {
  const field = fields.find((f) => f.key === key);
  return field?.options || [];
}

const studyTypeOptions = optionsOf("lit_4");
const syndromeOptions = optionsOf("lit_15");

const records = ref(
  LIT_RECORDS.map((r) => ({ ...r, values: { ...r.values } }))
);

const searchQuery = ref("");
const filterType = ref("");
const filterSyndrome = ref("");
const filterStatus = ref("");

const filteredRecords = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return records.value.filter((r) => {
    if (filterType.value && r.values.lit_4 !== filterType.value) return false;
    if (filterSyndrome.value && r.values.lit_15 !== filterSyndrome.value) return false;
    if (filterStatus.value && r.status !== filterStatus.value) return false;
    if (!q) return true;
    const haystack = [r.id, r.values.lit_1, r.values.lit_2, r.values.lit_19]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
});

const PAGE_SIZES = [10, 20, 50, 100];
const page = ref(1);
const pageSize = ref(10);

const pageCount = computed(() =>
  Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value))
);

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredRecords.value.slice(start, start + pageSize.value);
});

watch([filterType, pageSize], () => {
  page.value = 1;
});

watch(pageCount, (n) => {
  if (page.value > n) page.value = n;
});

function statusMeta(status) {
  return DOR_STATUS_META[status] || { label: status || "—", cls: "badge-default" };
}

function formatPct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return Math.round(num * 100) + "%";
}

function confClass(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "conf-low";
  if (num >= 0.85) return "conf-high";
  if (num >= 0.6) return "conf-mid";
  return "conf-low";
}

function isMultiline(field) {
  const desc = field.desc || "";
  if (field.label.length > 9) return true;
  return /描述|简述|药名|方剂|穴位|主症|主诉|诊断|治则|组成|操作|方案|标准|依据|指标|不良|评估|原则|排除|纳入|剂量|频次|阈值/.test(desc);
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 3000);
}

/* ───────── 分栏编辑器 ───────── */
const editingRecord = ref(null);
const editValues = ref({});

const original = computed(() =>
  editingRecord.value ? ORIGINALS[editingRecord.value.id] || null : null
);

function openEditor(record) {
  editingRecord.value = record;
  const next = {};
  fields.forEach((f) => {
    next[f.key] = record.values[f.key] ?? "";
  });
  editValues.value = next;
}

const sourceWidth = ref(40);
const resizing = ref(false);
const editorBodyRef = ref(null);

function startResize() {
  resizing.value = true;
  window.addEventListener("pointermove", onResizeMove);
  window.addEventListener("pointerup", stopResize);
}

function onResizeMove(e) {
  if (!resizing.value || !editorBodyRef.value) return;
  const rect = editorBodyRef.value.getBoundingClientRect();
  if (!rect.width) return;
  const pct = ((e.clientX - rect.left) / rect.width) * 100;
  sourceWidth.value = Math.min(80, Math.max(20, pct));
}

function stopResize() {
  resizing.value = false;
  window.removeEventListener("pointermove", onResizeMove);
  window.removeEventListener("pointerup", stopResize);
}

function closeEditor() {
  editingRecord.value = null;
  editValues.value = {};
}

function nowText() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function handleSave() {
  const target = records.value.find((r) => r.id === editingRecord.value?.id);
  if (target) {
    target.values = { ...editValues.value };
    target.updated_at = nowText();
  }
  showToast("已保存");
  closeEditor();
}

function handleKeydown(e) {
  if (e.key === "Escape" && editingRecord.value) closeEditor();
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  if (props.initialRecordId) {
    const target = records.value.find((r) => r.id === props.initialRecordId);
    if (target) openEditor(target);
  }
});

onBeforeUnmount(() => {
  clearTimeout(toastTimer);
  window.removeEventListener("keydown", handleKeydown);
 stopResize(); });
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; }
.admin-page.is-embedded { padding: 0; }

.admin-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.header-text h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0 0 4px; }
.header-sub { margin: 0; font-size: 12px; color: #888; }

.btn-primary { padding: 8px 18px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; white-space: nowrap; transition: background 0.15s; }
.btn-primary:hover { background: #00695c; }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.search-bar { display: flex; gap: 8px; flex: 1; max-width: 360px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; transition: border-color 0.2s; }
.search-input:focus { border-color: #00796b; }
.btn-clear { padding: 8px 12px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; color: #666; cursor: pointer; }
.btn-clear:hover { background: #f5f5f5; }

.filters { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.filter-group { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #666; }
.filter-group label { white-space: nowrap; font-weight: 500; }
.filter-select { padding: 5px 8px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; color: #333; outline: none; background: #fff; }
.filter-select:focus { border-color: #00796b; }
.result-count { font-size: 12px; color: #888; white-space: nowrap; }

.table-wrap { overflow-x: auto; border: 1px solid #e8e8e8; border-radius: 8px; }
.pool-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pool-table th { text-align: left; padding: 10px 12px; background: #f5f5f5; color: #666; font-weight: 500; border-bottom: 2px solid #e0e0e0; white-space: nowrap; }
.pool-table td { padding: 10px 12px; border-bottom: 1px solid #eee; color: #333; vertical-align: middle; }
.pool-table tbody tr:last-child td { border-bottom: none; }
.row-clickable { cursor: pointer; transition: background 0.15s; }
.row-clickable:hover { background: #f0f7f6; }

.col-id { width: 90px; }
.col-title { min-width: 300px; }
.col-author { min-width: 120px; }
.col-num { width: 64px; }
.col-type { min-width: 110px; }
.col-syndrome { min-width: 100px; }
.col-conf { width: 80px; }
.col-status { width: 90px; }
.col-actions { width: 76px; }

.cell-id { color: #888; font-size: 12px; white-space: nowrap; }
.cell-title { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #1a1a2e; }
.cell-author { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #666; }
.cell-num { white-space: nowrap; }
.cell-type { white-space: nowrap; }
.cell-actions { white-space: nowrap; }
.text-muted { color: #bbb; }
.empty-row { text-align: center; color: #999; padding: 48px 12px !important; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; white-space: nowrap; }
.badge-extracted { background: #e8f5e9; color: #2e7d32; }
.badge-review { background: #fff8e1; color: #f57f17; }
.badge-failed { background: #ffebee; color: #c62828; }
.badge-default { background: #f5f5f5; color: #666; }
.badge-syndrome { background: #e0f2f1; color: #00695c; }

.conf { font-size: 12px; font-weight: 600; }
.conf-high { color: #2e7d32; }
.conf-mid { color: #ef6c00; }
.conf-low { color: #c62828; }

.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; background: #fff; cursor: pointer; }
.btn-view { color: #00796b; border-color: #b2dfdb; }
.btn-view:hover { background: #e0f2f1; }

/* ───────── 全屏分栏编辑器 ───────── */
.editor-overlay { position: fixed; inset: 0; z-index: 100; background: #fff; display: flex; flex-direction: column; }
.editor-top { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-bottom: 1px solid #e8e8e8; background: #fafafa; flex-shrink: 0; }
.editor-top-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.editor-id { font-size: 14px; font-weight: 600; color: #1a1a2e; }
.editor-meta { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: #888; }
.editor-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 22px; line-height: 1; color: #999; cursor: pointer; border-radius: 4px; flex-shrink: 0; }
.editor-close:hover { background: #f0f0f0; color: #333; }

.editor-body { flex: 1; min-height: 0; display: flex; }
.editor-pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.editor-source { flex: 0 0 auto; background: #fafafa; min-width: 0; }
.editor-splitter { flex: 0 0 7px; cursor: col-resize; background: #f0f2f2; border-left: 1px solid #e8e8e8; border-right: 1px solid #e8e8e8; position: relative; touch-action: none; transition: background 0.15s; }
.editor-splitter::after { content: ""; position: absolute; top: 50%; left: 50%; width: 3px; height: 34px; transform: translate(-50%, -50%); border-radius: 3px; background: #c9d6d4; }
.editor-splitter:hover, .editor-splitter.dragging { background: var(--teal-soft, #e0f2f1); }
.editor-splitter:hover::after, .editor-splitter.dragging::after { background: var(--teal, #00796b); }
.editor-fields { flex: 1 1 auto; min-width: 0; }
.pane-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 16px; border-bottom: 1px solid #ececec; flex-shrink: 0; }
.pane-label { font-size: 12px; font-weight: 600; color: #00796b; letter-spacing: 0.5px; }
.pane-hint { font-size: 11px; color: #999; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pane-scroll { flex: 1; overflow-y: auto; padding: 16px; }

.source-title { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #1a1a2e; line-height: 1.5; }
.source-body { margin: 0; font-family: inherit; font-size: 13px; line-height: 1.8; color: #444; white-space: pre-wrap; word-break: break-word; }
.source-empty { margin: 0; padding: 32px 0; text-align: center; font-size: 13px; color: #aaa; }

.form-scroll { padding: 8px 20px 20px; }
.field-group { padding: 14px 0 4px; border-bottom: 1px dashed #ececec; }
.field-group:last-child { border-bottom: none; }
.group-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #00796b; margin: 0 0 10px; }
.group-title::before { content: ""; width: 3px; height: 13px; border-radius: 2px; background: #00796b; }
.group-count { font-size: 11px; font-weight: 400; color: #999; background: #f0f0f0; border-radius: 8px; padding: 0 6px; }

.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
.field-item { min-width: 0; }
.field-item-wide { grid-column: 1 / -1; }
.field-label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.required { color: #e53935; margin-left: 2px; }
.field-control {
  width: 100%; box-sizing: border-box; padding: 7px 10px; border: 1px solid #d0d0d0; border-radius: 6px;
  font-size: 13px; font-family: inherit; color: #333; background: #fff; outline: none; transition: border-color 0.15s;
}
.field-control:focus { border-color: #00796b; }
textarea.field-control { resize: vertical; min-height: 52px; line-height: 1.4; }

.editor-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px; border-top: 1px solid #e8e8e8; background: #fafafa; flex-shrink: 0; }
.btn-cancel { padding: 8px 20px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; color: #666; cursor: pointer; }
.btn-cancel:hover { background: #f0f0f0; }

/* 编辑器过渡 */
.editor-fade-enter-active, .editor-fade-leave-active { transition: opacity 0.2s ease; }
.editor-fade-enter-from, .editor-fade-leave-to { opacity: 0; }

@media (max-width: 960px) {
  .editor-body { flex-direction: column; }
  .editor-splitter { display: none; }
  .editor-source { height: 40%; }
  .editor-source { border-bottom: 1px solid #e8e8e8; }
}

/* toast */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }

/* ── 分页 ── */
.pager-bar { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
.page-size { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b7280; }
.page-size .filter-select { padding: 4px 8px; }
.page-info { font-size: 12px; color: #9ca3af; margin-left: auto; }
.pager-btns { display: flex; gap: 8px; }
.pager-btns .btn-sm:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
