<template>
  <div>
    <!-- 顶层：任务组列表 -->
    <div v-if="reviewLoading" class="loading">加载中...</div>
    <div v-else-if="reviewGroups.length === 0" class="placeholder-card">
      暂无待复核提交
    </div>
    <template v-else>
      <!-- 下级视图：任务详情 -->
      <template v-if="reviewDetailTask">
        <div class="review-detail-header">
          <button class="btn-sm" @click="closeReviewDetail">← 返回任务列表</button>
          <span class="review-detail-title">任务 #{{ reviewDetailTask.task_id }} · {{ reviewDetailTask.annotator_username }} · {{ tableLabel(reviewDetailTask.table_name) }} · 共 {{ reviewDetailTask.count }} 条</span>
          <span class="review-detail-time">提交于 {{ formatDate(reviewDetailTask.submitted_at) }}</span>
        </div>
        <div class="review-toolbar">
          <label class="review-select-all">
            <input
              type="checkbox"
              class="wiz-checkbox"
              :checked="isDetailAllSelected"
              :disabled="!detailSelectableItems.length"
              @change="toggleDetailSelectAll"
            />
            <span>全选本页</span>
          </label>
          <button
            class="btn-sm btn-review-approve"
            :disabled="!selectedReviewIds.size || batchActing"
            @click="handleBatchApprove"
          >
            批量通过
          </button>
          <button
            class="btn-sm btn-review-reject"
            :disabled="!selectedReviewIds.size || batchActing"
            @click="openBatchReject"
          >
            批量驳回
          </button>
          <button
            class="btn-sm"
            @click="toggleAllExpand"
          >
            {{ isAllExpanded ? "全部收起" : "全部展开" }}
          </button>
          <span class="review-count">
            已选 <strong>{{ selectedReviewIds.size }}</strong> / 本页 {{ detailSelectableItems.length }} · 共 {{ detailItems.length }} 条
          </span>
        </div>

        <div v-if="detailItems.length === 0" class="placeholder-card">
          该任务暂无待复核条目
        </div>
        <div v-else class="review-flat-list" data-testid="review-detail-list">
          <table class="pool-table review-table" data-testid="review-table">
            <thead>
              <tr>
                <th class="rev-col-check"></th>
                <th class="rev-col-id">#记录ID</th>
                <th>标注员</th>
                <th>表类型</th>
                <th>提交值摘要</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in detailItems" :key="item.submission_id">
                <tr
                  class="review-row"
                  :class="{
                    'review-row-core-missing': item.core_missing,
                    'review-row-selected': selectedReviewIds.has(item.submission_id),
                  }"
                >
                  <td class="rev-col-check">
                    <input
                      type="checkbox"
                      class="wiz-checkbox"
                      :checked="selectedReviewIds.has(item.submission_id)"
                      @change="toggleReviewItem(item.submission_id)"
                    />
                  </td>
                  <td class="rev-col-id">#{{ item.record_id }}</td>
                  <td>{{ reviewDetailTask.annotator_username || "—" }}</td>
                  <td>{{ tableLabel(reviewDetailTask.table_name) }}</td>
                  <td class="rev-summary">
                    <span v-if="item.core_missing" class="core-missing-badge">核心缺失</span>
                    <span v-if="!hasDiff(item)" class="badge badge-no-diff">无需修改</span>
                    <span v-else class="badge badge-has-diff">{{ Object.keys(item.proposed_fields || {}).length }} 字段</span>
                  </td>
                  <td>
                    <span class="badge badge-pending">待复核</span>
                  </td>
                  <td class="cell-actions">
                    <button
                      class="btn-sm btn-review-approve"
                      :disabled="actingId === item.submission_id || item.core_missing"
                      @click="handleSingleApprove(item)"
                    >通过</button>
                    <button
                      class="btn-sm btn-review-reject"
                      :disabled="actingId === item.submission_id"
                      @click="openReject(item)"
                    >驳回</button>
                    <button
                      class="btn-sm btn-review-expand"
                      @click="toggleReviewExpand(item.submission_id)"
                    >{{ expandedReviewIds.has(item.submission_id) ? "收起" : "展开" }}</button>
                  </td>
                </tr>
                <tr v-if="expandedReviewIds.has(item.submission_id)" class="review-expand-row">
                  <td colspan="7" class="review-expand-cell">
                    <div v-if="!hasDiff(item)" class="no-diff-placeholder">无需修改</div>
                    <template v-else>
                    <div class="diff-legend"><span class="diff-legend-mark">■</span> 高亮 = 标注员修改的字段</div>
                    <div class="diff-grid">
                      <div class="diff-col diff-col-current">
                        <div class="diff-col-title">当前值</div>
                        <div v-for="field in diffFields(item)" :key="'c-' + field" class="diff-row">
                          <span class="diff-key">{{ field }}</span>
                          <span class="diff-val">{{ formatValue(item.current_values?.[field]) }}</span>
                        </div>
                      </div>
                      <div class="diff-col diff-col-proposed">
                        <div class="diff-col-title">提交值</div>
                        <div v-for="field in diffFields(item)" :key="'p-' + field" class="diff-row">
                          <span class="diff-key">{{ field }}</span>
                          <span
                            class="diff-val"
                            :class="{
                              'diff-changed':
                                formatValue(item.proposed_fields?.[field]) !==
                                formatValue(item.current_values?.[field]),
                            }"
                          >{{ formatValue(item.proposed_fields?.[field]) }}</span>
                        </div>
                      </div>
                    </div>
                    </template>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </template>
      <!-- 顶层：任务组卡片列表 -->
      <div v-else class="review-group-list" data-testid="review-group-list">
        <div
          v-for="group in reviewGroups"
          :key="group.task_id"
          class="review-group-card"
          :data-testid="'review-group-' + group.task_id"
        >
          <div class="review-group-info">
            <span class="review-group-task">任务 #{{ group.task_id }}</span>
            <span class="review-group-annotator">{{ group.annotator_username }}</span>
            <span class="review-group-table">{{ tableLabel(group.table_name) }}</span>
            <span class="review-group-count">{{ group.count }} 条待复核</span>
            <span class="review-group-time">提交于 {{ formatDate(group.submitted_at) }}</span>
          </div>
          <button class="btn-sm btn-assign" @click="openReviewDetail(group)">进入复核</button>
        </div>
      </div>
    </template>

    <!-- ═══════════ 驳回对话框（单条 / 批量共用） ═══════════ -->
    <div v-if="rejectTarget || batchRejecting" class="modal-overlay" @click.self="closeReject">
      <div class="modal-box" data-testid="reject-dialog">
        <div class="modal-header">
          <h2 v-if="batchRejecting">批量驳回（{{ selectedReviewIds.size }} 条）</h2>
          <h2 v-else>驳回提交 #{{ rejectTarget?.submission_id }}（记录 #{{ rejectTarget?.record_id }}）</h2>
          <button class="modal-close" @click="closeReject">&times;</button>
        </div>
        <div class="modal-body">
          <p class="annotator-hint">驳回后选中的条目将带复核意见进入标注员返工箱。</p>
          <div class="form-field">
            <label>复核意见（必填）</label>
            <textarea
              v-model="rejectComment"
              rows="4"
              placeholder="请填写驳回原因，将反馈给标注员"
            ></textarea>
          </div>
          <div v-if="rejectError" class="form-error">{{ rejectError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="closeReject">取消</button>
          <button
            class="btn-save btn-reject-confirm"
            :disabled="rejecting || !rejectComment.trim()"
            @click="confirmReject"
          >
            {{ rejecting ? "驳回中..." : "确认驳回" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import {
  reviewQueue,
  approveSubmission,
  rejectSubmission,
  batchApprove,
  batchReject,
} from "../../../api/annotation";

/* ───────── 字典 ───────── */
const TABLE_LABELS = { lit: "文献元数据", case: "病案元数据", guideline: "指南元数据" };

function tableLabel(name) {
  return TABLE_LABELS[name] || name;
}
function formatDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 4000);
}

/* ───────── 复核队列（分组+下级视图） ───────── */
// 进入详情时首屏自动展开的最大条目数（超出部分由「全部展开」手动触发）
const REVIEW_INITIAL_EXPAND = 20;
const reviewGroups = ref([]);
const reviewLoading = ref(false);
const reviewDetailTask = ref(null);
const selectedReviewIds = ref(new Set());
const expandedReviewIds = ref(new Set());
const actingId = ref(null);
const batchActing = ref(false);

const detailItems = computed(() => (reviewDetailTask.value ? reviewDetailTask.value.items || [] : []));
const detailSelectableItems = computed(() => detailItems.value.filter((i) => !i.core_missing));
const isDetailAllSelected = computed(() => {
  const sel = detailSelectableItems.value;
  return sel.length > 0 && sel.every((i) => selectedReviewIds.value.has(i.submission_id));
});

async function loadReviewGroups() {
  reviewLoading.value = true;
  try {
    const res = await reviewQueue();
    const groups = Array.isArray(res.data) ? res.data : [];
    reviewGroups.value = groups;
    if (reviewDetailTask.value) {
      const updated = groups.find((g) => g.task_id === reviewDetailTask.value.task_id);
      if (updated) {
        reviewDetailTask.value = updated;
        const validIds = new Set(updated.items.map((i) => i.submission_id));
        const nextSelected = new Set([...selectedReviewIds.value].filter((id) => validIds.has(id)));
        if (nextSelected.size !== selectedReviewIds.value.size) {
          selectedReviewIds.value = nextSelected;
        }
        const nextExpanded = new Set([...expandedReviewIds.value].filter((id) => validIds.has(id)));
        if (nextExpanded.size !== expandedReviewIds.value.size) {
          expandedReviewIds.value = nextExpanded;
        }
      } else {
        reviewDetailTask.value = null;
        selectedReviewIds.value = new Set();
        expandedReviewIds.value = new Set();
      }
    }
  } catch (e) {
    reviewGroups.value = [];
    showToast(e.response?.data?.detail || "加载复核队列失败", "error");
  } finally {
    reviewLoading.value = false;
  }
}

function openReviewDetail(group) {
  reviewDetailTask.value = group;
  selectedReviewIds.value = new Set();
  // 首屏只自动展开前 REVIEW_INITIAL_EXPAND 条，避免全量 diff 网格渲染卡顿
  const items = group.items || [];
  const initial = items.slice(0, REVIEW_INITIAL_EXPAND);
  expandedReviewIds.value = new Set(initial.map((i) => i.submission_id));
}

function closeReviewDetail() {
  reviewDetailTask.value = null;
  selectedReviewIds.value = new Set();
  expandedReviewIds.value = new Set();
}

function toggleReviewItem(sid) {
  const next = new Set(selectedReviewIds.value);
  if (next.has(sid)) next.delete(sid);
  else next.add(sid);
  selectedReviewIds.value = next;
}

function toggleDetailSelectAll() {
  const sel = detailSelectableItems.value;
  const allSel = isDetailAllSelected.value;
  const next = new Set(selectedReviewIds.value);
  for (const i of sel) {
    if (allSel) next.delete(i.submission_id);
    else next.add(i.submission_id);
  }
  selectedReviewIds.value = next;
}

function toggleReviewExpand(sid) {
  const next = new Set(expandedReviewIds.value);
  if (next.has(sid)) next.delete(sid);
  else next.add(sid);
  expandedReviewIds.value = next;
}

const isAllExpanded = computed(() => {
  const items = detailItems.value;
  return items.length > 0 && items.every((i) => expandedReviewIds.value.has(i.submission_id));
});

function toggleAllExpand() {
  if (isAllExpanded.value) {
    expandedReviewIds.value = new Set();
  } else {
    expandedReviewIds.value = new Set(detailItems.value.map((i) => i.submission_id));
  }
}

function hasDiff(entry) {
  const p = entry.proposed_fields;
  return !!p && typeof p === "object" && Object.keys(p).length > 0;
}

function diffFields(entry) {
  return Object.keys(entry.proposed_fields || {});
}

function formatValue(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.join("、") : "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

async function handleSingleApprove(entry) {
  actingId.value = entry.submission_id;
  try {
    const res = await approveSubmission(entry.submission_id);
    if (res.data?.status === "expired") {
      showToast(`提交 #${entry.submission_id} 基准冲突，已归档为过期`, "error");
    } else {
      showToast(`提交 #${entry.submission_id} 已通过`);
    }
    removeDetailItem(entry.submission_id);
    await loadReviewGroups();
  } catch (e) {
    showToast(e.response?.data?.detail || "通过失败", "error");
  } finally {
    actingId.value = null;
  }
}

function removeDetailItem(sid) {
  if (reviewDetailTask.value) {
    const idx = reviewDetailTask.value.items.findIndex((i) => i.submission_id === sid);
    if (idx !== -1) {
      reviewDetailTask.value.items.splice(idx, 1);
      reviewDetailTask.value.count = Math.max(0, (reviewDetailTask.value.count || 1) - 1);
    }
  }
  selectedReviewIds.value.delete(sid);
  if (expandedReviewIds.value.has(sid)) {
    const next = new Set(expandedReviewIds.value);
    next.delete(sid);
    expandedReviewIds.value = next;
  }
}

async function handleBatchApprove() {
  const ids = [...selectedReviewIds.value];
  if (!ids.length) return;
  if (!confirm(`确认批量通过 ${ids.length} 条提交？`)) return;
  batchActing.value = true;
  try {
    const res = await batchApprove(ids);
    const d = res.data || {};
    const s = d.summary || d;
    showToast(`通过 ${s.approved ?? 0} · 过期 ${s.expired ?? 0} · 异常 ${s.error ?? 0}`);
    selectedReviewIds.value = new Set();
    expandedReviewIds.value = new Set();
    await loadReviewGroups();
  } catch (e) {
    showToast(e.response?.data?.detail || "批量通过失败", "error");
  } finally {
    batchActing.value = false;
  }
}

/* ─── 驳回对话框 ─── */
const rejectTarget = ref(null);
const batchRejecting = ref(false);
const rejectComment = ref("");
const rejecting = ref(false);
const rejectError = ref("");

function openReject(entry) {
  batchRejecting.value = false;
  rejectTarget.value = entry;
  rejectComment.value = "";
  rejectError.value = "";
}

function openBatchReject() {
  if (!selectedReviewIds.value.size) return;
  rejectTarget.value = null;
  batchRejecting.value = true;
  rejectComment.value = "";
  rejectError.value = "";
}

function closeReject() {
  rejectTarget.value = null;
  batchRejecting.value = false;
  rejectError.value = "";
}

async function confirmReject() {
  const comment = rejectComment.value.trim();
  if (!comment) return;
  rejectError.value = "";
  rejecting.value = true;
  try {
    if (batchRejecting.value) {
      const decisions = [...selectedReviewIds.value].map((sid) => ({ submission_id: sid, comment }));
      const res = await batchReject(decisions);
      const d = res.data || {};
      const s = d.summary || d;
      showToast(`驳回 ${s.rejected ?? 0} · 异常 ${s.error ?? 0}`);
      closeReject();
      selectedReviewIds.value = new Set();
      expandedReviewIds.value = new Set();
      await loadReviewGroups();
    } else if (rejectTarget.value) {
      await rejectSubmission(rejectTarget.value.submission_id, comment);
      showToast(`提交 #${rejectTarget.value.submission_id} 已驳回，条目进入返工箱`);
      removeDetailItem(rejectTarget.value.submission_id);
      closeReject();
      await loadReviewGroups();
    }
  } catch (e) {
    rejectError.value = e.response?.data?.detail || "驳回失败";
  } finally {
    rejecting.value = false;
  }
}

/* ───────── 轮询 ───────── */
let reviewPollTimer = null;
function startReviewPolling() {
  stopReviewPolling();
  reviewPollTimer = setInterval(() => {
    if (!reviewLoading.value && !batchActing.value && !actingId.value && !reviewDetailTask.value) {
      loadReviewGroups();
    }
  }, 15000);
}
function stopReviewPolling() {
  if (reviewPollTimer) {
    clearInterval(reviewPollTimer);
    reviewPollTimer = null;
  }
}

/* ───────── 生命周期 ───────── */
onMounted(() => {
  loadReviewGroups();
  startReviewPolling();
});

onBeforeUnmount(() => {
  stopReviewPolling();
});
</script>

<style scoped>
/* ── 基础 ── */
.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }
.placeholder-card { border: 1px dashed #d0d0d0; border-radius: 10px; padding: 64px 0; text-align: center; color: #999; font-size: 14px; background: #fafafa; }
.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; cursor: pointer; background: #fff; }
.wiz-checkbox { accent-color: #00796b; width: 15px; height: 15px; cursor: pointer; }

/* ── 对话框 ── */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; width: 480px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #e8e8e8; }
.modal-header h2 { font-size: 15px; font-weight: 600; margin: 0; }
.modal-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #999; cursor: pointer; border-radius: 4px; }
.modal-close:hover { background: #f0f0f0; color: #333; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid #e8e8e8; }
.form-field { margin-bottom: 0; }
.form-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.form-field textarea { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; resize: vertical; font-family: inherit; line-height: 1.6; }
.form-field textarea:focus { border-color: #00796b; }
.form-error { color: #c62828; font-size: 12px; margin: 10px 0 0; }
.btn-reject-confirm { background: #c62828; }
.btn-reject-confirm:hover:not(:disabled) { background: #b71c1c; }

/* ── 复核队列（分组+详情视图） ── */

/* 顶层：任务组卡片列表 */
.review-group-list { display: flex; flex-direction: column; gap: 10px; }
.review-group-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: box-shadow 0.15s ease;
}
.review-group-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.10); }

.review-group-info { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; flex: 1; min-width: 0; }
.review-group-task { font-weight: 600; color: #00796b; font-size: 14px; white-space: nowrap; }
.review-group-annotator { font-weight: 500; color: #333; font-size: 13px; }
.review-group-table { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #e0f2f1; color: #00695c; font-size: 12px; }
.review-group-count { font-size: 13px; color: #555; }
.review-group-time { font-size: 12px; color: #999; white-space: nowrap; margin-left: auto; }

/* 详情：任务头 */
.review-detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  margin-bottom: 14px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.review-detail-title { font-weight: 600; font-size: 14px; color: #1a1a2e; flex: 1; }
.review-detail-time { font-size: 12px; color: #999; white-space: nowrap; }

/* 详情表格外层 */
.review-flat-list { overflow-x: auto; }

/* 行基础（仅过渡；背景由 row-selected / row-core-missing 控制） */
.review-row { transition: background 0.15s ease; }

/* ── 工具栏+表头 ── */
.review-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.review-select-all { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #333; cursor: pointer; user-select: none; }
.review-count { margin-left: auto; font-size: 12px; color: #666; }
.review-count strong { color: #00796b; }
.review-pager { display: flex; align-items: center; gap: 10px; }
.review-pager .btn-sm:disabled { opacity: 0.5; cursor: default; }

.review-table { font-size: 13px; }
.rev-col-check { width: 36px; text-align: center; }
.rev-col-id { width: 80px; white-space: nowrap; }
.rev-summary { font-size: 12px; }

.review-row-selected td { background: #f0f7f6 !important; }
.review-row-core-missing td { background: #fff8f8 !important; }
.review-row-core-missing .btn-review-approve { opacity: 0.4; cursor: not-allowed; }

.core-missing-badge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 4px; background: #ffebee; color: #c62828; font-size: 11px; }
.btn-review-approve { color: #00796b; border-color: #b2dfdb; }
.btn-review-approve:hover:not(:disabled) { background: #e0f2f1; }
.btn-review-reject { color: #c62828; border-color: #ef9a9a; }
.btn-review-reject:hover:not(:disabled) { background: #ffebee; }
.btn-review-approve:disabled, .btn-review-reject:disabled { opacity: 0.5; cursor: default; }

.badge-no-diff { background: #f5f5f5; color: #999; }
.badge-has-diff { background: #e0f2f1; color: #00695c; }
.badge-pending { background: #fff8e1; color: #f57f17; }
.btn-review-expand { color: #00796b; border-color: #b2dfdb; }
.btn-review-expand:hover { background: #e0f2f1; }

.review-expand-row td { padding: 0 !important; border-bottom: 1px solid #e0e0e0; }
.review-expand-cell { padding: 12px 16px !important; background: #fafafa; }

.diff-legend { padding: 0 0 6px; font-size: 12px; color: #b06a00; }
.diff-legend-mark { color: #b06a00; }
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; }
.diff-col { min-width: 0; padding: 8px 12px 10px; }
.diff-col-current { border-right: 1px dashed #e0e0e0; }
.diff-col-proposed { background: #f0f7f6; }
.diff-col-title { margin-bottom: 6px; font-size: 11px; font-weight: 600; letter-spacing: 2px; color: #999; }
.diff-col-proposed .diff-col-title { color: #00796b; }
.diff-row { display: flex; align-items: baseline; gap: 10px; padding: 3px 0; border-bottom: 1px dotted #f0f0f0; font-size: 12px; }
.diff-row:last-child { border-bottom: none; }
.diff-key { flex-shrink: 0; width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #999; }
.diff-val { min-width: 0; word-break: break-all; color: #333; }
.diff-col-proposed .diff-val { color: #00695c; font-weight: 500; }
.diff-changed { background: rgba(199, 124, 0, 0.12); border-left: 3px solid #b06a00; }
.no-diff-placeholder { padding: 18px; text-align: center; color: #999; font-size: 13px; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
