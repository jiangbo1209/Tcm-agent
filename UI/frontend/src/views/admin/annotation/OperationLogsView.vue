<template>
  <div>
    <div class="log-filters">
      <select v-model="logFilters.table_name" class="filter-select" data-testid="log-filter-table" @change="resetAndLoadLogs">
        <option value="">全部表</option>
        <option value="lit">文献元数据</option>
        <option value="case">病案元数据</option>
        <option value="guideline">指南元数据</option>
      </select>
      <select v-model="logCategoryFilter" class="filter-select" data-testid="log-filter-category" @change="handleCategoryChange">
        <option value="">全部分类</option>
        <option value="任务记录">任务记录</option>
        <option value="修改记录">修改记录</option>
        <option value="复核记录">复核记录</option>
      </select>
      <select v-model="logFilters.action" class="filter-select" data-testid="log-filter-action" @change="resetAndLoadLogs">
        <option value="">全部动作</option>
        <option v-for="a in filteredLogActions" :key="a" :value="a">{{ actionMeta(a).label }}</option>
      </select>
      <input
        v-model="logFilters.record_id"
        type="number"
        placeholder="记录 ID"
        class="filter-input"
        data-testid="log-filter-record-id"
        @keyup.enter="resetAndLoadLogs"
      />
      <button class="btn-sm btn-assign" data-testid="log-search-btn" @click="resetAndLoadLogs">查询</button>
    </div>

    <div v-if="logsLoading" class="loading">加载中...</div>
    <template v-else>
      <div class="table-wrap">
        <table class="pool-table logs-table" data-testid="logs-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>时间</th>
              <th>操作人</th>
              <th>表</th>
              <th>记录</th>
              <th>分类</th>
              <th>动作</th>
              <th>变更摘要</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in displayedLogs" :key="log.id">
              <td>{{ log.id }}</td>
              <td class="cell-time">{{ formatDate(log.created_at) }}</td>
              <td>{{ log.username || "—" }}</td>
              <td>{{ tableLabel(log.table_name) }}</td>
              <td>#{{ log.record_id }}</td>
              <td>
                <span v-if="getCategory(log.action)" class="badge" :class="categoryMeta(getCategory(log.action)).cls">
                  {{ categoryMeta(getCategory(log.action)).label }}
                </span>
                <span v-else class="badge badge-category-neutral">—</span>
              </td>
              <td>
                <span class="badge" :class="actionMeta(log.action).cls">
                  {{ actionMeta(log.action).label }}
                </span>
              </td>
              <td class="cell-summary">{{ changeSummary(log) }}</td>
              <td class="cell-actions">
                <button
                  v-if="hasOldFields(log) && (log.action === 'approve' || log.action === 'save_direct')"
                  class="btn-sm btn-toggle"
                  :disabled="rollingBackId === log.id"
                  data-testid="log-rollback-btn"
                  @click="handleRollback(log)"
                >
                  {{ rollingBackId === log.id ? "回滚中..." : "回滚" }}
                </button>
              </td>
            </tr>
            <tr v-if="displayedLogs.length === 0">
              <td colspan="9" class="empty-row">暂无日志</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pager">
        <button class="btn-sm" :disabled="logPage <= 1 || logsLoading" @click="goLogPage(logPage - 1)">
          上一页
        </button>
        <span class="pager-info">第 {{logPage}}/{{logPageCount}} 页 · 共 {{logTotal}} 条</span>
        <button
          class="btn-sm"
          :disabled="logPage >= logPageCount || logsLoading"
          @click="goLogPage(logPage + 1)"
        >
          下一页
        </button>
      </div>
    </template>

    <!-- toast -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { queryLogs, rollbackLog } from "../../../api/annotation";

/* ───────── 字典 ───────── */
const TABLE_LABELS = { lit: "文献元数据", case: "病案元数据", guideline: "指南元数据" };

function tableLabel(name) {
  return TABLE_LABELS[name] || name;
}

function formatDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

/* ───────── toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 4000);
}

/* ───────── 操作记录 ───────── */
const LOG_ACTIONS = [
  "approve",
  "reject",
  "expire",
  "rollback",
  "save_direct",
  "claim",
  "assign",
  "draft",
  "no_change",
  "submit",
];
const ACTION_META = {
  approve: { label: "通过", cls: "badge-action-approve" },
  reject: { label: "驳回", cls: "badge-action-reject" },
  expire: { label: "过期", cls: "badge-action-expire" },
  rollback: { label: "回滚", cls: "badge-action-rollback" },
  save_direct: { label: "直改", cls: "badge-action-neutral" },
  claim: { label: "领取", cls: "badge-action-neutral" },
  assign: { label: "代派", cls: "badge-action-neutral" },
  draft: { label: "草稿", cls: "badge-action-neutral" },
  no_change: { label: "无变更", cls: "badge-action-neutral" },
  submit: { label: "提交", cls: "badge-action-submit" },
};

const ACTION_CATEGORIES = {
  "任务记录": ["claim", "assign", "submit", "expire"],
  "修改记录": ["draft", "no_change", "save_direct", "rollback"],
  "复核记录": ["approve", "reject"],
};

const ACTION_CATEGORY_MAP = Object.fromEntries(
  Object.entries(ACTION_CATEGORIES).flatMap(([cat, acts]) => acts.map((a) => [a, cat]))
);

const CATEGORY_META = {
  "任务记录": { label: "任务记录", cls: "badge-category-task" },
  "修改记录": { label: "修改记录", cls: "badge-category-edit" },
  "复核记录": { label: "复核记录", cls: "badge-category-review" },
};

