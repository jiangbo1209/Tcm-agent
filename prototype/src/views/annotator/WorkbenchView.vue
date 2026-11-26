<template>
  <div class="admin-page" :class="{ 'workbench-fill': activeTab === 'tasks' }">
    <!-- 页签 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'tasks' }"
        @click="switchTab('tasks')"
      >
        标注任务
        <span class="tab-count">{{ activeTasks.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'rework' }"
        @click="switchTab('rework')"
      >
        返工箱
        <span class="tab-count">{{ reworkTasks.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'records' }"
        @click="switchTab('records')"
      >
        我的标注记录
        <span class="tab-count">{{ records.length }}</span>
      </button>
    </div>

    <template v-if="activeTab === 'tasks'">
      <!-- 任务卡片 -->
      <div class="review-carousel">
        <button
          class="carousel-arrow left"
          type="button"
          :disabled="activeTasks.length === 0"
          title="上一个任务"
          @click="stepTask(-1)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div class="task-cards" @wheel.prevent="onTaskWheel">
          <article
            v-for="task in activeTasks"
            :key="task.id"
            class="task-card"
            :class="{ active: selectedTaskId === task.id }"
            :style="{ '--task-color': taskColor(task) }"
            @click="selectTask(task)"
          >
            <div class="task-card-top">
              <span class="mono task-id">{{ task.id }}</span>
              <span class="badge" :class="taskStatusCls(task.status)">
                {{ taskStatusLabel(task.status) }}
              </span>
            </div>
            <div class="task-card-meta">
              <span class="task-count">{{ task.docIds.length }} 条</span>
              <span class="pending-chip">已处理 {{ taskProcessed(task) }} / {{ task.docIds.length }}</span>
            </div>
            <p class="task-time">截止 {{ task.deadline }}</p>
          </article>
        </div>

        <button
          class="carousel-arrow right"
          type="button"
          :disabled="activeTasks.length === 0"
          title="下一个任务"
          @click="stepTask(1)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      <!-- 标注工作区：任务条目 | 原文面板 | 字段表单 -->
      <div
        v-if="selectedTask"
        ref="workLayoutRef"
        class="work-layout"
        :class="{ 'list-collapsed': workListCollapsed }"
      >
        <aside v-if="!workListCollapsed" class="task-list card" :style="{ borderColor: activeTaskColor }">
          <div class="list-head">
            <span>任务条目</span>
            <div class="list-head-right">
              <span class="list-count">{{ activeItems.length }} 条</span>
              <button class="list-toggle" type="button" title="收起条目列表" @click="setListCollapsed(true)">«</button>
            </div>
          </div>
          <div class="list-body">
            <button
              v-for="item in activeItems"
              :key="item.id"
              class="task-item"
              :class="{ active: item.id === currentId }"
              @click="selectItem(item.id)"
            >
              <div class="task-item-top">
                <span class="task-no">{{ item.id }}</span>
                <span class="badge" :class="STATUS_META[item.status]">{{ item.status }}</span>
              </div>
              <div class="task-title" :title="item.title">{{ item.title }}</div>
            </button>
          </div>
        </aside>

        <div v-else class="work-list-rail" :style="{ borderColor: activeTaskColor }">
          <button type="button" title="展开条目列表" @click="setListCollapsed(false)">»</button>
          <button type="button" title="上一条" @click="prevItem">‹</button>
          <button type="button" title="下一条" @click="nextItem">›</button>
        </div>

        <section class="original-panel card" :style="sourceWidth ? { width: sourceWidth + 'px' } : {}">
          <header class="original-head">
            <div class="original-title">
              <span class="original-tag">原文</span>
              <div class="font-switch" role="group" aria-label="正文字号">
                <button
                  v-for="option in FONT_OPTIONS"
                  :key="option.value"
                  class="font-btn"
                  :class="{ active: originalFont === option.value }"
                  @click="originalFont = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
          </header>

          <template v-if="currentOriginal">
            <div class="original-meta">
              <span class="original-source">{{ currentOriginal.source }}</span>
              <h3 class="original-name" :title="currentOriginal.title">
                {{ currentOriginal.title }}
              </h3>
            </div>
            <div class="original-body" :class="'font-' + originalFont">
              {{ currentOriginal.body }}
            </div>
          </template>

          <div v-else class="original-empty">
            <div class="empty-mark">▤</div>
            <p>暂无原文</p>
            <span>该条目在本地 mock 中未提供原文片段</span>
          </div>
        </section>

        <div
          class="source-editor-splitter"
          title="拖动调整原文宽度"
          @pointerdown.prevent="startSourceResize"
        ></div>

        <section class="editor card">
          <template v-if="currentItem">
            <header class="editor-head">
              <div class="editor-title">
                <span class="editor-no">{{ currentItem.id }}</span>
                <h2 :title="currentItem.title">{{ currentItem.title || "未命名条目" }}</h2>
              </div>
              <div class="editor-meta">
                <span class="badge" :class="[currentItem.status === '已提交' ? 'badge-ok' : currentItem.status === '已暂存' ? 'badge-warn' : 'badge-muted']">
                  {{ currentItem.status }}
                </span>
                <span class="group-hint">按母版前 2 组渲染</span>
              </div>
            </header>

            <div v-if="currentKind === 'case'" class="key-fields">
              <span class="key-fields-label">关键字段</span>
              <span
                v-for="keyField in CASE_KEY_FIELDS"
                :key="keyField.key"
                class="key-chip"
              >
                <span class="key-name">{{ keyField.label }}</span>
                <span class="key-value">{{ displayValue(keyField) }}</span>
              </span>
            </div>

            <div class="editor-body">
              <section
                v-for="group in visibleGroups"
                :key="group.label"
                class="field-group"
              >
                <h3 class="group-title">
                  {{ group.label }}
                  <span class="group-count">{{ group.fields.length }} 字段</span>
                </h3>
                <div class="field-grid">
                  <div
                    v-for="field in group.fields"
                    :key="field.key"
                    class="field-item"
                    :class="{ wide: isLongField(field) }"
                  >
                    <label class="field-label" :for="field.key">
                      {{ field.label }}<span v-if="field.required" class="req">*</span>
                    </label>
                    <select
                      v-if="field.options"
                      :id="field.key"
                      v-model="form[field.key]"
                      class="field-control"
                    >
                      <option value="">— 请选择 —</option>
                      <option v-for="opt in field.options" :key="opt" :value="opt">
                        {{ opt }}
                      </option>
                    </select>
                    <textarea
                      v-else-if="isLongField(field)"
                      :id="field.key"
                      v-model="form[field.key]"
                      class="field-control field-textarea"
                      rows="3"
                      :placeholder="field.desc"
                    ></textarea>
                    <input
                      v-else
                      :id="field.key"
                      v-model="form[field.key]"
                      type="text"
                      class="field-control"
                      :placeholder="field.desc"
                    />
                  </div>
                </div>
              </section>
            </div>

            <footer class="editor-footer">
              <div class="footer-actions">
                <button class="btn-sm" @click="markNoChange">标记无需修改</button>
                <button class="btn-sm teal" @click="stashCurrent">暂存本条</button>
                <button class="btn-primary" @click="openSubmit">提交整批</button>
              </div>
            </footer>
          </template>

          <div v-else class="editor-empty">
            <div class="empty-mark">▤</div>
            <p>未选择标注条目</p>
            <span>从左侧任务条目中选择一条开始标注</span>
          </div>
        </section>
      </div>

      <div v-else class="review-empty">
        <p>暂无待标注任务</p>
        <span>请先在「任务领取」领取任务，或等待管理员下发。</span>
      </div>
    </template>

    <!-- 返工箱 -->
    <div v-else-if="activeTab === 'rework'" class="review-panel card">
      <div class="records-head">
        <h2>返工箱</h2>
        <span>复核驳回的条目 · 返工期限 5 天，超时回收</span>
      </div>
      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th>任务</th>
              <th class="col-kind">类型</th>
              <th class="col-conf">条目数</th>
              <th>驳回时间</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in reworkTasks" :key="t.id">
              <td class="mono">{{ t.id }}</td>
              <td>
                <span class="badge" :class="t.kind === 'lit' ? 'badge-lit' : 'badge-case'">
                  {{ t.kind === "lit" ? "文献" : "病案" }}
                </span>
              </td>
              <td>{{ t.docIds.length }}</td>
              <td class="muted">{{ t.rejectedAt || "—" }}</td>
              <td><button class="btn-sm teal" @click="resubmitRework(t)">返工完成并重新提交</button></td>
            </tr>
            <tr v-if="reworkTasks.length === 0">
              <td colspan="5" class="empty-row">暂无返工任务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 我的标注记录 -->
    <div v-else class="records card">
      <div class="records-head">
        <h2>我的标注记录</h2>
        <span>近 30 天提交的文献 / 病案标注与复核意见</span>
      </div>
      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th class="col-no">编号</th>
              <th class="col-kind">对象类型</th>
              <th>标题</th>
              <th class="col-status">状态</th>
              <th class="col-time">提交时间</th>
              <th>复核意见</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.id">
              <td class="cell-no">{{ record.id }}</td>
              <td>
                <span class="badge" :class="record.kind === '病案' ? 'badge-case' : 'badge-lit'">
                  {{ record.kind }}
                </span>
              </td>
              <td class="cell-title" :title="record.title">{{ record.title }}</td>
              <td>
                <span class="badge" :class="RECORD_STATUS_META[record.status]">
                  {{ record.status }}
                </span>
              </td>
              <td class="cell-time">{{ record.submittedAt }}</td>
              <td class="cell-review" :class="{ muted: !record.review }">
                {{ record.review || "—" }}
              </td>
            </tr>
            <tr v-if="records.length === 0">
              <td colspan="6" class="empty-row">暂无提交记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 提交确认 -->
    <div v-if="confirmOpen" class="modal-mask" @click.self="confirmOpen = false">
      <div class="modal">
        <h3>确认提交本批标注？</h3>
        <p>
          将把 <strong>{{ stagedCount }}</strong> 条「已暂存」记录提交至复核队列，
          提交后本批次内不可再编辑。
        </p>
        <div class="modal-actions">
          <button class="btn-sm" @click="confirmOpen = false">取消</button>
          <button class="btn-primary" @click="confirmSubmit">确认提交</button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast-pop">
      <div v-if="toast.show" class="toast" :class="'toast-' + toast.tone">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";
import { CASE_GROUPS, LIT_GROUPS, flattenGroups } from "../../constants/dorFields";
import { resolveOriginal } from "../../data/originals";
import { etlStore } from "../../stores/etl";
import { annotationStore } from "../../stores/annotation";

const STATUS_META = {
  待标注: "badge-muted",
  已暂存: "badge-warn",
  已提交: "badge-ok",
};

const RECORD_STATUS_META = {
  已通过: "badge-ok",
  已提交: "badge-teal",
  需修改: "badge-danger",
};

const FONT_OPTIONS = [
  { value: "sm", label: "小" },
  { value: "md", label: "中" },
  { value: "lg", label: "大" },
];

const CASE_KEY_FIELDS = [
  { key: "case_1", label: "年龄", unit: "岁" },
  { key: "case_10", label: "AMH", unit: "ng/mL" },
  { key: "case_23", label: "证型", unit: "" },
];

const LONG_KEYS = [
  "lit_8",
  "lit_9",
  "lit_13",
  "lit_14",
  "case_5",
  "case_6",
  "case_7",
  "case_17",
  "case_20",
  "case_24",
  "case_26",
  "case_28",
  "case_32",
  "case_34",
];

const TITLES = {
  sys: "补肾填精法治疗卵巢储备功能减退的系统评价",
  rct: "左归丸联合西药治疗 DOR 的随机对照试验",
  needle: "针药结合治疗肾虚肝郁型 DOR 的临床观察",
  cohort: "温肾健脾法干预脾肾阳虚型 DOR 的队列研究",
  dea: "电针联合 DHEA 对卵巢储备功能减退的疗效分析",
  meta: "中西医结合治疗 DOR 的系统评价与 Meta 分析",
};

const records = [
  {
    id: "LIT-2026-098",
    kind: "文献",
    title: TITLES.sys,
    status: "已通过",
    submittedAt: "2026-11-20 16:42",
    review: "抽取完整，结局指标已核对，通过。",
  },
  {
    id: "CASE-2026-198",
    kind: "病案",
    title: "病案 · 37 岁 · 继发性不孕 3 年（肾虚肝郁证）",
    status: "已通过",
    submittedAt: "2026-11-19 14:05",
    review: "四诊信息与证型判定一致。",
  },
  {
    id: "LIT-2026-096",
    kind: "文献",
    title: TITLES.rct,
    status: "需修改",
    submittedAt: "2026-11-19 10:18",
    review: "AMH 单位疑似录入错误，请对照原文后重新提交。",
  },
  {
    id: "CASE-2026-196",
    kind: "病案",
    title: "病案 · 32 岁 · 原发性不孕 2 年（痰湿证）",
    status: "已提交",
    submittedAt: "2026-11-18 17:31",
    review: "",
  },
  {
    id: "LIT-2026-095",
    kind: "文献",
    title: TITLES.needle,
    status: "已通过",
    submittedAt: "2026-11-18 15:07",
    review: "穴位与疗程字段复核无误。",
  },
  {
    id: "CASE-2026-194",
    kind: "病案",
    title: "病案 · 41 岁 · 继发性不孕 5 年（脾肾阳虚证）",
    status: "需修改",
    submittedAt: "2026-11-17 09:36",
    review: "AFC 与超声描述不一致，请核对。",
  },
  {
    id: "LIT-2026-092",
    kind: "文献",
    title: TITLES.meta,
    status: "已提交",
    submittedAt: "2026-11-16 17:55",
    review: "",
  },
  {
    id: "LIT-2026-090",
    kind: "文献",
    title: "DOR 患者中医体质分布与证型相关性分析",
    status: "需修改",
    submittedAt: "2026-11-15 11:23",
    review: "研究类型与原文描述不符，建议改为横断面研究。",
  },
];

const activeTab = ref("tasks");
const activeTasks = computed(() =>
  annotationStore.tasks.filter((t) => ["assigned", "drafting"].includes(t.status)),
);
const selectedTaskId = ref("");
const selectedTask = computed(
  () => activeTasks.value.find((t) => t.id === selectedTaskId.value) || null,
);

const KIND_COLORS = { lit: "#00796b", case: "#b06a00" };
function taskColor(task) {
  return KIND_COLORS[task.kind] || "var(--line)";
}
const activeTaskColor = computed(() =>
  selectedTask.value ? taskColor(selectedTask.value) : "var(--line)",
);

function taskStatusLabel(status) {
  return (
    { assigned: "待标注", drafting: "标注中", rework: "返工中" }[status] || status
  );
}
function taskStatusCls(status) {
  if (status === "drafting") return "badge-teal";
  if (status === "rework") return "badge-danger";
  return "badge-muted";
}

const itemsById = reactive({});
function syncTaskItems(task) {
  if (!task) return;
  task.docIds.forEach((id) => {
    if (itemsById[id]) return;
    const doc = etlStore.get(id);
    if (!doc) return;
    itemsById[id] = {
      id: doc.id,
      originalId: doc.id,
      title: doc.name,
      status: "待标注",
      values: { ...doc.values },
    };
  });
}
function taskProcessed(task) {
  return task.docIds.filter((id) => itemsById[id] && itemsById[id].status !== "待标注").length;
}

const reworkTasks = computed(() => annotationStore.reworkTasks);

function resubmitRework(task) {
  annotationStore.resubmit(task.id);
  showToast(`任务 ${task.id} 已重新提交复核`, "ok");
}

const selectedDocId = ref("");
const form = ref({});
const confirmOpen = ref(false);
const originalFont = ref("md");
const workListCollapsed = ref(false);
const sourceWidth = ref(null);
const sourceResizing = ref(false);
const workLayoutRef = ref(null);
let resizeStartX = 0;
let resizeStartW = 0;

function setListCollapsed(collapsed) {
  if (collapsed === workListCollapsed.value) return;
  workListCollapsed.value = collapsed;
  sourceWidth.value = null;
}

function startSourceResize(e) {
  sourceResizing.value = true;
  resizeStartX = e.clientX;
  const source = workLayoutRef.value?.querySelector(".original-panel");
  resizeStartW = source ? source.getBoundingClientRect().width : 0;
  window.addEventListener("pointermove", onSourceResize);
  window.addEventListener("pointerup", stopSourceResize);
}

function onSourceResize(e) {
  if (!sourceResizing.value) return;
  const rect = workLayoutRef.value?.getBoundingClientRect();
  const listWidth = workListCollapsed.value ? 26 : rect ? rect.width * 0.2 : 0;
  const max = rect ? rect.width - listWidth - 320 - 31 : 900;
  sourceWidth.value = Math.min(
    Math.max(280, max),
    Math.max(280, resizeStartW + (e.clientX - resizeStartX)),
  );
}

function stopSourceResize() {
  sourceResizing.value = false;
  window.removeEventListener("pointermove", onSourceResize);
  window.removeEventListener("pointerup", stopSourceResize);
}

const toast = reactive({ show: false, message: "", tone: "ok" });
let toastTimer = null;

const activeItems = computed(() => {
  if (!selectedTask.value) return [];
  return selectedTask.value.docIds.map((id) => itemsById[id]).filter(Boolean);
});

const currentId = computed(() => selectedDocId.value);

const currentItem = computed(
  () => activeItems.value.find((item) => item.id === currentId.value) || null,
);

const currentDoc = computed(() =>
  currentItem.value ? etlStore.get(currentItem.value.id) : null,
);

const currentKind = computed(() => currentDoc.value?.kind || "lit");

const currentOriginal = computed(() => resolveOriginal(currentDoc.value));

const stagedCount = computed(
  () => activeItems.value.filter((item) => item.status === "已暂存").length,
);

const visibleGroups = computed(() => {
  const groups = currentKind.value === "case" ? CASE_GROUPS : LIT_GROUPS;
  const flat = flattenGroups(groups);
  return groups.slice(0, 2).map((group) => ({
    label: group.label,
    fields: flat.filter((field) => field.group === group.label),
  }));
});

function displayValue(keyField) {
  const raw = currentItem.value ? currentItem.value.values[keyField.key] : "";
  if (raw === undefined || raw === null || raw === "") return "—";
  return keyField.unit && /^[\d.]+$/.test(raw) ? `${raw} ${keyField.unit}` : raw;
}

function loadItem(id) {
  const item = itemsById[id];
  form.value = item ? { ...item.values } : {};
}

function ensureTaskSelection() {
  if (!activeTasks.value.some((t) => t.id === selectedTaskId.value)) {
    selectedTaskId.value = activeTasks.value[0]?.id || "";
  }
  activeTasks.value.forEach(syncTaskItems);
  const task = selectedTask.value;
  if (task && !task.docIds.includes(selectedDocId.value)) {
    selectedDocId.value = task.docIds[0] || "";
  }
  loadItem(selectedDocId.value);
}

function switchTab(tab) {
  activeTab.value = tab;
  if (tab === "tasks") {
    ensureTaskSelection();
  }
}

function selectTask(task) {
  selectedTaskId.value = task.id;
  syncTaskItems(task);
  if (!task.docIds.includes(selectedDocId.value)) {
    selectedDocId.value = task.docIds[0] || "";
  }
  loadItem(selectedDocId.value);
  nextTick(() => {
    document
      .querySelector(".task-card.active")
      ?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  });
}

function onTaskWheel(e) {
  e.currentTarget.scrollLeft += e.deltaY || e.deltaX;
}

function stepTask(delta) {
  const list = activeTasks.value;
  if (!list.length) return;
  const idx = list.findIndex((t) => t.id === selectedTaskId.value);
  const next =
    idx === -1
      ? delta > 0
        ? 0
        : list.length - 1
      : Math.min(list.length - 1, Math.max(0, idx + delta));
  const task = list[next];
  if (task) selectTask(task);
}

function selectItem(id) {
  selectedDocId.value = id;
  loadItem(id);
}

function isLongField(field) {
  return (
    !field.options &&
    (LONG_KEYS.includes(field.key) || field.desc.length > 14)
  );
}

function showToast(message, tone = "ok") {
  toast.message = message;
  toast.tone = tone;
  toast.show = true;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.show = false;
  }, 2600);
}

