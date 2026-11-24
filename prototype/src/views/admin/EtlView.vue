<template>
  <div class="admin-page" data-testid="etl-view">
    <!-- ── 页头 ── -->
    <div class="admin-header">
      <div>
        <h1>ETL 抽取</h1>
        <p class="header-sub">LLM 抽取 → 校验 → 归一 → 建图</p>
      </div>
    </div>

    <!-- ── 顶部菜单 ── -->
    <nav class="tab-bar">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        type="button"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- ═══════════ Tab 1：抽取任务 ═══════════ -->
    <div v-show="activeTab === 'extract'" class="tab-body">
      <!-- 抽取配置 -->
      <section class="card panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">抽取配置</h2>
            <span class="panel-hint">先选择对象与执行范围，再开始抽取</span>
          </div>
          <div class="segmented">
            <button
              v-for="obj in OBJECT_TYPES"
              :key="obj.key"
              type="button"
              class="seg-btn"
              :class="{ active: objectType === obj.key }"
              @click="switchObject(obj.key)"
            >
              {{ obj.label }}
            </button>
          </div>
        </div>

        <!-- 范围模式 -->
        <div class="field-row">
          <span class="field-label">执行范围</span>
          <div class="radio-group">
            <label v-for="mode in SCOPE_MODES" :key="mode.key" class="radio-item">
              <input v-model="scopeMode" type="radio" :value="mode.key" name="scope-mode" />
              <span>{{ mode.label }}</span>
            </label>
          </div>
        </div>

        <!-- 模式 1：未抽取的记录 -->
        <div v-if="scopeMode === 'pending'" class="scope-hint">
          当前{{ objectLabel }}中尚有
          <strong>{{ pendingCount }}</strong>
          条记录未完成抽取，本次将全部处理。
        </div>

        <!-- 模式 2：指定记录 -->
        <div v-else-if="scopeMode === 'specified'" class="specified-panel">
          <div class="table-toolbar">
            <input
              v-model="recordQuery"
              type="text"
              class="filter-input"
              placeholder="搜索编号或标题..."
            />
            <span class="table-count">
              已选 <strong>{{ selectedIds.length }}</strong> / 当前结果
              {{ filteredRecords.length }} 条
            </span>
          </div>
          <div class="table-wrap record-table-wrap">
            <table class="pool-table">
              <thead>
                <tr>
                  <th class="col-check">
                    <input
                      type="checkbox"
                      :checked="allPageSelected"
                      :indeterminate.prop="somePageSelected"
                      @change="togglePage"
                    />
                  </th>
                  <th>编号</th>
                  <th>标题</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="record in filteredRecords" :key="record.id">
                  <td class="col-check">
                    <input v-model="selectedIds" type="checkbox" :value="record.id" />
                  </td>
                  <td class="cell-mono">{{ record.id }}</td>
                  <td class="cell-title" :title="recordTitleFor(objectType, record)">
                    {{ recordTitleFor(objectType, record) }}
                  </td>
                  <td>
                    <span class="badge" :class="statusMeta(record.status).cls">
                      {{ statusMeta(record.status).label }}
                    </span>
                  </td>
                </tr>
                <tr v-if="filteredRecords.length === 0">
                  <td colspan="4" class="empty-row">没有匹配的记录</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="table-tip">「全选」仅作用于当前搜索结果，共 {{ filteredRecords.length }} 条。</p>
        </div>

        <!-- 模式 3：按筛选条件 -->
        <div v-else class="filter-panel">
          <div v-if="objectType === 'literature'" class="filter-item">
            <label>研究类型</label>
            <select v-model="filterStudyType" class="filter-select">
              <option value="">全部</option>
              <option v-for="opt in studyTypeOptions" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </div>
          <div v-if="objectType === 'literature'" class="filter-item">
            <label>年份区间</label>
            <div class="year-row">
              <input
                v-model.number="yearFrom"
                type="number"
                class="filter-input year-input"
                placeholder="起始"
              />
              <span class="year-sep">—</span>
              <input
                v-model.number="yearTo"
                type="number"
                class="filter-input year-input"
                placeholder="结束"
              />
            </div>
          </div>
          <div v-else class="filter-item">
            <label>不孕类型</label>
            <select v-model="filterCaseType" class="filter-select">
              <option value="">全部</option>
              <option v-for="opt in infertilityOptions" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </div>
          <div class="filter-item">
            <label>状态</label>
            <select v-model="filterStatus" class="filter-select">
              <option value="">全部</option>
              <option v-for="(meta, key) in DOR_STATUS_META" :key="key" :value="key">
                {{ meta.label }}
              </option>
            </select>
          </div>
        </div>

        <!-- 范围汇总 -->
        <div class="scope-summary" :class="{ 'scope-empty': scopeCount === 0 }">
          <span class="summary-dot"></span>
          <span>
            本次抽取范围：<strong>{{ scopeCount }}</strong> 条（{{ objectLabel }}共
            {{ totalCount }} 条，本次不会处理其余
            {{ Math.max(totalCount - scopeCount, 0) }} 条）
          </span>
        </div>

        <div class="action-row">
          <button
            class="btn-primary"
            type="button"
            :disabled="scopeCount === 0"
            @click="startExtraction"
          >
            开始抽取
          </button>
          <span v-if="scopeCount === 0" class="action-hint">请先选择执行范围</span>
        </div>
      </section>

      <!-- 任务列表 -->
      <section class="card panel">
        <div class="panel-head">
          <h2 class="panel-title">抽取任务</h2>
          <span class="panel-hint">最近 {{ tasks.length }} 条任务</span>
        </div>
        <div class="table-wrap">
          <table class="pool-table">
            <thead>
              <tr>
                <th>任务ID</th>
                <th>对象</th>
                <th>范围模式</th>
                <th>条数</th>
                <th>状态</th>
                <th class="col-progress">进度</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.id">
                <td class="cell-mono">{{ task.id }}</td>
                <td>{{ task.target }}</td>
                <td>{{ task.scopeMode }}</td>
                <td>{{ task.count }}</td>
                <td>
                  <span class="badge" :class="taskStatusClass(task.status)">{{ task.status }}</span>
                  <span v-if="task.failed" class="fail-note">{{ task.failed }} 条失败</span>
                </td>
                <td>
                  <div class="progress-cell">
                    <div class="progress-track">
                      <div
                        class="progress-fill"
                        :class="'fill-' + taskStatusTone(task.status)"
                        :style="{ width: task.progress + '%' }"
                      ></div>
                    </div>
                    <span class="progress-text">{{ task.progress }}%</span>
                  </div>
                </td>
                <td class="cell-time">{{ task.createdAt }}</td>
                <td>
                  <button class="btn-sm teal" type="button" @click="openDetail(task)">
                    查看详情
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- ═══════════ Tab 2：质检看板 ═══════════ -->
    <div v-show="activeTab === 'quality'" class="tab-body">
      <div class="quality-embed">
        <EtlQualityView />
      </div>
    </div>

    <!-- ── 任务详情抽屉 ── -->
    <transition name="fade">
      <div v-if="detailTask" class="drawer-mask" @click.self="closeDetail"></div>
    </transition>
    <transition name="slide">
      <aside v-if="detailTask" class="drawer">
        <header class="drawer-head">
          <div>
            <span class="drawer-id">{{ detailTask.id }}</span>
            <h2 class="drawer-title">{{ detailTask.target }}抽取任务</h2>
            <p class="drawer-sub">
              {{ detailTask.scopeMode }} · {{ detailTask.count }} 条 · {{ detailTask.createdAt }}
            </p>
          </div>
          <button class="drawer-close" type="button" title="关闭" @click="closeDetail">
            &times;
          </button>
        </header>

        <div class="drawer-body">
          <div class="detail-stats">
            <span class="detail-stat stat-ok">成功 {{ detailStats.ok }}</span>
            <span class="detail-stat stat-review">待复核 {{ detailStats.review }}</span>
            <span class="detail-stat stat-fail">失败 {{ detailStats.fail }}</span>
          </div>
          <div class="table-wrap">
            <table class="pool-table detail-table">
              <thead>
                <tr>
                  <th>记录</th>
                  <th>状态</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in detailRows" :key="row.id">
                  <td>
                    <span class="cell-mono">{{ row.id }}</span>
                    <p class="detail-title">{{ row.title }}</p>
                  </td>
                  <td>
                    <span class="badge" :class="rowStatusClass(row.status)">{{ row.status }}</span>
                  </td>
                  <td class="detail-reason">{{ row.reason || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <footer class="drawer-foot">
          <span class="foot-hint">失败 {{ detailStats.fail }} 条，可重新入队</span>
          <button
            class="btn-sm teal"
            type="button"
            :disabled="detailStats.fail === 0"
            @click="retryFailed"
          >
            失败项重试
          </button>
        </footer>
      </aside>
    </transition>

    <!-- ── Toast ── -->
    <transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import EtlQualityView from "./EtlQualityView.vue";
import { CASE_RECORDS, DOR_STATUS_META, LIT_RECORDS } from "../../data/dorMock";
import { CASE_GROUPS, LIT_GROUPS, flattenGroups } from "../../constants/dorFields";

const TABS = [
  { key: "extract", label: "抽取任务" },
  { key: "quality", label: "质检看板" },
];

const OBJECT_TYPES = [
  { key: "literature", label: "文献" },
  { key: "case", label: "病案" },
];

const SCOPE_MODES = [
  { key: "pending", label: "未抽取的记录" },
  { key: "specified", label: "指定记录" },
  { key: "filter", label: "按筛选条件" },
];

const LIT_FIELDS = flattenGroups(LIT_GROUPS);
const CASE_FIELDS = flattenGroups(CASE_GROUPS);

function fieldOptions(fields, key) {
  const field = fields.find((f) => f.key === key);
  return field && Array.isArray(field.options) ? field.options : [];
}

const studyTypeOptions = fieldOptions(LIT_FIELDS, "lit_4");
const infertilityOptions = fieldOptions(CASE_FIELDS, "case_4");

const activeTab = ref("extract");
const objectType = ref("literature");
const scopeMode = ref("pending");
const selectedIds = ref([]);
const recordQuery = ref("");

const filterStudyType = ref("");
const filterStatus = ref("");
const yearFrom = ref("");
const yearTo = ref("");
const filterCaseType = ref("");

const toast = ref("");
const detailTask = ref(null);
const detailRows = ref([]);

const pad2 = (n) => String(n).padStart(2, "0");

const tasks = ref([
  {
    id: "ETL-20250319-005",
    target: "文献",
    targetKey: "literature",
    scopeMode: "按筛选条件",
    count: 42,
    status: "抽取中",
    progress: 68,
    failed: 0,
    createdAt: "2025-03-19 11:05",
  },
  {
    id: "ETL-20250319-004",
    target: "病案",
    targetKey: "case",
    scopeMode: "指定记录",
    count: 18,
    status: "部分失败",
    progress: 100,
    failed: 4,
    createdAt: "2025-03-19 09:40",
  },
  {
    id: "ETL-20250318-003",
    target: "文献",
    targetKey: "literature",
    scopeMode: "未抽取的记录",
    count: 36,
    status: "已完成",
    progress: 100,
    failed: 0,
    createdAt: "2025-03-18 16:20",
  },
  {
    id: "ETL-20250318-002",
    target: "文献",
    targetKey: "literature",
    scopeMode: "按筛选条件",
    count: 24,
    status: "已完成",
    progress: 100,
    failed: 0,
    createdAt: "2025-03-18 10:12",
  },
  {
    id: "ETL-20250317-001",
    target: "病案",
    targetKey: "case",
    scopeMode: "未抽取的记录",
    count: 12,
    status: "排队中",
    progress: 0,
    failed: 0,
    createdAt: "2025-03-17 18:02",
  },
]);

const objectLabel = computed(() => (objectType.value === "literature" ? "文献" : "病案"));

const records = computed(() =>
  objectType.value === "literature" ? LIT_RECORDS : CASE_RECORDS
);

const totalCount = computed(() => records.value.length);

const pendingCount = computed(
  () => records.value.filter((record) => record.status !== "extracted").length
);

function statusMeta(status) {
  return DOR_STATUS_META[status] || { label: status, cls: "badge-muted" };
}

function recordTitleFor(type, record) {
  if (type === "literature") {
    return record.values.lit_1 || "未命名文献";
  }
  const parts = [
    record.values.case_1 ? `${record.values.case_1} 岁` : "",
    record.values.case_4 || "",
    record.values.case_3 ? `不孕 ${record.values.case_3} 年` : "",
  ].filter(Boolean);
  return parts.join(" · ") || "未命名病案";
}

const filteredRecords = computed(() => {
  const query = recordQuery.value.trim().toLowerCase();
  if (!query) return records.value;
  return records.value.filter((record) => {
    const title = recordTitleFor(objectType.value, record);
    return (
      record.id.toLowerCase().includes(query) || title.toLowerCase().includes(query)
    );
  });
});

const allPageSelected = computed(
  () =>
    filteredRecords.value.length > 0 &&
    filteredRecords.value.every((record) => selectedIds.value.includes(record.id))
);

const somePageSelected = computed(
  () =>
    filteredRecords.value.some((record) => selectedIds.value.includes(record.id)) &&
    !allPageSelected.value
);

function togglePage(event) {
  const pageIds = filteredRecords.value.map((record) => record.id);
  if (event.target.checked) {
    selectedIds.value = Array.from(new Set([...selectedIds.value, ...pageIds]));
  } else {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id));
  }
}

