<template>
  <div class="annotation-workbench">
    <div class="wb-header">
      <h1>标注工作台</h1>
      <button
        v-if="reworkCount > 0"
        type="button"
        class="rework-badge"
        data-testid="rework-badge"
        title="查看待返工条目"
        @click="openReworkDrawer"
      >
        待返工 {{ reworkCount }}
      </button>
    </div>

    <!-- 初始加载 -->
    <div v-if="view === 'loading'" class="wb-loading">加载中...</div>

    <!-- 功能总闸未开启（503，A5） -->
    <div v-else-if="view === 'disabled'" class="wb-empty" data-testid="feature-disabled">
      <p class="empty-title">功能未开启</p>
      <p class="empty-hint">数据标注功能尚未开放，请联系管理员。</p>
    </div>

    <!-- 领取面板：无进行中任务时展示 -->
    <div v-else-if="view === 'claim'" class="claim-panel" data-testid="claim-panel">
      <div class="panel-card">
        <h2>领取标注任务</h2>
        <p class="panel-hint">
          点击下方按钮领取一批待标注数据（每次最多 50 条），
          领取后须在截止时间内完成并提交。
        </p>
        <p v-if="claimError" class="panel-error">{{ claimError }}</p>
        <button class="btn-primary" :disabled="claiming" @click="handleClaim">
          {{ claiming ? "领取中..." : "领取任务" }}
        </button>
      </div>
    </div>

    <!-- 任务卡片：有进行中任务时展示 -->
    <div v-else class="task-card" data-testid="task-card">
      <template v-if="!taskCompleted">
        <div class="task-meta">
          <span class="meta-label">所属表</span>
          <span class="meta-value">{{ task.table_name }}</span>
        </div>
        <div class="task-meta">
          <span class="meta-label">进度</span>
          <span class="meta-value">{{ completedCount }}/{{ task.count }}</span>
        </div>
        <div class="task-meta">
          <span class="meta-label">剩余时间</span>
          <span class="meta-value countdown" :class="{ expired }">{{ countdownText }}</span>
        </div>
      </template>
      <!-- 整批提交成功后的完成态 -->
      <template v-else>
        <div class="task-done">
          <span class="done-title">已提交复核</span>
          <span class="done-hint">
            本批 {{ submitResult?.count ?? task.count }} 条已进入复核流程，可领取下一批继续。
          </span>
          <p v-if="staleIds.length" class="stale-warning" data-testid="stale-warning">
            ⚠ 以下条目的基准数据在暂存后被他人更新，请复核时留意：
            #{{ staleIds.join("、#") }}
          </p>
          <button class="btn-primary" data-testid="claim-next" @click="claimNextBatch">
            领取下一批
          </button>
        </div>
      </template>
    </div>

    <!-- 条目列表（T14：真实渲染 + 筛选 chips） -->
    <div v-if="view !== 'task' || !taskCompleted" class="item-list" data-testid="item-list">
      <template v-if="view === 'claim'">
        <p class="item-empty">领取任务后在此查看待标注条目</p>
      </template>
      <template v-else-if="!taskCompleted">
        <div class="list-toolbar">
          <div class="chip-row" role="tablist">
            <button
              v-for="chip in visibleChips"
              :key="chip.key"
              type="button"
              class="chip"
              :class="{ active: activeFilter === chip.key }"
              @click="activeFilter = chip.key"
            >
              {{ chip.label }}
              <span class="chip-count">{{ chipCount(chip.key) }}</span>
            </button>
          </div>
          <button
            v-if="stagedCount >= 1"
            type="button"
            class="btn-submit-batch"
            data-testid="submit-batch"
            :disabled="submitting"
            @click="handleSubmitBatch"
          >
            {{ submitting ? "提交中..." : "整批提交复核" }}
          </button>
        </div>
        <p v-if="submitError" class="list-error">{{ submitError }}</p>

        <div v-if="itemsLoading" class="item-empty">条目加载中...</div>
        <div v-else-if="itemsHint" class="item-empty">{{ itemsHint }}</div>
        <div v-else-if="filteredItems.length === 0" class="item-empty">暂无符合条件的条目</div>
        <div v-else class="item-rows">
          <button
            v-for="item in filteredItems"
            :key="item.id"
            type="button"
            class="item-row"
            :class="{ active: editingItem?.id === item.id }"
            @click="openEditor(item)"
          >
            <span class="item-id">#{{ item.recordId ?? item.id }}</span>
            <span class="item-title">{{ itemTitle(item) }}</span>
            <span class="status-badge" :class="statusMeta(item.status).cls">
              {{ statusMeta(item.status).label }}
            </span>
          </button>
        </div>
      </template>
    </div>

    <!-- 编辑抽屉：左侧字段编辑 / 右侧 PDF 对照 -->
    <div v-if="editorOpen" class="editor-overlay" @click.self="requestCloseEditor">
      <aside class="editor-panel" data-testid="editor-panel" role="dialog" aria-label="条目编辑">
        <header class="pane-header">
          <span class="pane-title">
            编辑 #{{ editingItem?.recordId ?? editingItem?.id }}
            <small v-if="editingItem?.tableName">（{{ editingItem.tableName }}）</small>
          </span>
          <button type="button" class="pane-close" aria-label="关闭" @click="requestCloseEditor">&times;</button>
        </header>
        <div class="editor-body">
          <div class="editor-fields">
            <p v-if="editorFields.length === 0" class="item-empty">
              暂无可编辑字段（等待后端提供 editable_fields 元数据）
            </p>
            <div v-for="field in editorFields" :key="field" class="edit-field">
              <label>{{ field }}</label>
              <textarea
                v-if="isJsonField(field)"
                v-model="editForm[field]"
                rows="2"
                class="field-textarea"
              ></textarea>
              <span v-if="isJsonField(field)" class="field-hint">多个值用英文逗号分隔</span>
              <textarea
                v-else-if="isLongField(field)"
                v-model="editForm[field]"
                rows="5"
                class="field-textarea"
              ></textarea>
              <input v-else v-model="editForm[field]" type="text" class="field-input" />
            </div>
          </div>
          <div v-if="editingItem?.fileUuid" class="editor-pdf">
            <iframe v-if="pdfUrl" :src="pdfUrl" class="pdf-frame" title="PDF 对照" frameborder="0"></iframe>
            <div v-else-if="pdfLoading" class="pdf-placeholder">加载 PDF...</div>
            <div v-else class="pdf-placeholder">{{ pdfError || "无法加载 PDF" }}</div>
          </div>
        </div>
        <footer class="editor-footer">
          <p v-if="draftError" class="draft-error">{{ draftError }}</p>
          <button
            type="button"
            class="btn-secondary"
            data-testid="mark-no-change"
            :disabled="savingDraft"
            @click="saveDraft([])"
          >
            标记无需修改
          </button>
          <button
            type="button"
            class="btn-primary"
            data-testid="complete-item"
            :disabled="savingDraft"
            @click="saveDraft(collectFields())"
          >
            {{ savingDraft ? "暂存中..." : "完成本条" }}
          </button>
        </footer>
      </aside>
    </div>

    <!-- 返工抽屉 -->
    <div v-if="reworkDrawerOpen" class="rework-overlay" @click.self="closeReworkDrawer">
      <aside class="rework-panel" data-testid="rework-drawer" role="dialog" aria-label="待返工列表">
        <header class="pane-header">
          <span class="pane-title">待返工条目（{{ reworkItems.length }}）</span>
          <button type="button" class="pane-close" aria-label="关闭" @click="closeReworkDrawer">&times;</button>
        </header>
        <div class="rework-body">
          <div v-if="reworkLoading" class="item-empty">加载中...</div>
          <div v-else-if="reworkItems.length === 0" class="item-empty">
            暂无待返工条目（返工接口尚未就绪时同样显示此提示）
          </div>
          <button
            v-for="entry in reworkItems"
            :key="entry.itemId"
            type="button"
            class="rework-entry"
            @click="openReworkInEditor(entry)"
          >
            <span class="rework-title">
              {{ entry.title || `#${entry.recordId ?? entry.itemId}` }}
              <span v-if="reworkExpired(entry)" class="expired-tag">已超期释放</span>
            </span>
            <span v-if="entry.comment" class="rework-comment">驳回意见：{{ entry.comment }}</span>
            <span class="rework-deadline" :class="{ expired: reworkExpired(entry) }">
              剩余 {{ reworkCountdownText(entry) }}
            </span>
          </button>
        </div>
      </aside>
    </div>

    <!-- 轻提示 toast -->
    <transition name="toast-fade">
      <div v-if="toast" class="toast" :class="'toast-' + toast.type" data-testid="toast">
        {{ toast.text }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { claimTask, getMyTask, getMyTaskDetail, getMyRework, draftItem, submitTask } from "../api/annotation";
import { fetchFileUrl } from "../api/admin";

// 视图状态：loading | disabled | claim | task
const view = ref("loading");
const task = ref(null);
const claiming = ref(false);
const claimError = ref("");
const reworkCount = ref(0);

/* ---------- 条目状态 ---------- */

const items = ref([]);
const itemsLoading = ref(false);
const itemsHint = ref(""); // 后端条目端点未就绪等降级提示
// GET /my/task/detail 顶层的 editable_fields 元数据（数组）；null=后端未提供
const detailEditableFields = ref(null);
const activeFilter = ref("all");
const submitting = ref(false);
const submitError = ref("");
const taskCompleted = ref(false);
const submitResult = ref(null); // submitTask 响应：{ task_id, completed, count, stale_base_item_ids }

const nowMs = ref(Date.now());
let countdownTimer = null;
let reworkTimer = null;
let toastTimer = null;
const REWORK_POLL_MS = 30_000;

function applyTask(data) {
  // 契约对齐后端 claim / my-task 响应：{ task_id, count, deadline_at, table_name }
  task.value = {
    task_id: data.task_id,
    count: Number(data.count ?? 0),
    deadline_at: data.deadline_at,
    table_name: data.table_name,
  };
  resetItemList();
}

function resetItemList() {
  items.value = [];
  itemsHint.value = "";
  activeFilter.value = "all";
  taskCompleted.value = false;
  submitResult.value = null;
  submitError.value = "";
  closeEditorAfterSave();
}

/** 宽松归一化条目：后端明细端点契约未定，兼容多种字段命名。 */
function normalizeItem(raw) {
  const record =
    raw.record ?? raw.record_data ?? raw.core_record ?? raw.core ?? null;
  const submission = raw.submission ?? raw.latest_submission ?? null;
  return {
    id: raw.item_id ?? raw.id,
    recordId: raw.record_id ?? record?.id,
    tableName: raw.table_name ?? "",
    status: raw.status ?? "pending",
    record,
    proposedFields:
      submission?.proposed_fields ?? raw.proposed_fields ?? null,
    fileUuid: raw.file_uuid ?? record?.file_uuid ?? null,
    editableFields: raw.editable_fields ?? raw.editableFields ?? null,
  };
}

async function loadItems() {
  itemsLoading.value = true;
  itemsHint.value = "";
  try {
    const res = await getMyTaskDetail();
    const data = res.data;
    // editable_fields 在明细响应顶层（非逐条目）：编辑器只渲染可编辑字段，
    // 否则回退到记录键会把 original_name/crawl_status 等系统字段一并提交 → 后端 400。
    detailEditableFields.value = Array.isArray(data?.editable_fields)
      ? data.editable_fields
      : null;
    const list = Array.isArray(data)
      ? data
      : Array.isArray(data?.items)
        ? data.items
        : [];
    items.value = list.map(normalizeItem);
  } catch {
    // 条目端点尚未落地（404）/网络失败：按空列表降级，不伪造数据、不中断页面
    detailEditableFields.value = null;
    items.value = [];
    itemsHint.value = "条目接口尚未就绪";
  } finally {
    itemsLoading.value = false;
  }
}

/* ---------- 筛选 chips ---------- */

const FILTER_CHIPS = [
  { key: "all", label: "全部" },
  { key: "pending", label: "待处理" },
  { key: "drafted", label: "已暂存" },
  { key: "no_change", label: "无需修改" },
  { key: "rejected", label: "被驳回" },
  { key: "approved", label: "已通过" },
];

function isNoChangeItem(it) {
  // 「无需修改」= drafted 且提案为空 dict；形状不允许判定时该类不可识别
  return (
    it.status === "drafted" &&
    it.proposedFields != null &&
    typeof it.proposedFields === "object" &&
    Object.keys(it.proposedFields).length === 0
  );
}

const visibleChips = computed(() =>
  FILTER_CHIPS.filter(
    (chip) =>
      chip.key !== "no_change" ||
      // 仅当条目形状携带提案信息、可区分「无需修改」时才展示该 chip
      items.value.some((it) => it.proposedFields != null),
  ),
);

function chipCount(key) {
  if (key === "all") return items.value.length;
  if (key === "no_change") return items.value.filter(isNoChangeItem).length;
  return items.value.filter((it) => it.status === key).length;
}

const filteredItems = computed(() =>
  items.value.filter((it) => {
    if (activeFilter.value === "all") return true;
    if (activeFilter.value === "no_change") return isNoChangeItem(it);
    return it.status === activeFilter.value;
  }),
);

const STATUS_META = {
  pending: { label: "待处理", cls: "st-pending" },
  drafted: { label: "已暂存", cls: "st-drafted" },
  rejected: { label: "被驳回", cls: "st-rejected" },
  submitted: { label: "待复核", cls: "st-submitted" },
  approved: { label: "已通过", cls: "st-approved" },
};

function statusMeta(status) {
  return STATUS_META[status] ?? { label: status || "未知", cls: "st-other" };
}

function itemTitle(item) {
  const rec = item.record;
  if (rec && typeof rec === "object") {
    const candidate =
      rec.title ||
      rec.cleaned_title ||
      rec.tcm_diagnosis ||
      rec.western_diagnosis ||
      rec.original_name;
    if (candidate) return candidate;
  }
  return `记录 ${item.recordId ?? item.id}`;
}

const stagedCount = computed(
  () => items.value.filter((it) => it.status === "drafted").length,
);

const completedCount = computed(() => stagedCount.value);

const staleIds = computed(() => {
  const ids = submitResult.value?.stale_base_item_ids;
  return Array.isArray(ids) ? ids : [];
});

/* ---------- 截止时间倒计时（每秒跳动；挂载期常驻 ticker） ---------- */

const remainingMs = computed(() => {
  if (!task.value?.deadline_at) return null;
  return new Date(task.value.deadline_at).getTime() - nowMs.value;
});

const expired = computed(() => remainingMs.value != null && remainingMs.value <= 0);

const countdownText = computed(() => {
  if (remainingMs.value == null) return "—";
  if (expired.value) return "已超时";
  const total = Math.floor(remainingMs.value / 1000);
  const hh = String(Math.floor(total / 3600)).padStart(2, "0");
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
});

function startCountdown() {
  stopCountdown();
  nowMs.value = Date.now();
  countdownTimer = setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

/* ---------- 返工徽标轮询（30s）+ 返工抽屉数据 ---------- */

const reworkDrawerOpen = ref(false);
const reworkLoading = ref(false);
const reworkItems = ref([]);

function normalizeRework(raw) {
  return {
    itemId: raw.item_id ?? raw.id,
    recordId: raw.record_id,
    tableName: raw.table_name ?? "",
    title: raw.record_title ?? raw.title ?? raw.record?.title ?? null,
    comment: raw.review_comment ?? raw.comment ?? raw.reason ?? "",
    deadlineAt:
      raw.rework_deadline ?? raw.deadline_at ?? raw.deadline ?? null,
  };
}

async function pollRework() {
  try {
    const res = await getMyRework();
    // T7 契约未定，兼容 { count | items } 与数组两种返回形状
    const data = res.data;
    if (Array.isArray(data)) {
      reworkItems.value = data.map(normalizeRework);
      reworkCount.value = data.length;
    } else {
      reworkCount.value = Number(data?.count ?? 0) || 0;
      if (Array.isArray(data?.items)) {
        reworkItems.value = data.items.map(normalizeRework);
      }
    }
  } catch {
    // T7 落地前端点缺失（404）/网络失败：徽标隐藏，不打扰用户
    reworkCount.value = 0;
    reworkItems.value = [];
  }
}

function startReworkPolling() {
  stopReworkPolling();
  pollRework();
  reworkTimer = setInterval(pollRework, REWORK_POLL_MS);
}

function stopReworkPolling() {
  if (reworkTimer) {
    clearInterval(reworkTimer);
    reworkTimer = null;
  }
}

async function openReworkDrawer() {
  reworkDrawerOpen.value = true;
  reworkLoading.value = true;
  await pollRework(); // 打开时刷新一次最新清单
  reworkLoading.value = false;
}

function closeReworkDrawer() {
  reworkDrawerOpen.value = false;
}

function reworkRemainingMs(entry) {
  if (!entry.deadlineAt) return null;
  return new Date(entry.deadlineAt).getTime() - nowMs.value;
}

function reworkExpired(entry) {
  const ms = reworkRemainingMs(entry);
  return ms != null && ms <= 0;
}

function reworkCountdownText(entry) {
  const ms = reworkRemainingMs(entry);
  if (ms == null) return "—";
  if (ms <= 0) return "已超期释放";
  const total = Math.floor(ms / 1000);
  const dd = Math.floor(total / 86400);
  const hh = String(Math.floor((total % 86400) / 3600)).padStart(2, "0");
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  return dd > 0 ? `${dd}天 ${hh}:${mm}` : `${hh}:${mm}`;
}

function openReworkInEditor(entry) {
  // 返工重做走同一条 draftItem 流程：仅当条目属于当前进行中任务时可打开
  const target = items.value.find((it) => it.id === entry.itemId);
  if (!target) {
    showToast("该返工条目不在当前任务中，请先完成当前批次或重新领取", "warn");
    return;
  }
  reworkDrawerOpen.value = false;
  openEditor(target);
}

/* ---------- 编辑抽屉 ---------- */

const editorOpen = ref(false);
const editingItem = ref(null);
const editForm = ref({});
const editFormOriginal = ref({});
const editorFields = ref([]);
const savingDraft = ref(false);
const draftError = ref("");
const pdfUrl = ref("");
const pdfLoading = ref(false);
const pdfError = ref("");

// 系统字段不作为通用回退的可编辑键
const SYSTEM_KEYS = new Set([
  "id",
  "created_at",
  "updated_at",
  "file_uuid",
  "storage_path",
]);

function isJsonField(key) {
  return ["authors", "keywords"].includes(key);
}

function isLongField(field) {
  return field.length > 20 || ["abstract", "ai_summary", "commentary"].includes(field);
}

function resolveEditorFields(item) {
  // 1) editable_fields 元数据优先：逐条目覆盖（未来契约）→ 明细响应顶层元数据。
  //    顶层是当前后端 GET /my/task/detail 的真实位置；缺失时才走记录键回退。
  const meta = item.editableFields ?? detailEditableFields.value;
  if (Array.isArray(meta) && meta.length) {
    return [...meta];
  }
  // 2) 回退：已有提案键 + 内嵌记录的可见字段，通用输入渲染
  const keys = [];
  const push = (k) => {
    if (k && !keys.includes(k) && !SYSTEM_KEYS.has(k)) keys.push(k);
  };
  if (item.proposedFields && typeof item.proposedFields === "object") {
    Object.keys(item.proposedFields).forEach(push);
  }
  if (item.record && typeof item.record === "object") {
    Object.keys(item.record).forEach(push);
  }
  return keys;
}

function toFormValue(key, val) {
  if (isJsonField(key)) {
    if (Array.isArray(val)) return val.join(", ");
    if (val == null) return "";
    if (typeof val === "object") return JSON.stringify(val);
    return String(val);
  }
  return val == null ? "" : String(val);
}

function buildEditForm(item) {
  editorFields.value = resolveEditorFields(item);
  editForm.value = {};
  editFormOriginal.value = {};
  for (const key of editorFields.value) {
    const hasProposal =
      item.proposedFields && typeof item.proposedFields === "object"
        ? key in item.proposedFields
        : false;
    const str = toFormValue(
      key,
      hasProposal ? item.proposedFields[key] : item.record?.[key],
    );
    editForm.value[key] = str;
    editFormOriginal.value[key] = str;
  }
}

function hasUnsavedChanges() {
  if (!editingItem.value) return false;
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

function clearPdf() {
  pdfUrl.value = "";
  pdfLoading.value = false;
  pdfError.value = "";
}

function openEditor(item) {
  editingItem.value = item;
  editorOpen.value = true;
  draftError.value = "";
  buildEditForm(item);
  if (item.fileUuid) {
    loadPdf(item.fileUuid);
  } else {
    clearPdf();
  }
}

function requestCloseEditor() {
  if (hasUnsavedChanges()) {
    if (!confirm("有未保存的修改，确定关闭吗？")) return;
  }
  closeEditorAfterSave();
}

function closeEditorAfterSave() {
  editorOpen.value = false;
  editingItem.value = null;
  editForm.value = {};
  editFormOriginal.value = {};
  editorFields.value = [];
  draftError.value = "";
  clearPdf();
}

/** 表单字符串 -> 提案负载（authors/keywords 逗号拆分，同 AdminDataEdit 口径）。 */
function collectFields() {
  const fields = {};
  for (const [key, value] of Object.entries(editForm.value)) {
    if (isJsonField(key)) {
      const strVal = (value || "").replaceAll("，", ",").trim();
      fields[key] =
        strVal === ""
          ? []
          : strVal
              .split(",")
              .map((s) => s.trim())
              .filter((s) => s.length > 0);
    } else {
      fields[key] = value === "" ? null : value;
    }
  }
  return fields;
}

/**
 * 暂存单条：fields 为数组形式（[] 即「标记无需修改」→ proposed_fields={}）。
 * 成功后本地行标记「已暂存」；响应若携带 C8 失效提示则弹警告 toast。
 */
async function saveDraft(fieldsList) {
  if (!editingItem.value || savingDraft.value) return;
  const itemId = editingItem.value.id;
  // 与 AdminDataEdit 同口径：null 原样透传（清空字段），[] 无变更 → {}
  const proposed = {};
  for (const [key, value] of Object.entries(fieldsList)) {
    proposed[key] = value;
  }
  savingDraft.value = true;
  draftError.value = "";
  try {
    const res = await draftItem(itemId, proposed);
    markItemDrafted(itemId, proposed);
    // C8 失效预警：后端在响应中附带 stale 提示时告警（T6 形状之外的字段，宽松探测）
    if (res.data?.stale || res.data?.base_stale || res.data?.is_stale) {
      showToast("注意：该记录基准已被更新，整批提交时将提示失效风险", "warn");
    } else {
      showToast(res.data?.action === "no_change" ? "已标记无需修改" : "已暂存本条", "ok");
    }
    closeEditorAfterSave();
  } catch (e) {
    draftError.value = e.response?.data?.detail || "暂存失败，请稍后重试";
  } finally {
    savingDraft.value = false;
  }
}

function markItemDrafted(itemId, proposedFields) {
  const it = items.value.find((i) => i.id === itemId);
  if (!it) return;
  it.status = "drafted";
  it.proposedFields = proposedFields;
}

/* ---------- 整批提交复核 ---------- */

async function handleSubmitBatch() {
  if (!task.value || submitting.value) return;
  const total = task.value.count;
  if (
    !confirm(
      stagedCount.value < total
        ? `尚有 ${total - stagedCount.value} 条未暂存，后端将拒绝提交。仍要现在尝试整批提交复核吗？`
        : `确定将本批 ${total} 条全部提交复核吗？提交后不可再修改。`,
    )
  ) {
    return;
  }
  submitting.value = true;
  submitError.value = "";
  try {
    const res = await submitTask(task.value.task_id);
    submitResult.value = res.data ?? {};
    taskCompleted.value = true;
    closeEditorAfterSave();
    reworkDrawerOpen.value = false;
    showToast("整批提交成功，已进入复核流程", "ok");
  } catch (e) {
    submitError.value = e.response?.data?.detail || "提交失败，请稍后重试";
  } finally {
    submitting.value = false;
  }
}

async function claimNextBatch() {
  resetItemList();
  await loadCurrentTask();
}

/* ---------- 轻提示 toast ---------- */

const toast = ref(null);

function showToast(text, type = "info") {
  toast.value = { text, type };
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = null;
    toastTimer = null;
  }, 4000);
}

/* ---------- 当前任务加载与领取 ---------- */

async function loadCurrentTask() {
  view.value = "loading";
  try {
    const res = await getMyTask();
    // T7 契约：{ task: {...} | null }；落地前不会走到这里
    const current = res.data?.task ?? null;
    if (current) {
      applyTask(current);
      view.value = "task";
      loadItems();
    } else {
      view.value = "claim";
    }
  } catch (e) {
    if (e.response?.status === 503) {
      // A5：ANNOTATION_ENABLED 总闸关闭 → 友好空态
      view.value = "disabled";
    } else {
      // T7 落地前 /my/task 不存在（404），403/网络失败同理：
      // 一律降级为“无进行中任务”，回退领取面板。T7 接入真实数据后可细化分支。
      view.value = "claim";
    }
  }
}

async function handleClaim() {
  claiming.value = true;
  claimError.value = "";
  try {
    const res = await claimTask();
    applyTask(res.data);
    view.value = "task";
    loadItems();
  } catch (e) {
    if (e.response?.status === 503) {
      claimError.value = "功能未开启";
    } else {
      claimError.value = e.response?.data?.detail || "领取失败，请稍后重试";
    }
  } finally {
    claiming.value = false;
  }
}

function handleKeydown(e) {
  if (e.key !== "Escape") return;
  if (editorOpen.value) {
    requestCloseEditor();
  } else if (reworkDrawerOpen.value) {
    reworkDrawerOpen.value = false;
  }
}

onMounted(() => {
  startCountdown(); // 常驻 ticker：任务倒计时与返工截止倒计时共用
  startReworkPolling();
  window.addEventListener("keydown", handleKeydown);
  loadCurrentTask();
});

onBeforeUnmount(() => {
  stopCountdown();
  stopReworkPolling();
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.annotation-workbench { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; box-sizing: border-box; }

.wb-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.wb-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }

.rework-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; background: #ffebee; color: #c62828; font-size: 12px; font-weight: 500; border: none; cursor: pointer; font-family: inherit; }
.rework-badge:hover { background: #ffcdd2; }

.wb-loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

.wb-empty { text-align: center; padding: 64px 0; }
.empty-title { font-size: 16px; font-weight: 600; color: #666; margin: 0 0 8px; }
.empty-hint { font-size: 13px; color: #999; margin: 0; }

.claim-panel { display: flex; justify-content: center; padding: 32px 0; }
.panel-card { width: 420px; background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 28px 32px; text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.panel-card h2 { font-size: 16px; font-weight: 600; color: #1a1a2e; margin: 0 0 10px; }
.panel-hint { font-size: 13px; color: #888; line-height: 1.6; margin: 0 0 18px; }
.panel-error { font-size: 12px; color: #c62828; margin: 0 0 12px; }

.btn-primary { padding: 9px 32px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; font-family: inherit; }
.btn-primary:hover { background: #00695c; }
.btn-primary:disabled { opacity: 0.6; cursor: default; }
.btn-secondary { padding: 9px 24px; border: 1px solid #00796b; border-radius: 6px; background: #fff; color: #00796b; font-size: 13px; cursor: pointer; font-family: inherit; }
.btn-secondary:hover { background: #e0f2f1; }
.btn-secondary:disabled { opacity: 0.6; cursor: default; }

.task-card { display: flex; gap: 32px; background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.task-meta { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.meta-label { font-size: 12px; color: #999; }
.meta-value { font-size: 15px; font-weight: 600; color: #333; word-break: break-all; }
.countdown { font-variant-numeric: tabular-nums; color: #00796b; }
.countdown.expired { color: #c62828; }

.task-done { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.done-title { font-size: 15px; font-weight: 600; color: #2e7d32; }
.done-hint { font-size: 13px; color: #666; }
.stale-warning { margin: 0; padding: 8px 12px; background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 6px; font-size: 12px; color: #e65100; line-height: 1.6; }

.item-list { background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 16px 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); min-height: 120px; }
.list-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid #f0f0f0; margin-bottom: 8px; flex-wrap: wrap; }
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { padding: 4px 12px; border: 1px solid #d0d0d0; border-radius: 14px; background: #fff; color: #666; font-size: 12px; cursor: pointer; transition: all 0.15s; font-family: inherit; }
.chip:hover { border-color: #00796b; color: #00796b; }
.chip.active { background: #00796b; border-color: #00796b; color: #fff; }
.chip-count { opacity: 0.7; margin-left: 2px; font-variant-numeric: tabular-nums; }
.btn-submit-batch { padding: 7px 18px; border: none; border-radius: 6px; background: #e65100; color: #fff; font-size: 13px; cursor: pointer; white-space: nowrap; font-family: inherit; }
.btn-submit-batch:hover { background: #d84a00; }
.btn-submit-batch:disabled { opacity: 0.6; cursor: default; }
.list-error { margin: 8px 0; font-size: 12px; color: #c62828; }

.item-rows { display: flex; flex-direction: column; }
.item-row { display: flex; align-items: center; gap: 12px; width: 100%; padding: 11px 8px; border: none; border-bottom: 1px solid #f5f5f5; background: transparent; text-align: left; cursor: pointer; font-family: inherit; transition: background 0.15s; }
.item-row:last-child { border-bottom: none; }
.item-row:hover { background: #f7faf9; }
.item-row.active { background: #e0f2f1; }
.item-id { color: #999; font-size: 12px; flex-shrink: 0; min-width: 48px; }
.item-title { flex: 1; font-size: 13px; color: #1a1a2e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge { flex-shrink: 0; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.st-pending { background: #f0f0f0; color: #666; }
.st-drafted { background: #e0f2f1; color: #00796b; }
.st-rejected { background: #ffebee; color: #c62828; }
.st-submitted { background: #e3f2fd; color: #1565c0; }
.st-approved { background: #e8f5e9; color: #2e7d32; }
.st-other { background: #f0f0f0; color: #999; }

.item-empty { text-align: center; padding: 36px 0; font-size: 13px; color: #999; margin: 0; }

/* 编辑抽屉 */
.editor-overlay, .rework-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45); z-index: 1000; }
.editor-panel { position: absolute; top: 0; right: 0; height: 100%; width: min(960px, 92vw); background: #fff; box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15); display: flex; flex-direction: column; }
.pane-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid #e8e8e8; font-size: 14px; font-weight: 600; color: #1a1a2e; background: #fafafa; flex-shrink: 0; }
.pane-title small { font-weight: 400; color: #999; font-size: 12px; }
.pane-close { width: 30px; height: 30px; border: none; background: transparent; font-size: 22px; color: #888; cursor: pointer; border-radius: 6px; line-height: 1; }
.pane-close:hover { background: #eee; color: #333; }
.editor-body { flex: 1; display: flex; overflow: hidden; }
.editor-fields { flex: 1; overflow-y: auto; padding: 16px 20px; box-sizing: border-box; }
.editor-pdf { width: 46%; border-left: 1px solid #e8e8e8; background: #525659; position: relative; }
.pdf-frame { width: 100%; height: 100%; border: none; }
.pdf-placeholder { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #ccc; font-size: 13px; padding: 0 16px; text-align: center; }
.edit-field { margin-bottom: 14px; }
.edit-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; word-break: break-all; }
.field-input, .field-textarea { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; font-family: inherit; box-sizing: border-box; }
.field-input:focus, .field-textarea:focus { border-color: #00796b; }
.field-textarea { resize: vertical; min-height: 56px; }
.field-hint { display: block; font-size: 11px; color: #999; margin-top: 2px; }
.editor-footer { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 12px 20px; border-top: 1px solid #e8e8e8; flex-shrink: 0; }
.draft-error { margin: 0 auto 0 0; font-size: 12px; color: #c62828; }

/* 返工抽屉 */
.rework-panel { position: absolute; top: 0; right: 0; height: 100%; width: min(420px, 90vw); background: #fff; box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15); display: flex; flex-direction: column; }
.rework-body { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; }
.rework-entry { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border: 1px solid #e8e8e8; border-radius: 8px; background: #fff; text-align: left; cursor: pointer; font-family: inherit; transition: border-color 0.15s; }
.rework-entry:hover { border-color: #00796b; }
.rework-title { font-size: 13px; font-weight: 600; color: #1a1a2e; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rework-comment { font-size: 12px; color: #c62828; line-height: 1.5; word-break: break-all; }
.rework-deadline { font-size: 12px; color: #00796b; font-variant-numeric: tabular-nums; }
.rework-deadline.expired { color: #999; }
.expired-tag { padding: 1px 8px; border-radius: 8px; background: #f0f0f0; color: #999; font-size: 11px; font-weight: 400; }

/* toast */
.toast { position: fixed; left: 50%; bottom: 40px; transform: translateX(-50%); z-index: 2000; padding: 10px 20px; border-radius: 8px; font-size: 13px; color: #fff; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2); max-width: 80vw; }
.toast-ok { background: #2e7d32; }
.toast-warn { background: #e65100; }
.toast-info { background: #455a64; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s, transform 0.25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }
</style>
