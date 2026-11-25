<template>
  <div class="admin-page">
    <header class="admin-header">
      <div class="header-text">
        <h1>标注管理</h1>
        <p class="header-sub">建池 → 派发 → 标注 → 复核 → 回滚 · 全流程留痕</p>
      </div>
      <div class="header-right">
        <div class="header-meta">
          <span class="meta-item">任务池 <strong>{{ POOLS.length }}</strong></span>
          <span class="meta-divider"></span>
          <span class="meta-item">待复核 <strong>{{ REVIEW_TASKS.length }}</strong></span>
          <span class="meta-divider"></span>
          <span class="meta-item">今日操作 <strong>{{ LOGS.length }}</strong></span>
        </div>
        <button class="btn-primary" type="button" @click="wizardOpen = true">建池向导</button>
      </div>
    </header>

    <!-- 子页签 -->
    <div class="sub-tabs" role="tablist" aria-label="标注任务视图">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="sub-tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span class="sub-count">{{ tabCount(tab.key) }}</span>
      </button>
    </div>

    <!-- ───────── 任务池 ───────── -->
    <div v-show="activeTab === 'pools'" class="tab-body">
      <!-- 建池向导弹窗 -->
      <div v-if="wizardOpen" class="modal-mask" @click.self="wizardOpen = false">
        <div class="modal-box wizard-modal">

        <div class="panel-head">
          <div class="panel-heading">
            <h2 class="panel-title">建池向导</h2>
            <p class="panel-sub">选择表类型、输入检索词，预览命中后确认建池</p>
          </div>
          <div class="wizard-head-right">
            <span class="panel-hint">简版 · 按检索式圈定待标注范围</span>
            <button class="modal-close" type="button" @click="wizardOpen = false">×</button>
          </div>
        </div>

        <div class="wizard-grid">
          <label class="wizard-field">
            <span class="wizard-label">表类型</span>
            <select
              v-model="poolForm.tableType"
              class="filter-select"
              @change="invalidatePreview"
            >
              <option v-for="type in TABLE_TYPES" :key="type.key" :value="type.key">
                {{ type.label }}
              </option>
            </select>
          </label>

          <label class="wizard-field query-field">
            <span class="wizard-label">搜索词</span>
            <input
              v-model="poolForm.query"
              class="filter-input"
              type="text"
              placeholder="如：补肾填精 AND 卵巢储备功能减退"
              @input="invalidatePreview"
            />
          </label>

          <label class="wizard-field expected-field">
            <span class="wizard-label">预计条数</span>
            <input
              v-model.number="poolForm.expected"
              class="filter-input"
              type="number"
              min="1"
              max="500"
            />
          </label>

          <div class="wizard-actions">
            <button class="btn-sm teal" type="button" @click="previewPool">预览</button>
            <button class="btn-primary" type="button" @click="confirmPool">确认建池</button>
          </div>
        </div>

        <div v-if="previewResult" class="preview-box">
          <div class="preview-head">
            <span class="preview-badge">预览结果</span>
            <strong class="preview-count">{{ previewResult.count }} 条</strong>
            <span class="preview-target">
              {{ tableTypeLabel(previewResult.tableType) }} · 预计 {{ previewResult.expected }} 条
            </span>
            <span class="preview-query">「{{ previewResult.query }}」</span>
          </div>
          <ul class="preview-list">
            <li v-for="sample in previewSamples" :key="sample.id">
              <span class="preview-id">{{ sample.id }}</span>
              <span class="preview-title" :title="sample.title">{{ sample.title }}</span>
            </li>
          </ul>
          <p class="preview-foot">仅展示前 3 条命中示例 · 建池后仍可调整派发范围</p>
        </div>
        <div v-else class="preview-empty">
          输入检索词后点击「预览」，查看 mock 命中条数与样例记录
        </div>
        </div>
      </div>


      <section class="panel">
        <div class="panel-head">
          <div class="panel-heading">
            <h2 class="panel-title">池列表</h2>
            <p class="panel-sub">按状态跟踪余量与截止时间</p>
          </div>
          <span class="panel-hint">共 {{ POOLS.length }} 个池</span>
        </div>

        <div class="table-wrap">
          <table class="pool-table">
            <thead>
              <tr>
                <th class="col-pool-id">任务池 ID</th>
                <th class="col-table-type">表类型</th>
                <th class="col-pool-status">状态</th>
                <th class="col-remain">余量</th>
                <th class="col-deadline">截止</th>
                <th class="col-pool-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pool in POOLS" :key="pool.id">
                <td class="mono pool-id">{{ pool.id }}</td>
                <td>{{ tableTypeLabel(pool.tableType) }}</td>
                <td>
                  <span class="badge" :class="poolStatusMeta(pool.status).cls">
                    {{ poolStatusMeta(pool.status).label }}
                  </span>
                </td>
                <td>
                  <div class="remain-cell">
                    <span class="remain-num">{{ pool.remaining }}<small> / {{ pool.total }}</small></span>
                    <span class="remain-track" :title="`已消耗 ${poolPct(pool)}%`">
                      <span class="remain-fill" :style="{ width: poolPct(pool) + '%' }"></span>
                    </span>
                  </div>
                </td>
                <td class="mono cell-deadline">{{ pool.deadline }}</td>
                <td class="col-pool-actions">
                  <button
                    class="btn-sm teal"
                    type="button"
                    :disabled="pool.status === 'done' || pool.status === 'closed'"
                    @click="assignPool(pool)"
                  >
                    指派
                  </button>
                  <button
                    class="btn-sm"
                    type="button"
                    :disabled="pool.status === 'done' || pool.status === 'closed' || pool.status === 'pending'"
                    @click="togglePause(pool)"
                  >
                    {{ pool.status === "paused" ? "恢复" : "暂停" }}
                  </button>
                  <button
                    class="btn-sm danger"
                    type="button"
                    :disabled="pool.status === 'done' || pool.status === 'closed'"
                    @click="closePool(pool)"
                  >
                    关闭
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- ───────── 复核队列 ───────── -->
    <div v-show="activeTab === 'review'" class="tab-body">
      <div class="task-cards">
        <article
          v-for="task in REVIEW_TASKS"
          :key="task.id"
          class="task-card"
          :class="{ active: selectedTaskId === task.id }"
        >
          <div class="task-card-top">
            <span class="mono task-id">{{ task.id }}</span>
            <span class="badge" :class="task.tableType === 'case' ? 'badge-warn' : 'badge-teal'">
              {{ tableTypeLabel(task.tableType) }}
            </span>
          </div>
          <div class="task-card-meta">
            <span class="task-person">
              <span class="mini-avatar">{{ task.annotator.slice(0, 1) }}</span>
              {{ task.annotator }}
            </span>
            <span class="task-total">{{ task.total }} 条</span>
          </div>
          <p class="task-time">提交于 {{ task.submittedAt }}</p>
          <div class="task-card-foot">
            <span class="task-pending">待处理 {{ taskPendingCount(task) }} / {{ task.entries.length }}</span>
            <button
              class="btn-sm"
              :class="{ teal: selectedTaskId === task.id }"
              type="button"
              @click="enterReview(task)"
            >
              {{ selectedTaskId === task.id ? "继续复核" : "进入复核" }}
            </button>
          </div>
        </article>
      </div>

      <section v-if="selectedTask" class="panel review-detail">
        <div class="detail-head">
          <div class="detail-heading">
            <div class="detail-title">
              <span class="mono">{{ selectedTask.id }}</span>
              <span class="badge" :class="selectedTask.tableType === 'case' ? 'badge-warn' : 'badge-teal'">
                {{ tableTypeLabel(selectedTask.tableType) }}
              </span>
            </div>
            <p class="detail-sub">
              标注员 {{ selectedTask.annotator }} · 共 {{ selectedTask.total }} 条 ·
              当前展示 {{ selectedTask.entries.length }} 条样例
            </p>
          </div>
          <button class="btn-sm" type="button" @click="leaveReview">收起复核</button>
        </div>

        <div class="table-wrap">
          <table class="pool-table review-table">
            <thead>
              <tr>
                <th class="col-record">记录 ID</th>
                <th class="col-annotator">标注员</th>
                <th class="col-summary">摘要</th>
                <th class="col-review-status">状态</th>
                <th class="col-pass">通过</th>
                <th class="col-reject">驳回</th>
                <th class="col-diff">差异</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="entry in selectedTask.entries" :key="entry.id">
                <tr :class="{ 'row-open': expandedEntryId === entry.id }">
                  <td class="mono record-id">{{ entry.id }}</td>
                  <td class="cell-annotator">{{ entry.annotator }}</td>
                  <td class="cell-summary" :title="entry.summary">{{ entry.summary }}</td>
                  <td>
                    <span class="badge" :class="reviewStatusMeta(entry.status).cls">
                      {{ reviewStatusMeta(entry.status).label }}
                    </span>
                  </td>
                  <td>
                    <button
                      class="btn-sm pass"
                      type="button"
                      :disabled="entry.status !== 'pending'"
                      @click="approveEntry(entry)"
                    >
                      通过
                    </button>
                  </td>
                  <td>
                    <button
                      class="btn-sm reject"
                      type="button"
                      :disabled="entry.status !== 'pending'"
                      @click="rejectEntry(entry)"
                    >
                      驳回
                    </button>
                  </td>
                  <td>
                    <button class="btn-link" type="button" @click="toggleDiff(entry.id)">
                      {{ expandedEntryId === entry.id ? "收起 diff" : `展开 diff (${changedCount(entry)})` }}
                    </button>
                  </td>
                </tr>
                <tr v-if="expandedEntryId === entry.id" class="diff-row">
                  <td colspan="7">
                    <div class="diff-panel">
                      <div class="diff-head">
                        <span class="diff-head-title">字段变更对比</span>
                        <span class="diff-legend"><i></i> 变更字段</span>
                      </div>
                      <div class="diff-cols">
                        <span></span>
                        <span>当前值</span>
                        <span></span>
                        <span>提交值</span>
                      </div>
                      <div
                        v-for="item in entry.diffs"
                        :key="item.label"
                        class="diff-item"
                        :class="{ changed: item.changed }"
                      >
                        <span class="diff-label">{{ item.label }}</span>
                        <span class="diff-value current" :title="item.current">{{ item.current || "—" }}</span>
                        <span class="diff-arrow">→</span>
                        <span class="diff-value submitted" :title="item.submitted">{{ item.submitted || "—" }}</span>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <p class="detail-note">
          amber 高亮为本次提交发生变更的字段；复核通过后变更合入母版，驳回则退回标注员修改。
        </p>
      </section>

      <div v-else class="review-empty">
        <p>选择一个任务进入复核</p>
        <span>卡片展示任务号、标注员、条数与提交时间，点开查看条目差异。</span>
      </div>
    </div>

    <!-- ───────── 操作记录 ───────── -->
    <div v-show="activeTab === 'logs'" class="tab-body">
      <section class="panel">
        <div class="panel-head">
          <div class="panel-heading">
            <h2 class="panel-title">操作记录</h2>
            <p class="panel-sub">建池、修改、复核全链路审计</p>
          </div>
          <span class="panel-hint">共 {{ filteredLogs.length }} 条记录</span>
        </div>

        <div class="log-filters">
          <label class="filter-group">
            <span>分类</span>
            <select v-model="logCategory" class="filter-select">
              <option value="">全部</option>
              <option v-for="cat in LOG_CATEGORIES" :key="cat.key" :value="cat.key">
                {{ cat.label }}
              </option>
            </select>
          </label>
          <label class="filter-group">
            <span>动作</span>
            <select v-model="logAction" class="filter-select">
              <option value="">全部</option>
              <option v-for="action in LOG_ACTIONS" :key="action.key" :value="action.key">
                {{ action.label }}
              </option>
            </select>
          </label>
          <button
            v-if="logCategory || logAction"
            class="btn-sm"
            type="button"
            @click="resetLogFilters"
          >
            清除筛选
          </button>
        </div>

        <div class="table-wrap">
          <table class="pool-table log-table">
            <thead>
              <tr>
                <th class="col-log-time">时间</th>
                <th class="col-log-user">操作人</th>
                <th class="col-log-table">表</th>
                <th class="col-log-record">记录</th>
                <th class="col-log-category">分类</th>
                <th class="col-log-action">动作</th>
                <th class="col-log-summary">摘要</th>
                <th class="col-log-rollback">回滚</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in filteredLogs" :key="log.id" :class="{ 'log-rolled': log.rolledBack }">
                <td class="mono cell-log-time">{{ log.time }}</td>
                <td>{{ log.operator }}</td>
                <td class="cell-log-table">{{ log.table }}</td>
                <td class="mono cell-log-record">{{ log.record }}</td>
                <td>
                  <span class="badge cat-badge" :class="'cat-' + log.category">
                    {{ logCategoryMeta(log.category).label }}
                  </span>
                </td>
                <td>
                  <span class="badge action-badge" :class="'action-' + log.action">
                    {{ logActionMeta(log.action).label }}
                  </span>
                </td>
                <td class="cell-log-summary" :title="log.summary">{{ log.summary }}</td>
                <td>
                  <button
                    v-if="canRollback(log)"
                    class="btn-sm danger"
                    type="button"
                    @click="rollbackLog(log)"
                  >
                    回滚
                  </button>
                  <span v-else-if="log.rolledBack" class="rolled-tag">已回滚</span>
                  <span v-else class="no-action">—</span>
                </td>
              </tr>
              <tr v-if="filteredLogs.length === 0">
                <td colspan="8" class="empty-row">当前筛选条件下暂无操作记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { LIT_RECORDS, CASE_RECORDS } from "../../data/dorMock";