function inYearRange(rawYear) {
  const year = Number(rawYear);
  if (!Number.isFinite(year) || year === 0) return false;
  if (yearFrom.value !== "" && year < Number(yearFrom.value)) return false;
  if (yearTo.value !== "" && year > Number(yearTo.value)) return false;
  return true;
}

const filterMatched = computed(() =>
  records.value.filter((record) => {
    if (filterStatus.value && record.status !== filterStatus.value) return false;
    if (objectType.value === "literature") {
      if (filterStudyType.value && record.values.lit_4 !== filterStudyType.value) {
        return false;
      }
      if (
        (yearFrom.value !== "" || yearTo.value !== "") &&
        !inYearRange(record.values.lit_3)
      ) {
        return false;
      }
    } else if (filterCaseType.value && record.values.case_4 !== filterCaseType.value) {
      return false;
    }
    return true;
  })
);

const scopeCount = computed(() => {
  if (scopeMode.value === "pending") return pendingCount.value;
  if (scopeMode.value === "specified") return selectedIds.value.length;
  return filterMatched.value.length;
});

function switchObject(key) {
  if (objectType.value === key) return;
  objectType.value = key;
  selectedIds.value = [];
  recordQuery.value = "";
  filterStudyType.value = "";
  filterStatus.value = "";
  yearFrom.value = "";
  yearTo.value = "";
  filterCaseType.value = "";
}

