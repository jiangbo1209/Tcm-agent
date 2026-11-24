<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-main">
        <h1>标注工作台</h1>
        <p class="header-sub">DOR 文献抽取复核 · 本地原型（不调用接口）</p>
        <div class="task-meta">
          <span class="task-code">{{ TASK.id }}</span>
          <span class="meta-item">来源池「{{ TASK.pool }}」</span>
          <span class="meta-item deadline">{{ TASK.deadline }}</span>
        </div>
      </div>
      <div class="progress-box">
        <div class="progress-text">
          已处理 <strong>{{ processed }}</strong><span>/ 20</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'batch' }"
        @click="activeTab = 'batch'"
      >
        评审批次
        <span class="tab-count">{{ items.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'records' }"
        @click="activeTab = 'records'"
      >
        我的标注记录
        <span class="tab-count">{{ records.length }}</span>
      </button>
    </div>

    <!-- 评审批次 -->
    <div v-if="activeTab === 'batch'" class="batch-layout">
      <aside class="task-list card">
        <div class="list-head">
          <span>本批条目</span>
          <span class="list-count">{{ items.length }} 条</span>
        </div>
        <div class="list-body">
          <button
            v-for="item in items"
            :key="item.id"
            class="task-item"
            :class="{ active: item.id === selectedId }"
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

      <section class="editor card">
        <template v-if="currentItem">
          <header class="editor-head">
            <div class="editor-title">
              <span class="editor-no">{{ currentItem.id }}</span>
              <h2 :title="currentItem.title">{{ currentItem.title || "未命名条目" }}</h2>
            </div>
            <div class="editor-meta">
              <span class="badge" :class="STATUS_META[currentItem.status]">
                {{ currentItem.status }}
              </span>
              <span class="group-hint">按文献母版前 2 组渲染</span>
            </div>
          </header>

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
            <span class="footer-hint">
              字段值仅保存在当前浏览器内存中，刷新即还原 mock 数据
            </span>
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
          <span>从左侧「本批条目」中选择一条开始标注</span>
        </div>
      </section>
    </div>

    <!-- 我的标注记录 -->
    <div v-else class="records card">
      <div class="records-head">
        <h2>我的标注记录</h2>
        <span>近 30 天提交的标注与复核意见</span>
      </div>
      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th class="col-no">编号</th>
              <th>标题</th>
              <th class="col-status">状态</th>
              <th class="col-time">提交时间</th>
              <th>复核意见</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.id">
              <td class="cell-no">{{ record.id }}</td>
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
              <td colspan="5" class="empty-row">暂无提交记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 提交确认 -->
    <div v-if="confirmOpen" class="modal-mask" @click.self="confirmOpen = false">
      <div class="modal">
        <h3>确认提交整批标注？</h3>
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
import { computed, reactive, ref } from "vue";
import { LIT_GROUPS, flattenGroups } from "../../constants/dorFields";

const TASK = {
  id: "TASK-2026-014",
  pool: "DOR 文献抽取复核",
  deadline: "剩 3 天",
};

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

const TITLES = {
  sys: "补肾填精法治疗卵巢储备功能减退的系统评价",
  rct: "左归丸联合西药治疗 DOR 的随机对照试验",
  needle: "针药结合治疗肾虚肝郁型 DOR 的临床观察",
  cohort: "温肾健脾法干预脾肾阳虚型 DOR 的队列研究",
  dea: "电针联合 DHEA 对卵巢储备功能减退的疗效分析",
  meta: "中西医结合治疗 DOR 的系统评价与 Meta 分析",
};

const items = reactive([
  {
    id: "LIT-2026-101",
    title: TITLES.sys,
    status: "已提交",
    values: {
      lit_1: TITLES.sys,
      lit_2: "陈某某、李某某",
      lit_3: "2024",
      lit_4: "META分析/系统评价",
      lit_6: "28.4±4.1",
      lit_7: "2016中国卵巢储备功能减退专家共识",
    },
  },
  {
    id: "LIT-2026-102",
    title: TITLES.needle,
    status: "已提交",
    values: {
      lit_1: TITLES.needle,
      lit_2: "赵某某",
      lit_3: "2023",
      lit_4: "随机对照试验(RCT)",
      lit_6: "31.2±3.6",
    },
  },
  {
    id: "LIT-2026-103",
    title: TITLES.rct,
    status: "已暂存",
    values: {
      lit_1: TITLES.rct,
      lit_2: "王某某、周某某",
      lit_3: "2023",
      lit_4: "随机对照试验(RCT)",
      lit_7: "博洛尼亚(Bologna)标准",
      lit_8: "AMH<1.1ng/mL 且 AFC≤5 个",
    },
  },
  {
    id: "LIT-2026-104",
    title: TITLES.cohort,
    status: "已提交",
    values: {
      lit_1: TITLES.cohort,
      lit_2: "孙某某",
      lit_3: "2022",
      lit_4: "队列研究",
    },
  },
  {
    id: "LIT-2026-105",
    title: TITLES.dea,
    status: "已暂存",
    values: {
      lit_1: TITLES.dea,
      lit_2: "刘某某、吴某某",
      lit_3: "2024",
      lit_4: "随机对照试验(RCT)",
      lit_8: "AFC<5 个，FSH>10 IU/L",
      lit_9: "AMH 0.62 ng/mL，AFC 4 个，FSH 11.8 IU/L",
    },
  },
  {
    id: "LIT-2026-106",
    title: "毓麟珠联合 IVF-ET 改善 DOR 患者妊娠结局的回顾性研究",
    status: "已提交",
    values: {
      lit_1: "毓麟珠联合 IVF-ET 改善 DOR 患者妊娠结局的回顾性研究",
      lit_2: "郑某某",
      lit_3: "2021",
      lit_4: "病例对照研究",
    },
  },
  {
    id: "LIT-2026-107",
    title: "基于数据挖掘的 DOR 中医用药规律研究",
    status: "待标注",
    values: {},
  },
  {
    id: "LIT-2026-108",
    title: "耳穴压豆辅助治疗 DOR 的病例系列",
    status: "待标注",
    values: {},
  },
  {
    id: "LIT-2026-109",
    title: "补肾填精法调节 DOR 患者性激素水平的机制探讨",
    status: "待标注",
    values: {},
  },
  {
    id: "LIT-2026-110",
    title: TITLES.meta,
    status: "待标注",
    values: {},
  },
]);

const records = [
  {
    id: "LIT-2026-098",
    title: TITLES.sys,
    status: "已通过",
    submittedAt: "2026-11-20 16:42",
    review: "抽取完整，结局指标已核对，通过。",
  },
  {
    id: "LIT-2026-096",
    title: TITLES.rct,
    status: "需修改",
    submittedAt: "2026-11-19 10:18",
    review: "AMH 单位疑似录入错误，请对照原文后重新提交。",
  },
  {
    id: "LIT-2026-095",
    title: TITLES.needle,
    status: "已通过",
    submittedAt: "2026-11-18 15:07",
    review: "穴位与疗程字段复核无误。",
  },
  {
    id: "CASE-2026-031",
    title: "肾虚肝郁型 DOR 病案一例（随访 12 个月）",
    status: "已通过",
    submittedAt: "2026-11-17 09:36",
    review: "四诊信息与证型判定一致。",
  },
  {
    id: "LIT-2026-092",
    title: TITLES.meta,
    status: "已提交",
    submittedAt: "2026-11-16 17:55",
    review: "",
  },
  {
    id: "LIT-2026-090",
    title: "DOR 患者中医体质分布与证型相关性分析",
    status: "需修改",
    submittedAt: "2026-11-15 11:23",
    review: "研究类型与原文描述不符，建议改为横断面研究。",
  },
];

const activeTab = ref("batch");
const selectedId = ref("LIT-2026-107");
const form = ref({});
const confirmOpen = ref(false);
const extraProcessed = ref(0);

const toast = reactive({ show: false, message: "", tone: "ok" });
let toastTimer = null;

const currentItem = computed(
  () => items.find((item) => item.id === selectedId.value) || null,
);

const processed = computed(() => Math.min(20, 6 + extraProcessed.value));

const progressPct = computed(() => Math.round((processed.value / 20) * 100));

const stagedCount = computed(
  () => items.filter((item) => item.status === "已暂存").length,
);

const visibleGroups = computed(() => {
  const flat = flattenGroups(LIT_GROUPS);
  return LIT_GROUPS.slice(0, 2).map((group) => ({
    label: group.label,
    fields: flat.filter((field) => field.group === group.label),
  }));
});

function selectItem(id) {
  selectedId.value = id;
  const item = items.find((entry) => entry.id === id);
  form.value = item ? { ...item.values } : {};
}

function isLongField(field) {
  return (
    !field.options &&
    (field.desc.length > 9 || ["lit_8", "lit_9", "lit_13", "lit_14"].includes(field.key))
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

function goNext() {
  const index = items.findIndex((item) => item.id === selectedId.value);
  for (let step = 1; step <= items.length; step += 1) {
    const next = items[(index + step) % items.length];
    if (next.id !== selectedId.value && next.status === "待标注") {
      selectItem(next.id);
      return;
    }
  }
  showToast("本批待标注条目已全部处理", "warn");
}

function markNoChange() {
  const item = currentItem.value;
  if (!item) return;
  const wasPending = item.status === "待标注";
  item.values = {};
  item.status = "已提交";
  item.note = "无需修改";
  if (wasPending) extraProcessed.value += 1;
  showToast(`${item.id} 已标记为无需修改`);
  goNext();
}

function stashCurrent() {
  const item = currentItem.value;
  if (!item) return;
  const wasPending = item.status === "待标注";
  item.values = { ...form.value };
  item.status = "已暂存";
  if (wasPending) extraProcessed.value += 1;
  showToast(`${item.id} 已暂存到本地`);
  goNext();
}

function openSubmit() {
  confirmOpen.value = true;
}

function confirmSubmit() {
  const staged = items.filter((item) => item.status === "已暂存");
  const submittedAt = "2026-11-24 16:40";
  staged.forEach((item) => {
    item.status = "已提交";
    item.submittedAt = submittedAt;
  });
  confirmOpen.value = false;
  showToast(
    staged.length
      ? `已提交整批 ${staged.length} 条标注`
      : "暂无已暂存的标注，未执行提交",
    staged.length ? "ok" : "warn",
  );
}
</script>

<style scoped>
.header-main {
  min-width: 0;
}

.task-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--ink-500);
}

.task-code {
  padding: 2px 8px;
  border: 1px solid var(--teal-border);
  border-radius: 4px;
  background: var(--teal-soft);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--teal-dark);
}