ensureTaskSelection();
watch(activeTasks, ensureTaskSelection);

function prevItem() {
  const list = activeItems.value;
  if (!list.length) return;
  const idx = list.findIndex((item) => item.id === currentId.value);
  const prev = list[(idx - 1 + list.length) % list.length];
  if (prev) selectItem(prev.id);
}

function nextItem() {
  const list = activeItems.value;
  if (!list.length) return;
  const idx = list.findIndex((item) => item.id === currentId.value);
  const next = list[(idx + 1) % list.length];
  if (next) selectItem(next.id);
}

function goNext() {
  const list = activeItems.value;
  const index = list.findIndex((item) => item.id === currentId.value);
  for (let step = 1; step <= list.length; step += 1) {
    const next = list[(index + step) % list.length];
    if (next.id !== currentId.value && next.status === "待标注") {
      selectItem(next.id);
      return;
    }
  }
  showToast("本任务待标注条目已全部处理", "warn");
}

function markNoChange() {
  const item = currentItem.value;
  if (!item) return;
  item.values = {};
  item.status = "已暂存";
  item.note = "无需修改";
  annotationStore.markDrafting([item.id]);
  loadItem(item.id);
  showToast(`${item.id} 已标记为无需修改`);
  goNext();
}

function stashCurrent() {
  const item = currentItem.value;
  if (!item) return;
  item.values = { ...form.value };
  item.status = "已暂存";
  annotationStore.markDrafting([item.id]);
  showToast(`${item.id} 已暂存到本地`);
  goNext();
}