const taskTimers = new Set();
const toastTimer = ref(null);

function schedule(fn, delay) {
  const timer = setTimeout(() => {
    taskTimers.delete(timer);
    fn();
  }, delay);
  taskTimers.add(timer);
}

function showToast(message) {
  toast.value = message;
  if (toastTimer.value) clearTimeout(toastTimer.value);
  toastTimer.value = setTimeout(() => {
    toast.value = "";
    toastTimer.value = null;
  }, 2800);
}

let taskSeq = 5;

function startExtraction() {
  if (scopeCount.value === 0) return;

  taskSeq += 1;
  const date = new Date();
  const day = `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}`;
  const count = scopeCount.value;
  const success = Math.round(count * 0.8);
  const failed = count - success;

  const task = {
    id: `ETL-${day}-${String(taskSeq).padStart(3, "0")}`,
    target: objectLabel.value,
    targetKey: objectType.value,
    scopeMode: SCOPE_MODES.find((mode) => mode.key === scopeMode.value)?.label || "—",
    count,
    status: "排队中",
    progress: 0,
    failed: 0,
    createdAt: `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(
      date.getDate()
    )} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`,
  };

  tasks.value.unshift(task);
  showToast(`任务 ${task.id} 已创建，共 ${count} 条`);

  schedule(() => {
    task.status = "抽取中";
    task.progress = 35;
    showToast(`任务 ${task.id} 开始抽取`);
  }, 600);

  schedule(() => {
    task.progress = 100;
    task.status = failed > 0 ? "部分失败" : "已完成";
    task.failed = failed;
    showToast(`抽取完成：成功 ${success} 条，失败 ${failed} 条`);
  }, 3000);
}