import { annotationStore } from "../../stores/annotation";

/* ───────── 页签 ───────── */
const TABS = [
  { key: "pools", label: "任务池" },
  { key: "review", label: "复核队列" },
  { key: "logs", label: "操作记录" },
];
const activeTab = ref("pools");



function tabCount(key) {
  if (key === "pools") return POOLS.value.length;
  if (key === "review") return REVIEW_TASKS.length;
  return LOGS.value.length;
}

/* ───────── toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;

function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 3200);
}

/* ───────── 任务池 ───────── */
const TABLE_TYPES = [
  { key: "literature", label: "文献表" },
  { key: "case", label: "病案表" },
];

const POOL_STATUS = {
  active: { label: "进行中", cls: "badge-teal" },
  pending: { label: "待指派", cls: "badge-warn" },
  paused: { label: "已暂停", cls: "badge-muted" },
  done: { label: "已完成", cls: "badge-ok" },
  closed: { label: "已关闭", cls: "badge-muted" },
};

const POOLS = ref([
  {
    id: "POOL-2025-018",
    tableType: "literature",
    status: "active",
    remaining: 32,
    total: 46,
    deadline: "2025-03-25",
  },
  {
    id: "POOL-2025-017",
    tableType: "case",
    status: "pending",
    remaining: 25,
    total: 25,
    deadline: "2025-03-24",
  },
  {
    id: "POOL-2025-016",
    tableType: "literature",
    status: "paused",
    remaining: 11,
    total: 30,
    deadline: "2025-03-21",
  },
  {
    id: "POOL-2025-015",
    tableType: "case",
    status: "done",
    remaining: 0,
    total: 40,
    deadline: "2025-03-18",
  },
]);