function openSubmit() {
  confirmOpen.value = true;
}

function confirmSubmit() {
  const staged = activeItems.value.filter((item) => item.status === "已暂存");
  const submittedAt = "2026-11-24 16:40";
  staged.forEach((item) => {
    item.status = "已提交";
    item.submittedAt = submittedAt;
  });
  if (staged.length) {
    annotationStore.submitByDocs(staged.map((item) => item.id));
  }
  confirmOpen.value = false;
  showToast(
    staged.length
      ? `已提交本批 ${staged.length} 条标注`
      : "暂无已暂存的标注，未执行提交",
    staged.length ? "ok" : "warn",
  );
}
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

.tab {
  position: relative;
  padding: 9px 16px 11px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--ink-500);
  cursor: pointer;
  transition: color 0.15s;
}

.tab:hover {
  color: var(--ink-700);
}

.tab.active {
  color: var(--teal-dark);
  font-weight: 600;
}

.tab.active::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--teal);
}

.tab-count {
  margin-left: 4px;
  padding: 0 6px;
  border-radius: 999px;
  background: #eef1f1;
  font-size: 10px;
  color: var(--ink-500);
}

.tab.active .tab-count {
  background: var(--teal-soft);
  color: var(--teal-dark);
}

/* ── 标注任务卡片 ── */
.review-carousel { display: flex; align-items: stretch; gap: 10px; margin-bottom: 16px; }
.carousel-arrow {
  flex: 0 0 34px; width: 34px; border: none; background: transparent;
  color: #64748b; opacity: 0.35; cursor: pointer; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: opacity 0.15s, background 0.15s;
}
.carousel-arrow:hover:not(:disabled) { opacity: 1; background: #f1f5f4; }
.carousel-arrow:disabled { opacity: 0.2; cursor: default; }
.carousel-arrow svg { width: 26px; height: 26px; }
.task-cards {
  display: flex; gap: 10px; overflow-x: auto; scroll-behavior: smooth;
  padding-bottom: 4px; flex: 1; min-width: 0;
  scrollbar-width: thin;
}
.task-cards::-webkit-scrollbar { height: 6px; }
.task-cards::-webkit-scrollbar-thumb { background: #dfe7e5; border-radius: 3px; }
.task-card {
  flex: 0 0 252px; width: 252px; cursor: pointer;
  display: flex;
  flex-direction: column;
  padding: 10px 12px 9px;
  border: 1px solid var(--task-color, var(--line));
  border-radius: 10px;
  background: #fff;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}
.task-card:hover {
  border-color: var(--task-color, var(--teal-border));
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
}
.task-card.active {
  border-color: var(--task-color, var(--teal));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--task-color, var(--teal)) 14%, transparent);
}
.task-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
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
  flex-wrap: nowrap;
}
.task-count { font-size: 12px; color: var(--ink-500); }
.pending-chip {
  flex-shrink: 0;
  font-size: 10px; color: #b06a00; background: #fff7e6;
  border: 1px solid #ffe3b3; border-radius: 999px; padding: 1px 7px; white-space: nowrap;
}
.task-time { margin: 6px 0 0; font-size: 10px; color: var(--ink-400); }
.review-empty {
  padding: 46px 20px;
  border: 1px dashed #d8dfe2;
  border-radius: 10px;
  background: #fbfcfc;
  text-align: center;
}
.review-empty p { margin: 0 0 6px; font-size: 13px; color: var(--ink-700); }
.review-empty span { font-size: 11px; color: var(--ink-400); }