const TASK_STATUS_META = {
  排队中: { cls: "badge-muted", tone: "idle" },
  抽取中: { cls: "badge-teal", tone: "running" },
  已完成: { cls: "badge-ok", tone: "done" },
  部分失败: { cls: "badge-warn", tone: "warn" },
};

function taskStatusClass(status) {
  return TASK_STATUS_META[status]?.cls || "badge-muted";
}

function taskStatusTone(status) {
  return TASK_STATUS_META[status]?.tone || "idle";
}

const DETAIL_PATTERN = [
  { status: "成功", reason: "" },
  { status: "成功", reason: "" },
  { status: "待复核", reason: "置信度 0.78，低于 0.85 阈值，需人工确认" },
  { status: "失败", reason: "原文段落解析失败，未返回结构化结果" },
  { status: "成功", reason: "" },
  { status: "待复核", reason: "字段「研究类型」与下拉选项不匹配" },
];

function openDetail(task) {
  detailTask.value = task;
  const list = task.targetKey === "literature" ? LIT_RECORDS : CASE_RECORDS;
  detailRows.value = DETAIL_PATTERN.map((pattern, index) => {
    const record = list[index % list.length];
    return {
      id: record.id,
      title: recordTitleFor(task.targetKey, record),
      status: pattern.status,
      reason: pattern.reason,
    };
  });
}