const poolForm = reactive({
  tableType: "literature",
  query: "",
  expected: 40,
});
const previewResult = ref(null);
const wizardOpen = ref(false);
const poolSeq = ref(19);

const previewSamples = computed(() => {
  const preview = previewResult.value;
  if (!preview) return [];
  const list = preview.tableType === "literature" ? LIT_RECORDS : CASE_RECORDS;
  return list.slice(0, 3).map((record) => ({
    id: record.id,
    title:
      preview.tableType === "literature"
        ? record.values.lit_1
        : `${record.values.case_1} 岁 · ${record.values.case_23 || "未分型"}`,
  }));
});

function tableTypeLabel(key) {
  return TABLE_TYPES.find((type) => type.key === key)?.label || key;
}

function poolStatusMeta(status) {
  return POOL_STATUS[status] || { label: status || "—", cls: "badge-muted" };
}

function poolPct(pool) {
  if (!pool.total) return 0;
  return Math.round(((pool.total - pool.remaining) / pool.total) * 100);
}

function invalidatePreview() {
  previewResult.value = null;
}

function previewPool() {
  const query = poolForm.query.trim();
  const expected = Math.max(1, Number(poolForm.expected) || 1);
  // 搜索词仅用于缩小范围；留空表示全部记录，同样可以预览
  const seed = query
    ? [...query].reduce((sum, ch) => sum + ch.charCodeAt(0), 0)
    : 0;
  const count = query ? Math.max(1, expected + (seed % 13) - 6) : expected;
  previewResult.value = {
    tableType: poolForm.tableType,
    query: query || "全部记录",
    expected,
    count,
  };
  showToast(`预览命中 ${count} 条记录（mock）`);
}

function confirmPool() {
  if (!previewResult.value) {
    showToast("请先预览命中结果，再确认建池", "error");
    return;
  }
  const id = `POOL-2025-${String(poolSeq.value).padStart(3, "0")}`;
  poolSeq.value += 1;
  const count = previewResult.value.count;
  POOLS.value.unshift({
    id,
    tableType: previewResult.value.tableType,
    status: "pending",
    remaining: count,
    total: count,
    deadline: "2025-03-28",
  });
  showToast(`任务池 ${id} 已创建，共 ${count} 条，等待指派（mock）`);
  poolForm.query = "";
  previewResult.value = null;
  wizardOpen.value = false;
}