.workbench-fill { display: flex; flex-direction: column; height: 100%; }
.workbench-fill .tabs,
.workbench-fill .review-carousel { flex-shrink: 0; }
.workbench-fill .work-layout { flex: 1 1 auto; height: auto; min-height: 560px; }
.work-layout {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.task-list { flex: 0 0 auto; width: calc((100% - 43px) * 0.2); min-width: 0; }
.original-panel { flex: 0 0 auto; width: calc((100% - 43px) * 0.4); min-width: 0; }
.editor { flex: 1 1 0; min-width: 0; }
.work-layout.list-collapsed .original-panel { width: calc((100% - 69px) * 0.6); }
.source-editor-splitter {
  flex: 0 0 7px; cursor: col-resize; background: #f0f2f2;
  border-left: 1px solid #e8e8e8; border-right: 1px solid #e8e8e8;
  border-radius: 4px; position: relative; touch-action: none;
}
.source-editor-splitter::after {
  content: ""; position: absolute; top: 50%; left: 50%; width: 3px; height: 30px;
  transform: translate(-50%, -50%); border-radius: 3px; background: #c9d6d4;
}
.source-editor-splitter:hover { background: #e0f2f1; }
.source-editor-splitter:hover::after { background: #00796b; }

.task-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  transition: border-color 0.16s ease;
}
.list-head-right { display: flex; align-items: center; gap: 8px; }
.list-toggle {
  border: none; background: transparent; color: #8a9695; cursor: pointer;
  font-size: 15px; line-height: 1; padding: 0 2px;
}
.list-toggle:hover { color: #00796b; }
.work-layout.list-collapsed .work-list-rail { flex: 0 0 26px; }
.work-list-rail {
  display: flex; flex-direction: column; border: 1px solid var(--line);
  border-left-width: 3px;
  border-radius: 10px; background: #fafbfb; overflow: hidden;
}
.work-list-rail button {
  border: none; background: transparent; color: #8a9695; cursor: pointer;
  font-size: 14px; padding: 8px 0;
}
.work-list-rail button:hover { color: #00796b; background: #f0f7f6; }

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700);
}

.list-count {
  font-weight: 400;
  font-size: 11px;
  color: var(--ink-400);
}

.list-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
}

.task-item {
  display: block;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-left: 3px solid transparent;
  border-radius: 6px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.task-item:hover {
  background: #f7fafa;
}

.task-item.active {
  border-left-color: var(--teal);
  background: var(--teal-soft);
}

.task-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.task-no {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--ink-500);
}

.task-title {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  font-size: 12px;
  line-height: 1.45;
  color: var(--ink-700);
}

.task-item.active .task-title {
  color: var(--ink-900);
}

.task-item .badge {
  flex-shrink: 0;
  padding: 1px 6px;
  font-size: 10px;
}

.original-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.original-head {
  flex-shrink: 0;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  background: #fbfdfd;
}

.original-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.original-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700);
}