function closeDetail() {
  detailTask.value = null;
  detailRows.value = [];
}

const detailStats = computed(() => {
  const stats = { ok: 0, review: 0, fail: 0 };
  detailRows.value.forEach((row) => {
    if (row.status === "成功") stats.ok += 1;
    else if (row.status === "待复核") stats.review += 1;
    else stats.fail += 1;
  });
  return stats;
});

function rowStatusClass(status) {
  if (status === "成功") return "badge-ok";
  if (status === "待复核") return "badge-warn";
  return "badge-danger";
}

function retryFailed() {
  const failedRows = detailRows.value.filter((row) => row.status === "失败");
  if (failedRows.length === 0) return;
  failedRows.forEach((row) => {
    row.status = "待复核";
    row.reason = "已重新入队，等待二次抽取";
  });
  showToast(`已提交 ${failedRows.length} 条失败项重试`);
}

onBeforeUnmount(() => {
  taskTimers.forEach((timer) => clearTimeout(timer));
  taskTimers.clear();
  if (toastTimer.value) clearTimeout(toastTimer.value);
});
</script>

<style scoped>
/* ── 顶部菜单 ── */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 18px;
}

.tab-btn {
  position: relative;
  padding: 10px 18px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--ink-500);
  cursor: pointer;
  border-radius: 6px 6px 0 0;
}

.tab-btn:hover {
  color: var(--teal);
  background: var(--teal-soft);
}

.tab-btn.active {
  color: var(--teal);
  font-weight: 600;
}

.tab-btn.active::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 2px;
  background: var(--teal);
  border-radius: 2px;
}

/* ── 面板 ── */
.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 18px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
}

.panel-hint {
  font-size: 12px;
  color: var(--ink-400);
}

/* ── 文献 / 病案 segmented ── */
.segmented {
  display: inline-flex;
  padding: 3px;
  background: #f0f4f3;
  border-radius: 8px;
  gap: 2px;
}

.seg-btn {
  padding: 6px 18px;
  border: none;
  border-radius: 6px;
  background: transparent;
  font-size: 13px;
  color: var(--ink-500);
  cursor: pointer;
}

.seg-btn.active {
  background: #fff;
  color: var(--teal-dark);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* ── 范围模式 ── */
.field-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.field-label {
  width: 64px;
  flex: none;
  font-size: 13px;
  color: var(--ink-500);
}

.radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.radio-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-700);
  cursor: pointer;
}

.radio-item input {
  accent-color: var(--teal);
  cursor: pointer;
}