function assignPool(pool) {
  const kind = pool.tableType === "case" ? "case" : "lit";
  const docs = annotationStore
    .availableDocs()
    .filter((d) => d.kind === kind)
    .slice(0, Math.min(5, pool.remaining || 5));
  if (pool.status === "pending") pool.status = "active";
  if (docs.length) {
    const task = annotationStore.assign(docs.map((d) => d.id));
    pool.remaining = Math.max(0, pool.remaining - docs.length);
    showToast(`任务池 ${pool.id} 已指派 · 生成标注任务 ${task.id}（${docs.length} 条）`);
  } else {
    showToast(`任务池 ${pool.id} 已指派给标注员周静（mock）`);
  }
}

function togglePause(pool) {
  if (pool.status === "active") {
    pool.status = "paused";
    showToast(`任务池 ${pool.id} 已暂停（mock）`);
  } else if (pool.status === "paused") {
    pool.status = "active";
    showToast(`任务池 ${pool.id} 已恢复进行（mock）`);
  }
}

function closePool(pool) {
  pool.status = "closed";
  showToast(`任务池 ${pool.id} 已关闭，余量 ${pool.remaining} 条退回待分配（mock）`, "error");
}

/* ───────── 复核队列 ───────── */
function diff(label, current, submitted) {
  return {
    label,
    current,
    submitted,
    changed: String(current) !== String(submitted),
  };
}

const REVIEW_STATUS = {
  pending: { label: "待复核", cls: "badge-warn" },
  approved: { label: "已通过", cls: "badge-ok" },
  rejected: { label: "已驳回", cls: "badge-danger" },
};

const REVIEW_TASKS = ref([
  {
    id: "TK-2025-091",
    tableType: "case",
    annotator: "周静",
    total: 24,
    submittedAt: "2025-03-19 10:15",
    entries: [
      {
        id: "CASE-002",
        annotator: "周静",
        summary: "38 岁 · 肝肾阴虚证 · AMH 0.42",
        status: "pending",
        diffs: [
          diff("年龄", "38", "38"),
          diff("AMH", "0.42 ng/mL", "0.51 ng/mL"),
          diff("证型", "肝肾阴虚证", "肝肾阴虚证"),
          diff("中医治疗", "左归丸加减：熟地黄24g、山药12g…", "左归丸加减：熟地黄24g、山药12g、龟甲胶10g…"),
          diff("妊娠结局", "未妊娠（移植2枚胚胎未着床）", "未妊娠（移植2枚胚胎未着床，HCG<5）"),
        ],
      },
      {
        id: "CASE-004",
        annotator: "周静",
        summary: "40 岁 · 脾肾阳虚证 · AMH 0.35",
        status: "pending",
        diffs: [
          diff("年龄", "40", "40"),
          diff("AMH", "0.35 ng/mL", "0.46 ng/mL"),
          diff("证型", "脾肾阳虚证", "脾肾阳虚证"),
          diff("中医治疗", "右归丸合理中汤加减", "右归丸合理中汤加减（加鹿角胶10g）"),
          diff("妊娠结局", "临床妊娠（单胎胎心）", "临床妊娠（单胎胎心）"),
        ],
      },
      {
        id: "CASE-005",
        annotator: "周静",
        summary: "36 岁 · 肾虚血瘀证 · AMH 0.55",
        status: "pending",
        diffs: [
          diff("年龄", "36", "36"),
          diff("AMH", "0.55 ng/mL", "0.55 ng/mL"),
          diff("证型", "肾虚血瘀证", "气滞血瘀证"),
          diff("中医治疗", "归肾丸合桃红四物汤加减", "归肾丸合桃红四物汤加减（加三棱9g、莪术9g）"),
        ],
      },
      {
        id: "CASE-006",
        annotator: "周静",
        summary: "29 岁 · 痰湿证 · AMH 0.92",
        status: "pending",
        diffs: [
          diff("年龄", "29", "29"),
          diff("AMH", "0.92 ng/mL", "0.92 ng/mL"),
          diff("证型", "痰湿证", "痰湿证"),
          diff("中医治疗", "苍附导痰汤加减", "苍附导痰汤加减（加薏苡仁30g）"),
          diff("妊娠结局", "临床妊娠（促排后自然受孕）", "临床妊娠（停经45天见胎心）"),
        ],
      },
      {
        id: "CASE-001",
        annotator: "周静",
        summary: "34 岁 · 肾虚证 · AMH 0.68",
        status: "approved",
        diffs: [
          diff("年龄", "34", "34"),
          diff("AMH", "0.68 ng/mL", "0.68 ng/mL"),
          diff("证型", "肾虚证", "肾虚证"),
          diff("妊娠结局", "临床妊娠（移植后28天见孕囊及胎心）", "临床妊娠（移植后28天见宫内孕囊及胎心）"),
        ],
      },
    ],
  },
  {
    id: "TK-2025-090",
    tableType: "literature",
    annotator: "孙浩",
    total: 17,
    submittedAt: "2025-03-19 09:42",
    entries: [
      {
        id: "LIT-002",
        annotator: "孙浩",
        summary: "队列研究 · 肾虚肝郁证 · 电针",
        status: "pending",
        diffs: [
          diff("研究类型", "队列研究", "队列研究"),
          diff("证型", "肾虚肝郁证", "肾虚肝郁证"),
          diff("干预措施", "电针", "电针（疏密波，2/100Hz）"),
          diff("年份", "2021", "2021"),
        ],
      },
      {
        id: "LIT-004",
        annotator: "孙浩",
        summary: "横断面研究 · 复合证型",
        status: "pending",
        diffs: [
          diff("研究类型", "横断面研究", "横断面研究"),
          diff("证型", "复合证型", "肾虚肝郁痰湿复合证"),
          diff("诊断标准", "未明确说明", "2016 中国 DOR 专家共识"),
          diff("样本量", "—", "86"),
        ],
      },
      {
        id: "LIT-005",
        annotator: "孙浩",
        summary: "META 分析 · 肝肾阴虚证 · 左归丸",
        status: "pending",
        diffs: [
          diff("研究类型", "META分析/系统评价", "系统评价 / Meta 分析"),
          diff("证型", "肝肾阴虚证", "肝肾阴虚证"),
          diff("方剂", "左归丸加减", "左归丸加减"),
          diff("临床妊娠率", "30.2%", "30.2%"),
        ],
      },
      {
        id: "LIT-006",
        annotator: "孙浩",
        summary: "准实验研究 · 肾虚血瘀证 · 坤泰胶囊",
        status: "approved",
        diffs: [
          diff("研究类型", "准实验/前后对照", "准实验/前后对照"),
          diff("证型", "肾虚血瘀证", "肾虚血瘀证"),
          diff("AMH 治疗后", "0.79±0.21", "0.79±0.21"),
          diff("周期取消率", "—", "12.5%"),
        ],
      },
      {
        id: "LIT-001",
        annotator: "孙浩",
        summary: "RCT · 肾虚证 · 补肾填精方",
        status: "approved",
        diffs: [
          diff("研究类型", "随机对照试验(RCT)", "随机对照试验（RCT）"),
          diff("证型", "肾虚证", "肾虚证"),
          diff("临床妊娠率", "38.5%", "38.5%"),
          diff("活产率", "32.7%", "32.7%"),
        ],
      },
    ],
  },
  {
    id: "TK-2025-089",
    tableType: "literature",
    annotator: "吴琦",
    total: 9,
    submittedAt: "2025-03-18 17:30",
    entries: [
      {
        id: "LIT-003",
        annotator: "吴琦",
        summary: "病例对照研究 · 痰湿证 · 苍附导痰汤",
        status: "pending",
        diffs: [
          diff("研究类型", "病例对照研究", "病例对照研究"),
          diff("证型", "痰湿证", "痰湿证"),
          diff("BMI 变化", "BMI下降1.6±0.8", "BMI 下降 1.6±0.8，痰湿积分下降"),
          diff("干预措施", "中药+针灸", "中药 + 穴位埋线"),
        ],
      },
      {
        id: "LIT-005",
        annotator: "吴琦",
        summary: "系统评价 · 肝肾阴虚证",
        status: "rejected",
        diffs: [
          diff("研究类型", "META分析/系统评价", "系统评价"),
          diff("证型", "肝肾阴虚证", "肝肾阴虚证"),
          diff("年份", "2024", "2023"),
        ],
      },
      {
        id: "LIT-006",
        annotator: "吴琦",
        summary: "准实验 · 肾虚血瘀证 · 微刺激",
        status: "pending",
        diffs: [
          diff("证型", "肾虚血瘀证", "肾虚血瘀证"),
          diff("AMH 治疗前", "0.61±0.17", "0.61±0.17"),
          diff("周期取消率", "—", "12.5%"),
        ],
      },
      {
        id: "LIT-002",
        annotator: "吴琦",
        summary: "队列研究 · 肾虚肝郁证 · 电针",
        status: "rejected",
        diffs: [
          diff("作者", "陈晓峰, 刘敏", "陈晓峰、刘敏"),
          diff("证型", "肾虚肝郁证", "肾虚肝郁证"),
          diff("年份", "2021", "2021"),
        ],
      },
      {
        id: "LIT-004",
        annotator: "吴琦",
        summary: "横断面研究 · 复合证型",
        status: "pending",
        diffs: [
          diff("证型", "复合证型", "复合证型"),
          diff("样本量", "—", "86"),
          diff("研究类型", "横断面研究", "横断面研究"),
        ],
      },
    ],
  },
]);