.font-switch {
  display: flex;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}

.font-btn {
  padding: 2px 7px;
  border: none;
  border-radius: 4px;
  background: transparent;
  font-size: 11px;
  color: var(--ink-500);
  cursor: pointer;
}

.font-btn.active {
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-weight: 600;
}

.original-meta {
  flex-shrink: 0;
  padding: 12px 14px 10px;
  border-bottom: 1px dashed var(--line);
}

.original-source {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--ink-400);
}

.original-name {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ink-900);
}

.original-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.75;
  color: var(--ink-700);
  background: #fff;
}

.original-body.font-sm {
  font-size: 12px;
}

.original-body.font-md {
  font-size: 13.5px;
}

.original-body.font-lg {
  font-size: 15.5px;
}

.original-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 24px;
  text-align: center;
  color: var(--ink-400);
}

.original-empty p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}

.original-empty span {
  font-size: 11px;
  line-height: 1.5;
}

.editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
  padding: 14px 20px;
  border-bottom: 1px solid var(--line);
}

.editor-title {
  min-width: 0;
}

.editor-no {
  display: inline-block;
  margin-bottom: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--teal-dark);
}

.editor-title h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--ink-900);
}

.editor-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.group-hint {
  font-size: 11px;
  color: var(--ink-400);
}