/* ── 未抽取提示 ── */
.scope-hint {
  padding: 10px 14px;
  border: 1px solid var(--teal-border);
  background: var(--teal-soft);
  border-radius: 6px;
  font-size: 13px;
  color: var(--teal-dark);
  margin-bottom: 14px;
}

.scope-hint strong {
  color: var(--teal);
  font-size: 14px;
}

/* ── 指定记录表格 ── */
.specified-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 14px;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.table-count {
  font-size: 12px;
  color: var(--ink-500);
}

.table-count strong {
  color: var(--teal);
}

.record-table-wrap {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
}

.record-table-wrap .pool-table th {
  position: sticky;
  top: 0;
  z-index: 1;
}

.col-check {
  width: 40px;
  text-align: center !important;
}

.col-check input {
  accent-color: var(--teal);
  cursor: pointer;
}

.cell-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}

.cell-title {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-400);
}

/* ── 筛选条件 ── */
.filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 14px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-item label {
  font-size: 12px;
  color: var(--ink-500);
}

.year-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.year-input {
  width: 84px;
}

.year-sep {
  color: var(--ink-400);
  font-size: 12px;
}

/* ── 范围汇总 ── */
.scope-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-left: 3px solid var(--teal);
  background: #f2faf8;
  border-radius: 0 6px 6px 0;
  font-size: 13px;
  color: var(--ink-700);
}

.scope-summary strong {
  color: var(--teal);
  font-size: 15px;
}

.summary-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--teal);
  flex: none;
}

.scope-empty {
  border-left-color: var(--danger);
  background: #fff5f5;
  color: var(--danger);
}

.scope-empty strong,
.scope-empty .summary-dot {
  color: var(--danger);
  background: var(--danger);
}

/* ── 操作 ── */
.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.btn-primary:disabled {
  background: #cfd8d6;
  cursor: not-allowed;
}

.action-hint {
  font-size: 12px;
  color: var(--ink-400);
}

/* ── 任务列表 ── */
.col-progress {
  width: 140px;
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-track {
  width: 80px;
  height: 6px;
  background: #eceff1;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.fill-idle {
  background: #b0bec5;
}

.fill-running {
  background: linear-gradient(90deg, #26a69a, #00796b);
}

.fill-done {
  background: var(--ok);
}

.fill-warn {
  background: var(--warn);
}

.progress-text {
  font-size: 12px;
  color: var(--ink-500);
  width: 34px;
  text-align: right;
}

.fail-note {
  margin-left: 6px;
  font-size: 11px;
  color: var(--danger);
}

.cell-time {
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}

/* ── 质检看板嵌入 ── */
.quality-embed :deep(.admin-page) {
  padding: 0;
  min-height: auto;
}

/* ── 抽屉 ── */
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.3);
  z-index: 40;
}

.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 540px;
  max-width: 100vw;
  background: #fff;
  z-index: 41;
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.14);
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--line);
  background: #fafcfb;
}

.drawer-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--teal);
}

.drawer-title {
  margin: 4px 0;
  font-size: 16px;
  font-weight: 600;
}

.drawer-sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}

.drawer-close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--ink-400);
  cursor: pointer;
}

.drawer-close:hover {
  color: var(--ink-900);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
}

.detail-stats {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.detail-stat {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.stat-ok {
  background: #e8f5e9;
  color: var(--ok);
}

.stat-review {
  background: #fff8e1;
  color: var(--warn);
}

.stat-fail {
  background: #ffebee;
  color: var(--danger);
}

.detail-table td {
  vertical-align: top;
}

.detail-title {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ink-700);
  max-width: 220px;
}

.detail-reason {
  font-size: 12px;
  color: var(--ink-500);
  max-width: 190px;
}

.drawer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-top: 1px solid var(--line);
  background: #fafafa;
}

.foot-hint {
  font-size: 12px;
  color: var(--ink-500);
}

.btn-sm:disabled {
  color: #bbb;
  border-color: #e0e0e0;
  cursor: not-allowed;
}

/* ── Toast ── */
.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  padding: 10px 20px;
  background: rgba(27, 27, 47, 0.92);
  color: #fff;
  font-size: 13px;
  border-radius: 6px;
  z-index: 60;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
}

/* ── 过渡 ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.24s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}
</style>