.meta-item {
  position: relative;
  padding-left: 12px;
}

.meta-item::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c3cbd3;
  transform: translateY(-50%);
}

.meta-item.deadline {
  color: var(--warn);
  font-weight: 500;
}

.progress-box {
  width: 190px;
  flex-shrink: 0;
  padding-top: 6px;
}

.progress-text {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--ink-500);
  text-align: right;
}

.progress-text strong {
  font-size: 18px;
  color: var(--teal-dark);
}

.progress-text span {
  color: var(--ink-400);
}

.progress-track {
  height: 6px;
  border-radius: 999px;
  background: #e8eeee;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #26a69a, var(--teal));
  transition: width 0.25s ease;
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.tab {
  position: relative;
  padding: 9px 16px 10px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--ink-500);
  cursor: pointer;
  transition: color 0.15s;
}

.tab:hover {
  color: var(--teal);
}

.tab.active {
  color: var(--teal-dark);
  font-weight: 600;
}

.tab.active::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 2px;
  border-radius: 2px;
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

.batch-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.task-list {
  overflow: hidden;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  flex-direction: column;
  max-height: 620px;
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

.editor {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
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

.editor-body {
  padding: 4px 20px 18px;
  max-height: 560px;
  overflow-y: auto;
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
  margin-top: auto;
  padding: 12px 20px;
  border-top: 1px solid var(--line);
  background: #fcfdfd;
  border-radius: 0 0 10px 10px;
}

.footer-hint {
  font-size: 11px;
  color: var(--ink-400);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.editor-empty {
  min-height: 420px;
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

.cell-title {
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-time {
  color: var(--ink-500);
  white-space: nowrap;
}

.cell-review {
  max-width: 320px;
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
  .batch-layout {
    grid-template-columns: 240px minmax(0, 1fr);
  }
}
</style>