.key-fields {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  flex-shrink: 0;
  padding: 9px 20px;
  border-bottom: 1px dashed var(--line);
  background: #fbfdfd;
}

.key-fields-label {
  font-size: 11px;
  color: var(--ink-400);
}

.key-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid var(--teal-border);
  border-radius: 999px;
  background: var(--teal-soft);
  font-size: 11px;
}

.key-name {
  color: var(--teal-dark);
}

.key-value {
  color: var(--ink-700);
  font-weight: 600;
}

.editor-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 20px 18px;
}

.field-group {
  margin-top: 16px;
}

.group-title {
  margin: 0 0 10px;
  padding-left: 8px;
  border-left: 3px solid var(--teal);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
}

.group-count {
  margin-left: 6px;
  font-size: 10px;
  font-weight: 400;
  color: var(--ink-400);
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.field-item.wide {
  grid-column: 1 / -1;
}

.field-label {
  display: block;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--ink-700);
}

.req {
  margin-left: 2px;
  color: var(--danger);
}

.field-control {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  font-family: inherit;
  font-size: 13px;
  color: var(--ink-900);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.field-control:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(0, 121, 107, 0.08);
}

.field-control::placeholder {
  color: #b3bcc4;
}

.field-textarea {
  min-height: 66px;
  line-height: 1.5;
  resize: vertical;
}

.editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
  margin-top: auto;
  padding: 12px 20px;
  border-top: 1px solid var(--line);
  background: #fcfdfd;
  border-radius: 0 0 10px 10px;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.editor-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--ink-400);
}

.empty-mark {
  font-size: 32px;
  color: #cfd8dc;
}

.editor-empty p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}

.editor-empty span {
  font-size: 11px;
}

.badge-lit {
  border: 1px solid var(--teal-border);
  background: var(--teal-soft);
  color: var(--teal-dark);
}

.badge-case {
  border: 1px solid #e6d3a8;
  background: #fdf6e5;
  color: #9a6b12;
}

.records {
  overflow: hidden;
}

.records-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
}

.records-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
}

.records-head span {
  font-size: 11px;
  color: var(--ink-400);
}

.cell-no {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--teal-dark);
  white-space: nowrap;
}

.col-kind {
  width: 92px;
}

.cell-title {
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-time {
  color: var(--ink-500);
  white-space: nowrap;
}

.cell-review {
  max-width: 300px;
  font-size: 12px;
  color: var(--ink-700);
}

.cell-review.muted {
  color: var(--ink-400);
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(26, 26, 46, 0.36);
}

.modal {
  width: 100%;
  max-width: 400px;
  padding: 22px 24px 18px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 18px 46px rgba(26, 26, 46, 0.22);
}

.modal h3 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
}