const selectedTaskId = ref(null);
const expandedEntryId = ref(null);

const selectedTask = computed(
  () => REVIEW_TASKS.value.find((task) => task.id === selectedTaskId.value) || null,
);

function reviewStatusMeta(status) {
  return REVIEW_STATUS[status] || { label: status || "—", cls: "badge-muted" };
}

function taskPendingCount(task) {
  return task.entries.filter((entry) => entry.status === "pending").length;
}

function changedCount(entry) {
  return entry.diffs.filter((item) => item.changed).length;
}

function enterReview(task) {
  selectedTaskId.value = task.id;
  expandedEntryId.value = null;
}

function leaveReview() {
  selectedTaskId.value = null;
  expandedEntryId.value = null;
}

function toggleDiff(entryId) {
  expandedEntryId.value = expandedEntryId.value === entryId ? null : entryId;
}

function approveEntry(entry) {
  if (entry.status !== "pending") return;
  entry.status = "approved";
  showToast(`${entry.id} 复核通过，变更已合入母版（mock）`);
}

function rejectEntry(entry) {
  if (entry.status !== "pending") return;
  entry.status = "rejected";
  showToast(`${entry.id} 已驳回并退回标注员（mock）`, "error");
}

/* ───────── 操作记录 ───────── */
const LOG_CATEGORIES = [
  { key: "task", label: "任务记录" },
  { key: "edit", label: "修改记录" },
  { key: "review", label: "复核记录" },
];

const LOG_ACTIONS = [
  { key: "create_pool", label: "建池" },
  { key: "assign", label: "派发" },
  { key: "save_direct", label: "直接保存" },
  { key: "save_submit", label: "提交标注" },
  { key: "approve", label: "复核通过" },
  { key: "reject", label: "复核驳回" },
  { key: "pause", label: "暂停" },
];

const LOG_CATEGORY_META = {
  task: { label: "任务记录" },
  edit: { label: "修改记录" },
  review: { label: "复核记录" },
};

