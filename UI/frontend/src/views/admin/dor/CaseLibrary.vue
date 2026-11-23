<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-text">
        <h1>病案库</h1>
        <p class="header-sub">DOR 病案母版 · {{ CASE_FIELD_COUNT }} 字段 · {{ CASE_GROUPS.length }} 分组</p>
      </div>
      <button class="btn-primary" @click="handleReextract">AI 重新抽取</button>
    </div>

    <div class="toolbar">
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索主诉、证型或编号..."
        />
        <button v-if="searchQuery" class="btn-clear" @click="searchQuery = ''">清除</button>
      </div>
      <div class="filters">
        <div class="filter-group">
          <label>证型</label>
          <select v-model="filterSyndrome" class="filter-select">
            <option value="">全部</option>
            <option v-for="opt in syndromeOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label>治疗阶段</label>
          <select v-model="filterStage" class="filter-select">
            <option value="">全部</option>
            <option v-for="opt in stageOptions" :key="opt" :value="opt">{{ opt }}</option>
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
            <th class="col-num">年龄</th>
            <th class="col-num">AMH</th>
            <th class="col-num">FSH</th>
            <th class="col-num">AFC</th>
            <th class="col-syndrome">证型</th>
            <th class="col-plan">中医方案</th>
            <th class="col-plan">西医方案</th>
            <th class="col-conf">置信度</th>
            <th class="col-status">状态</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in filteredRecords" :key="record.id" class="row-clickable" @click="openDrawer(record)">
            <td class="cell-id">{{ record.id }}</td>
            <td class="cell-num">{{ record.values.case_1 || "—" }}</td>
            <td class="cell-num">{{ record.values.case_10 || "—" }}</td>
            <td class="cell-num">{{ record.values.case_11 || "—" }}</td>
            <td class="cell-num">{{ record.values.case_14 || "—" }}</td>
            <td>
              <span v-if="record.values.case_23" class="badge badge-syndrome">{{ record.values.case_23 }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="cell-plan" :title="record.values.case_26">{{ record.values.case_26 || "—" }}</td>
            <td class="cell-plan" :title="record.values.case_28">{{ record.values.case_28 || "—" }}</td>
            <td>
              <span class="conf" :class="confClass(record.confidence)">{{ formatPct(record.confidence) }}</span>
            </td>
            <td>
              <span class="badge" :class="statusMeta(record.status).cls">{{ statusMeta(record.status).label }}</span>
            </td>
            <td class="cell-actions">
              <button class="btn-sm btn-view" @click.stop="openDrawer(record)">查看</button>
            </td>
          </tr>
          <tr v-if="filteredRecords.length === 0">
            <td colspan="11" class="empty-row">暂无病案记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 详情抽屉 -->
    <transition name="fade">
      <div v-if="drawerRecord" class="drawer-overlay" @click.self="closeDrawer"></div>
    </transition>
    <transition name="slide">
      <aside v-if="drawerRecord" class="drawer">
        <header class="drawer-header">
          <div class="drawer-head-main">
            <span class="drawer-id">{{ drawerRecord.id }}</span>
            <h2 class="drawer-title">{{ drawerRecord.values.case_17 || "未记录主诉" }}</h2>
            <div class="drawer-meta">
              <span class="badge" :class="statusMeta(drawerRecord.status).cls">
                {{ statusMeta(drawerRecord.status).label }}
              </span>
              <span class="drawer-meta-item">
                置信度
                <span class="conf" :class="confClass(drawerRecord.confidence)">
                  {{ formatPct(drawerRecord.confidence) }}
                </span>
              </span>
              <span class="drawer-meta-item">更新于 {{ drawerRecord.updated_at }}</span>
            </div>
          </div>
          <button class="drawer-close" title="关闭" @click="closeDrawer">&times;</button>
        </header>

        <div class="drawer-body">
          <section v-for="group in CASE_GROUPS" :key="group.label" class="field-group">
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
          </section>
        </div>

        <footer class="drawer-footer">
          <button class="btn-cancel" @click="closeDrawer">取消</button>
          <button class="btn-primary" @click="handleSave">保存</button>
        </footer>
      </aside>
    </transition>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import {
  CASE_GROUPS,
  CASE_FIELD_COUNT,
  flattenGroups,
} from "../../../constants/dorFields";
import { CASE_RECORDS, DOR_STATUS_META } from "./mockDorData";

const fields = flattenGroups(CASE_GROUPS);

function optionsOf(key) {
  const field = fields.find((f) => f.key === key);
  return field?.options || [];
}

const syndromeOptions = optionsOf("case_23");
const stageOptions = optionsOf("case_30");

const records = ref(
  CASE_RECORDS.map((r) => ({ ...r, values: { ...r.values } }))
);

const searchQuery = ref("");
const filterSyndrome = ref("");
const filterStage = ref("");
const filterStatus = ref("");

const filteredRecords = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return records.value.filter((r) => {
    if (filterSyndrome.value && r.values.case_23 !== filterSyndrome.value) return false;
    if (filterStage.value && r.values.case_30 !== filterStage.value) return false;
    if (filterStatus.value && r.status !== filterStatus.value) return false;
    if (!q) return true;
    const haystack = [r.id, r.values.case_17, r.values.case_23, r.values.case_26, r.values.case_28]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
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
  return /描述|简述|药名|方剂|穴位|主症|主诉|诊断|治则|组成|操作|方案|标准|依据|指标|不良|评估|原则|排除|纳入|剂量|频次|阈值|阶段|积/.test(desc);
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

/* ───────── 抽屉 ───────── */
const drawerRecord = ref(null);
const editValues = ref({});

function openDrawer(record) {
  drawerRecord.value = record;
  const next = {};
  fields.forEach((f) => {
    next[f.key] = record.values[f.key] ?? "";
  });
  editValues.value = next;
}

function closeDrawer() {
  drawerRecord.value = null;
  editValues.value = {};
}

function nowText() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function handleSave() {
  const target = records.value.find((r) => r.id === drawerRecord.value?.id);
  if (target) {
    target.values = { ...editValues.value };
    target.updated_at = nowText();
  }
  showToast("已保存");
  closeDrawer();
}

function handleReextract() {
  showToast("AI 重新抽取任务已提交（mock）");
}

function handleKeydown(e) {
  if (e.key === "Escape" && drawerRecord.value) closeDrawer();
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  clearTimeout(toastTimer);
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; }

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

.col-id { width: 96px; }
.col-num { width: 70px; }
.col-syndrome { width: 110px; }
.col-plan { min-width: 220px; }
.col-conf { width: 80px; }
.col-status { width: 90px; }
.col-actions { width: 76px; }

.cell-id { color: #888; font-size: 12px; white-space: nowrap; }
.cell-num { white-space: nowrap; }
.cell-plan { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #555; }
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

/* ───────── 抽屉 ───────── */
.drawer-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); z-index: 1000; }
.drawer {
  position: fixed; top: 0; right: 0; bottom: 0; width: 720px; max-width: 100vw;
  background: #fff; z-index: 1001; display: flex; flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.16);
}
.drawer-header { display: flex; align-items: flex-start; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #e8e8e8; background: #fafafa; flex-shrink: 0; }
.drawer-head-main { flex: 1; min-width: 0; }
.drawer-id { font-size: 12px; color: #999; }
.drawer-title { font-size: 16px; font-weight: 600; color: #1a1a2e; margin: 4px 0 8px; line-height: 1.4; }
.drawer-meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 12px; color: #888; }
.drawer-meta-item { display: inline-flex; align-items: center; gap: 4px; }
.drawer-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 22px; line-height: 1; color: #999; cursor: pointer; border-radius: 4px; flex-shrink: 0; }
.drawer-close:hover { background: #f0f0f0; color: #333; }

.drawer-body { flex: 1; overflow-y: auto; padding: 8px 20px 20px; }
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

.drawer-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px; border-top: 1px solid #e8e8e8; background: #fafafa; flex-shrink: 0; }
.btn-cancel { padding: 8px 20px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; color: #666; cursor: pointer; }
.btn-cancel:hover { background: #f0f0f0; }

/* 抽屉过渡 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.slide-enter-active, .slide-leave-active { transition: transform 0.28s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }

/* toast */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