.modal p {
  margin: 0 0 18px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-500);
}

.modal p strong {
  color: var(--teal-dark);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 30px;
  z-index: 40;
  transform: translateX(-50%);
  padding: 10px 18px;
  border-left: 3px solid var(--teal);
  border-radius: 8px;
  background: #263238;
  box-shadow: 0 10px 26px rgba(26, 26, 46, 0.24);
  font-size: 13px;
  color: #fff;
  white-space: nowrap;
}

.toast-warn {
  border-left-color: #ffb74d;
}

.toast-pop-enter-active,
.toast-pop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-pop-enter-from,
.toast-pop-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

@media (max-width: 1100px) {
  .workbench-fill .work-layout { flex: 0 0 auto; }
  .work-layout { flex-wrap: wrap; height: auto; min-height: 0; }

  .task-list {
    flex: 1 1 100%;
    height: auto;
    max-height: 700px;
  }

  .original-panel {
    flex: 1 1 100%;
    width: auto !important;
    height: 300px;
  }

  .source-editor-splitter { display: none; }

  .editor {
    flex: 1 1 100%;
    height: 620px;
  }



  .editor-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}

/* ── 抽取校验 ── */
.review-panel { padding: 16px 18px; }
.review-panel .records-head { margin-bottom: 12px; }
.col-kind { width: 80px; }
.col-status { width: 90px; }
.col-conf { width: 80px; }
.col-prob { width: 70px; }
.col-actions { width: 120px; }
.badge-review { background: #fff8e1; color: #f57f17; }
.badge-validated { background: #e0f2f1; color: #00695c; }
.err-text { color: #c62828; font-weight: 600; }

.review-modal {
  width: 1220px; max-width: 96vw; height: 86vh;
  background: #fff; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 24px 60px rgba(0,0,0,.25);
}
.review-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #e8e8e8; background: #fafafa; }
.review-head strong { font-size: 14px; }
.review-hint { margin-left: 10px; font-size: 11px; color: #888; }
.modal-x { border: none; background: transparent; font-size: 20px; color: #999; cursor: pointer; }
.review-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 32% 68%; }
.review-src { border-right: 1px solid #e8e8e8; background: #fafafa; padding: 12px; overflow-y: auto; }
.review-src h4, .review-fields h4 { margin: 0 0 8px; font-size: 12px; color: #666; }
.src-title { margin: 0 0 8px; font-size: 13px; font-weight: 600; }
.src-body { margin: 0; white-space: pre-wrap; font-size: 12px; line-height: 1.8; color: #333; font-family: inherit; }
.review-fields { display: flex; flex-direction: column; min-height: 0; padding: 12px; }
.rf-scroll { flex: 1; overflow-y: auto; }
.rf-group { margin-bottom: 14px; }
.rf-group h5 { display: flex; align-items: center; gap: 6px; margin: 0 0 8px; font-size: 12px; color: #00796b; }
.rf-group h5 span { font-size: 10px; padding: 0 6px; border-radius: 999px; background: #e0f2f1; }
.rf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.rf-item { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.rf-label { font-size: 11px; color: #667; }
.rf-label i { color: #c62828; font-style: normal; margin-left: 2px; }
.rf-control { width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid #d5d9d8; border-radius: 5px; font-size: 12px; outline: none; background: #fff; font-family: inherit; }
.rf-control:focus { border-color: #00796b; }
.rf-err { font-size: 10px; color: #c62828; font-style: normal; }
.review-foot { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-top: 1px solid #e8e8e8; background: #fafafa; }
.review-foot .foot-hint { font-size: 11px; color: #999; }
.review-foot .foot-actions { display: flex; gap: 8px; }
.review-foot .btn-primary { padding: 6px 16px; }
</style>