const LOG_ACTION_META = {
  create_pool: { label: "建池" },
  assign: { label: "派发" },
  save_direct: { label: "直接保存" },
  save_submit: { label: "提交标注" },
  approve: { label: "复核通过" },
  reject: { label: "复核驳回" },
  pause: { label: "暂停" },
};

const LOGS = ref([
  {
    id: "log-001",
    time: "2025-03-19 10:42",
    operator: "黄伟",
    table: "文献表",
    record: "POOL-2025-018",
    category: "task",
    action: "create_pool",
    summary: "创建文献任务池，检索式「补肾填精 AND DOR」，共 46 条",
    rolledBack: false,
  },
  {
    id: "log-002",
    time: "2025-03-19 10:15",
    operator: "黄伟",
    table: "病案表",
    record: "TK-2025-091",
    category: "task",
    action: "assign",
    summary: "派发 24 条病案给标注员周静，截止 2025-03-25",
    rolledBack: false,
  },
  {
    id: "log-003",
    time: "2025-03-19 09:58",
    operator: "林舒",
    table: "文献表",
    record: "LIT-003",
    category: "review",
    action: "approve",
    summary: "证型「痰湿证」变更确认，合入文献母版",
    rolledBack: false,
  },
  {
    id: "log-004",
    time: "2025-03-19 09:36",
    operator: "黄伟",
    table: "病案表",
    record: "CASE-002",
    category: "edit",
    action: "save_direct",
    summary: "AMH 0.42 → 0.51 ng/mL，覆盖原抽取值",
    rolledBack: false,
  },
  {
    id: "log-005",
    time: "2025-03-19 09:12",
    operator: "林舒",
    table: "文献表",
    record: "LIT-005",
    category: "review",
    action: "reject",
    summary: "研究类型枚举不合法，退回标注员重标",
    rolledBack: false,
  },
  {
    id: "log-006",
    time: "2025-03-19 08:55",
    operator: "黄伟",
    table: "文献表",
    record: "TK-2025-090",
    category: "task",
    action: "assign",
    summary: "派发 17 条文献给标注员孙浩",
    rolledBack: false,
  },
  {
    id: "log-007",
    time: "2025-03-19 08:40",
    operator: "周静",
    table: "病案表",
    record: "CASE-004",
    category: "edit",
    action: "save_submit",
    summary: "补充妊娠结局与随访信息，提交复核",
    rolledBack: false,
  },
  {
    id: "log-008",
    time: "2025-03-19 08:12",
    operator: "黄伟",
    table: "病案表",
    record: "POOL-2025-016",
    category: "task",
    action: "pause",
    summary: "暂停任务池，余量 11 条待重新分配",
    rolledBack: false,
  },
]);

const logCategory = ref("");
const logAction = ref("");

const filteredLogs = computed(() =>
  LOGS.value.filter((log) => {
    if (logCategory.value && log.category !== logCategory.value) return false;
    if (logAction.value && log.action !== logAction.value) return false;
    return true;
  }),
);

function logCategoryMeta(category) {
  return LOG_CATEGORY_META[category] || { label: category || "—" };
}

function logActionMeta(action) {
  return LOG_ACTION_META[action] || { label: action || "—" };
}

function resetLogFilters() {
  logCategory.value = "";
  logAction.value = "";
}

function canRollback(log) {
  return (log.action === "approve" || log.action === "save_direct") && !log.rolledBack;
}

function rollbackLog(log) {
  log.rolledBack = true;
  showToast(`已回滚 ${log.record} 的「${logActionMeta(log.action).label}」操作（mock）`, "error");
}

onBeforeUnmount(() => {
  clearTimeout(toastTimer);
});
</script>

<style scoped>
.admin-page {
  width: 100%;
  min-height: 100%;
  padding: 24px 32px 40px;
  box-sizing: border-box;
}

/* ── 页头 ── */
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.header-text h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}
.header-sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}
.header-meta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  font-size: 11px;
  color: var(--ink-400);
  white-space: nowrap;
}
.meta-item strong {
  margin-left: 3px;
  color: var(--teal);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.meta-divider {
  width: 1px;
  height: 12px;
  background: var(--line);
}

/* ── 子页签 ── */
.sub-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 16px;
}
.sub-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 16px 11px;
  border: none;
  background: transparent;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s ease;
}
.sub-tab:hover {
  color: var(--ink-700);
}
.sub-tab.active {
  color: var(--teal-dark);
  font-weight: 600;
}
.sub-tab.active::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--teal);
}
.sub-count {
  min-width: 19px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #f1f3f4;
  color: var(--ink-500);
  font-size: 10px;
  font-weight: 600;
  text-align: center;
}
.sub-tab.active .sub-count {
  background: var(--teal-soft);
  color: var(--teal);
}
.tab-body {
  min-height: 200px;
}

/* ── 面板通用 ── */
.panel {
  padding: 16px 18px 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--card);
  margin-bottom: 16px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}
.panel-heading {
  min-width: 0;
}
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
}
.panel-sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}
.panel-hint {
  font-size: 12px;
  color: var(--ink-400);
  white-space: nowrap;
}