function actionMeta(action) {
  return ACTION_META[action] || { label: action, cls: "badge-action-neutral" };
}

function getCategory(action) {
  return ACTION_CATEGORY_MAP[action] || "";
}

function categoryMeta(category) {
  return CATEGORY_META[category] || { label: category, cls: "badge-category-neutral" };
}

const LOG_PAGE_SIZE = 20;
const logFilters = ref({ table_name: "", action: "", record_id: "" });
const logCategoryFilter = ref("");
const logPage = ref(1);
const logTotal = ref(0);
const logs = ref([]);
const logsLoading = ref(false);
const rollingBackId = ref(null);

const logPageCount = computed(() => Math.max(1, Math.ceil(logTotal.value / LOG_PAGE_SIZE)));

const filteredLogActions = computed(() => {
  if (!logCategoryFilter.value) return LOG_ACTIONS;
  return ACTION_CATEGORIES[logCategoryFilter.value] || [];
});

const displayedLogs = computed(() => {
  if (!logCategoryFilter.value) return logs.value;
  const allowed = new Set(ACTION_CATEGORIES[logCategoryFilter.value] || []);
  return logs.value.filter((l) => allowed.has(l.action));
});

function handleCategoryChange() {
  const allowed = new Set(filteredLogActions.value);
  if (logFilters.value.action && !allowed.has(logFilters.value.action)) {
    logFilters.value.action = "";
  }
  resetAndLoadLogs();
}

function logParams() {
  const f = logFilters.value;
  const params = { page: logPage.value, page_size: LOG_PAGE_SIZE };
  if (f.table_name) params.table_name = f.table_name;
  if (f.action) params.action = f.action;
  if (f.record_id !== "" && f.record_id !== null && Number.isFinite(Number(f.record_id))) {
    params.record_id = Number(f.record_id);
  }
  return params;
}

async function loadLogs() {
  logsLoading.value = true;
  try {
    const res = await queryLogs(logParams());
    logs.value = Array.isArray(res.data?.items) ? res.data.items : [];
    logTotal.value = res.data?.total ?? 0;
  } catch (e) {
    logs.value = [];
    showToast(e.response?.data?.detail || "加载日志失败", "error");
  } finally {
    logsLoading.value = false;
  }
}

function resetAndLoadLogs() {
  logPage.value = 1;
  loadLogs();
}

function goLogPage(page) {
  if (page < 1 || page > logPageCount.value) return;
  logPage.value = page;
  loadLogs();
}

function hasOldFields(log) {
  return !!log.old_fields && typeof log.old_fields === "object" && Object.keys(log.old_fields).length > 0;
}

// 变更摘要单值：数组顿号连接，对象 JSON 化，空值显示 "-"
function compactValue(v) {
  if (v === null || v === undefined || v === "") return "-";
  if (Array.isArray(v)) return v.length ? v.join("、") : "-";
  if (typeof v === "object") return JSON.stringify(v);
  return `"${String(v)}"`;
}

function changeSummary(log) {
  const oldF = log.old_fields || {};
  const newF = log.new_fields || {};
  const keys = [...new Set([...Object.keys(oldF), ...Object.keys(newF)])];
  if (keys.length === 0) return "-";
  return keys.map((k) => `${k}: ${compactValue(oldF[k])} → ${compactValue(newF[k])}`).join("; ");
}

async function handleRollback(log) {
  const restoreKeys = Object.keys(log.old_fields || {});
  const detail = restoreKeys
    .map((k) => `${k}: ${compactValue(log.new_fields?.[k])} → ${compactValue(log.old_fields[k])}`)
    .join("; ");
  if (
    !confirm(
      `确定回滚日志 #${log.id} 吗？\n将把记录 #${log.record_id}（${tableLabel(log.table_name)}）恢复为：\n${detail}`
    )
  ) {
    return;
  }
  rollingBackId.value = log.id;
  try {
    await rollbackLog(log.id);
    showToast(`日志 #${log.id} 已回滚，记录 #${log.record_id} 字段已恢复`);
    await loadLogs(); // 重取当前页：列表顶部会出现新的 rollback 审计行
  } catch (e) {
    showToast(e.response?.data?.detail || "回滚失败", "error");
  } finally {
    rollingBackId.value = null;
  }
}

onMounted(() => {
  resetAndLoadLogs();
});
</script>

<style scoped>
/* ── 操作记录 ── */
.log-filters { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.filter-select, .filter-input { padding: 7px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; background: #fff; outline: none; }
.filter-select:focus, .filter-input:focus { border-color: #00796b; }
.filter-input { width: 130px; }

.logs-table .cell-summary { max-width: 420px; word-break: break-all; color: #555; font-size: 12px; }

.badge-action-approve { background: #e8f5e9; color: #2e7d32; }
.badge-action-reject { background: #ffebee; color: #c62828; }
.badge-action-expire { background: #fff8e1; color: #f57f17; }
.badge-action-rollback { background: #ede7f6; color: #5e35b1; }
.badge-action-submit { background: #e0f2f1; color: #00695c; }
.badge-action-neutral { background: #f5f5f5; color: #666; }

.badge-category-task { background: #e3f2fd; color: #1565c0; }
.badge-category-edit { background: #fff3e0; color: #e65100; }
.badge-category-review { background: #f3e5f5; color: #6a1b9a; }
.badge-category-neutral { background: #f5f5f5; color: #999; }

.pager { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.pager-info { font-size: 12px; color: #888; }
.pager .btn-sm:disabled { opacity: 0.5; cursor: default; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }

.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; cursor: pointer; background: #fff; }
.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }
</style>