/* ── 建池向导 ── */
.wizard-grid {
  display: grid;
  grid-template-columns: 140px minmax(220px, 1fr) 110px auto;
  align-items: end;
  gap: 12px;
}
.wizard-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.wizard-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-500);
}
.wizard-field .filter-select,
.wizard-field .filter-input {
  width: 100%;
  box-sizing: border-box;
  height: 34px;
}
.wizard-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wizard-actions .btn-primary {
  height: 34px;
  padding: 0 16px;
  white-space: nowrap;
}
.wizard-actions .btn-sm {
  height: 34px;
  padding: 0 16px;
}
.preview-box {
  margin-top: 14px;
  padding: 11px 13px;
  border: 1px solid var(--teal-border);
  border-radius: 8px;
  background: #f6fbfa;
}
.preview-head {
  display: flex;
  align-items: baseline;
  gap: 9px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.preview-badge {
  padding: 1px 7px;
  border-radius: 4px;
  background: var(--teal);
  color: #fff;
  font-size: 10px;
}
.preview-count {
  font-size: 17px;
  font-weight: 600;
  color: var(--teal);
  font-variant-numeric: tabular-nums;
}
.preview-target,
.preview-query {
  font-size: 11px;
  color: var(--ink-500);
}
.preview-query {
  color: var(--ink-400);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 360px;
}
.preview-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.preview-list li {
  display: flex;
  align-items: baseline;
  gap: 9px;
  min-width: 0;
}
.preview-id {
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  color: var(--teal-dark);
}
.preview-title {
  font-size: 11px;
  color: var(--ink-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.preview-foot {
  margin: 8px 0 0;
  font-size: 10px;
  color: var(--ink-400);
}
.preview-empty {
  margin-top: 14px;
  padding: 10px 13px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  font-size: 11px;
  color: var(--ink-400);
  text-align: center;
}

/* ── 表格通用 ── */
.table-wrap {
  overflow-x: auto;
}
.pool-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.pool-table th {
  text-align: left;
  padding: 9px 12px;
  background: #fafbfb;
  color: var(--ink-500);
  font-weight: 500;
  border-bottom: 1px solid #e0e0e0;
  white-space: nowrap;
}
.pool-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
  color: #333;
  vertical-align: middle;
}
.pool-table tbody tr:last-child td {
  border-bottom: none;
}
.pool-table tbody tr:hover {
  background: #fafafa;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
}
.col-pool-id {
  width: 136px;
}
.col-table-type {
  width: 86px;
}
.col-pool-status {
  width: 92px;
}
.col-remain {
  width: 150px;
}
.col-deadline {
  width: 104px;
}
.col-pool-actions {
  width: 190px;
  text-align: right;
  white-space: nowrap;
}
.pool-id {
  color: var(--ink-500);
}
.remain-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.remain-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--teal);
  font-variant-numeric: tabular-nums;
}
.remain-num small {
  font-weight: 400;
  color: var(--ink-400);
}
.remain-track {
  display: block;
  height: 4px;
  border-radius: 999px;
  background: #eef1f0;
  overflow: hidden;
  max-width: 110px;
}
.remain-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--teal);
  transition: width 0.3s ease;
}
.cell-deadline {
  color: var(--ink-500);
  white-space: nowrap;
}
.btn-sm {
  padding: 4px 11px;
  border: 1px solid #d5d9dc;
  border-radius: 5px;
  background: #fff;
  color: var(--ink-500);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}
.btn-sm:hover:not(:disabled) {
  border-color: var(--teal);
  color: var(--teal);
}
.btn-sm + .btn-sm {
  margin-left: 6px;
}
.btn-sm.teal {
  color: var(--teal);
  border-color: var(--teal-border);
}
.btn-sm.teal:hover:not(:disabled) {
  background: var(--teal-soft);
}
.btn-sm.danger {
  color: var(--danger);
  border-color: #f0c7c7;
}
.btn-sm.danger:hover:not(:disabled) {
  background: #fff5f5;
  border-color: var(--danger);
}
.btn-sm:disabled {
  color: #c3c9cd;
  border-color: #eceff1;
  background: #fafbfb;
  cursor: not-allowed;
}

/* ── 复核卡片 ── */
.task-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.task-card {
  display: flex;
  flex-direction: column;
  padding: 13px 14px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}
.task-card:hover {
  border-color: var(--teal-border);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
}
.task-card.active {
  border-color: var(--teal);
  box-shadow: 0 0 0 2px rgba(0, 121, 107, 0.08);
}
.task-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
}
.task-id {
  color: var(--ink-900);
  font-size: 12px;
  font-weight: 600;
}
.task-card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.task-person {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--ink-700);
}
.mini-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-size: 10px;
  font-weight: 700;
}
.task-total {
  font-size: 12px;
  font-weight: 600;
  color: var(--teal);
  font-variant-numeric: tabular-nums;
}
.task-time {
  margin: 5px 0 10px;
  font-size: 10px;
  color: var(--ink-400);
}
.task-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 9px;
  border-top: 1px dashed var(--line);
}
.task-pending {
  font-size: 10px;
  color: var(--ink-400);
}

/* ── 复核详情 ── */
.review-detail {
  margin-bottom: 0;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
}
.detail-sub {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}
.review-table {
  min-width: 860px;
}
.col-record {
  width: 96px;
}
.col-annotator {
  width: 74px;
}
.col-summary {
  min-width: 220px;
}
.col-review-status {
  width: 82px;
}
.col-pass,
.col-reject {
  width: 60px;
}
.col-diff {
  width: 108px;
}
.record-id {
  color: var(--ink-900);
  font-weight: 600;
}
.cell-annotator {
  color: var(--ink-500);
  font-size: 12px;
  white-space: nowrap;
}
.cell-summary {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-700);
  font-size: 12px;
}
.btn-sm.pass {
  color: var(--ok);
  border-color: #c8e6c9;
}
.btn-sm.pass:hover:not(:disabled) {
  background: #f1f9f1;
  border-color: var(--ok);
}
.btn-sm.reject {
  color: var(--danger);
  border-color: #f0c7c7;
}
.btn-sm.reject:hover:not(:disabled) {
  background: #fff5f5;
  border-color: var(--danger);
}
.btn-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--teal);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-link:hover {
  text-decoration: underline;
}
.row-open > td {
  background: #f7fbfa;
}
.diff-row > td {
  padding: 0 !important;
  background: #fbfdfc;
  border-bottom: 1px solid #e3ece9;
}
.diff-panel {
  padding: 12px 16px 14px;
  border-left: 3px solid var(--teal-border);
  margin: 0 0 0 12px;
}
.diff-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.diff-head-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-700);
}
.diff-legend {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: var(--ink-400);
}
.diff-legend i {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: #ffecb3;
  border: 1px solid #ffca28;
}
.diff-cols,
.diff-item {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr) 24px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}
.diff-cols {
  padding: 0 8px 5px;
  font-size: 10px;
  color: var(--ink-400);
}
.diff-item {
  padding: 7px 8px;
  border-radius: 6px;
  margin-bottom: 3px;
  background: #fbfcfc;
  border: 1px solid transparent;
}
.diff-item.changed {
  background: #fffaf0;
  border-color: #ffe0a3;
}
.diff-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-700);
}
.diff-value {
  display: block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--ink-500);
  background: #f4f6f6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.diff-item.changed .diff-value {
  background: #fff;
  border: 1px solid #ffd54f;
  color: #6d4c00;
}
.diff-arrow {
  text-align: center;
  color: var(--ink-400);
  font-size: 12px;
}
.diff-item.changed .diff-arrow {
  color: var(--warn);
  font-weight: 700;
}
.detail-note {
  margin: 12px 0 0;
  padding: 8px 11px;
  border-left: 3px solid #ffd54f;
  background: #fffdf7;
  border-radius: 0 6px 6px 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--ink-400);
}
.review-empty {
  padding: 46px 20px;
  border: 1px dashed #d8dfe2;
  border-radius: 10px;
  background: #fbfcfc;
  text-align: center;
}
.review-empty p {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-500);
}
.review-empty span {
  font-size: 11px;
  color: var(--ink-400);
}

/* ── 操作记录 ── */
.log-filters {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.filter-group {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--ink-500);
}
.filter-group .filter-select {
  height: 32px;
  padding: 0 9px;
  font-size: 12px;
}
.log-table {
  min-width: 1000px;
}
.col-log-time {
  width: 126px;
}
.col-log-user {
  width: 66px;
}
.col-log-table {
  width: 72px;
}
.col-log-record {
  width: 122px;
}
.col-log-category {
  width: 86px;
}
.col-log-action {
  width: 88px;
}
.col-log-summary {
  min-width: 220px;
}
.col-log-rollback {
  width: 68px;
  text-align: right;
  white-space: nowrap;
}
.cell-log-time {
  color: var(--ink-400);
  white-space: nowrap;
}
.cell-log-table {
  color: var(--ink-500);
  font-size: 12px;
}
.cell-log-record {
  color: var(--ink-900);
  white-space: nowrap;
}
.cell-log-summary {
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-500);
  font-size: 12px;
}
.cat-badge {
  font-size: 10px;
}
.cat-task {
  background: var(--teal-soft);
  color: var(--teal-dark);
}
.cat-edit {
  background: #fff8e1;
  color: #b26a00;
}
.cat-review {
  background: #e8f1fb;
  color: #1565c0;
}
.action-badge {
  font-size: 10px;
}
.action-create_pool,
.action-assign,
.action-pause {
  background: #f3f5f5;
  color: var(--ink-500);
}
.action-save_direct {
  background: #fff8e1;
  color: #b26a00;
}
.action-save_submit {
  background: #f3e8fb;
  color: #6a1b9a;
}
.action-approve {
  background: #e8f5e9;
  color: var(--ok);
}
.action-reject {
  background: #ffebee;
  color: var(--danger);
}
.rolled-tag {
  font-size: 10px;
  color: var(--ink-400);
}
.no-action {
  color: #d4d9dd;
  font-size: 12px;
}
.log-rolled .cell-log-summary {
  text-decoration: line-through;
  color: #b7bec3;
}
.log-rolled .cell-log-record {
  color: #b7bec3;
}

/* ── 空状态 ── */
.empty-row {
  text-align: center;
  color: var(--ink-400);
  padding: 36px 12px !important;
}

/* ── toast ── */
.toast {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 2000;
  padding: 12px 18px;
  border-radius: 8px;
  font-size: 13px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  max-width: 420px;
}
.toast-success {
  background: var(--teal);
  color: #fff;
}
.toast-error {
  background: var(--danger);
  color: #fff;
}
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── 响应式 ── */
@media (max-width: 1080px) {
  .wizard-grid {
    grid-template-columns: 140px minmax(0, 1fr) 110px;
  }
  .wizard-actions {
    grid-column: 1 / -1;
    justify-content: flex-end;
  }
  .task-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .admin-page {
    padding: 16px;
  }
  .admin-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .header-meta {
    width: 100%;
    justify-content: space-between;
  }
  .panel {
    padding: 14px;
  }
  .panel-head {
    flex-direction: column;
    gap: 5px;
  }
  .wizard-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .wizard-actions {
    grid-column: auto;
    justify-content: stretch;
  }
  .wizard-actions .btn-primary,
  .wizard-actions .btn-sm {
    flex: 1;
  }
  .task-cards {
    grid-template-columns: minmax(0, 1fr);
  }
  .diff-cols,
  .diff-item {
    grid-template-columns: 76px minmax(0, 1fr) 18px minmax(0, 1fr);
    gap: 5px;
  }
  .diff-panel {
    padding: 10px;
    margin-left: 0;
  }
}
.col-etl-check { width: 40px; text-align: center; }
.etl-check { width: 15px; height: 15px; accent-color: #00796b; cursor: pointer; }
.col-etl-conf { width: 90px; }
.etl-task-list { margin-top: 16px; padding-top: 12px; border-top: 1px dashed #e0e0e0; }
.etl-subtitle { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #444; }
.header-right { display: flex; align-items: center; gap: 14px; }
.wizard-head-right { display: flex; align-items: center; gap: 10px; }

.modal-mask {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.42);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.modal-box {
  width: 760px; max-width: 96vw; max-height: 88vh; overflow-y: auto;
  background: #fff; border-radius: 12px; padding: 18px 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.22);
}
.modal-close {
  width: 28px; height: 28px; border: none; background: transparent;
  font-size: 20px; color: #999; cursor: pointer; border-radius: 4px;
}
.modal-close:hover { background: #f0f0f0; color: #333; }
.wizard-modal .panel-head { margin-bottom: 14px; }
</style>
