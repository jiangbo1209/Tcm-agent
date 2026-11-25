<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-main">
        <h1>标注工作台</h1>
        <p class="header-sub">DOR 文献 / 病案抽取复核 · 本地原型（不调用接口）</p>
        <div class="task-meta">
          <span class="task-code">{{ TASK.id }}</span>
          <span class="meta-item">来源池「{{ TASK.pool }}」</span>
          <span class="meta-item">当前对象：{{ scopeLabel }}</span>
          <span class="meta-item deadline">{{ TASK.deadline }}</span>
        </div>
      </div>
      <div v-if="activeTab !== 'review'" class="progress-box">
        <div class="progress-text">
          已处理 <strong>{{ processed }}</strong><span>/ {{ total }}</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- 对象切换 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'lit' }"
        @click="switchTab('lit')"
      >
        文献标注
        <span class="tab-count">{{ litItems.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'case' }"
        @click="switchTab('case')"
      >
        病案标注
        <span class="tab-count">{{ caseItems.length }}</span>
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

    <!-- 标注工作区：任务列表 | 原文面板 | 字段表单 -->
    <div
      v-if="activeTab === 'lit' || activeTab === 'case'"
      class="work-layout"
      :class="{ 'list-collapsed': workListCollapsed }"
    >
      <aside v-if="!workListCollapsed" class="task-list card" :style="{ width: workListWidth + 'px' }">
        <div class="list-head">
          <span>{{ activeTab === 'case' ? '病案条目' : '文献条目' }}</span>
          <div class="list-head-right">
            <span class="list-count">{{ activeItems.length }} 条</span>
            <button class="list-toggle" type="button" title="收起条目列表" @click="workListCollapsed = true">«</button>
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

      <div v-else class="work-list-rail">
        <button type="button" title="展开条目列表" @click="workListCollapsed = false">»</button>
        <button type="button" title="上一条" @click="prevItem">‹</button>
        <button type="button" title="下一条" @click="nextItem">›</button>
      </div>

      <div
        v-if="!workListCollapsed"
        class="list-resizer"
        title="拖动调整列表宽度"
        @pointerdown.prevent="startListResize"
      ></div>

      <section class="original-panel card">
        <header class="original-head">
          <div class="original-title">
            <span class="original-tag">{{ activeTab === 'case' ? '病案原文' : '文献原文' }}</span>
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
              <span class="group-hint">
                {{ activeTab === 'case' ? '按病案母版前 2 组渲染' : '按文献母版前 2 组渲染' }}
              </span>
            </div>
          </header>

          <div v-if="activeTab === 'case'" class="key-fields">
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
          <span>从左侧「{{ activeTab === 'case' ? '病案条目' : '文献条目' }}」中选择一条开始标注</span>
        </div>
      </section>
    </div>

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
        <h3>确认提交整批{{ scopeLabel }}标注？</h3>
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
import { CASE_GROUPS, LIT_GROUPS, flattenGroups } from "../../constants/dorFields";
import { ORIGINALS, resolveOriginal } from "../../data/originals";
import { etlStore } from "../../stores/etl";
import { annotationStore } from "../../stores/annotation";

const TASK = {
  id: "TASK-2026-014",
  pool: "DOR 文献 / 病案抽取复核",
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

const litItems = reactive([
  {
    id: "LIT-2026-101",
    originalId: "LIT-001",
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
    originalId: "LIT-002",
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
    originalId: "LIT-003",
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
    originalId: "LIT-004",
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
    originalId: "LIT-005",
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
    originalId: "LIT-006",
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

const caseItems = reactive([
  {
    id: "CASE-2026-201",
    originalId: "CASE-001",
    title: "病案 CASE-2026-201 · 34 岁 · 原发性不孕 3 年（肾虚证）",
    status: "已提交",
    values: {
      case_1: "34",
      case_3: "3",
      case_4: "原发性不孕",
      case_10: "0.68",
      case_11: "13.2",
      case_14: "4",
      case_15: "25—28",
      case_17: "未避孕未孕 3 年，经量偏少、色暗，腰酸畏寒",
      case_23: "肾虚证",
      case_24: "腰膝酸软、畏寒肢冷，舌淡苔白，脉沉细",
    },
  },
  {
    id: "CASE-2026-202",
    originalId: "CASE-002",
    title: "病案 CASE-2026-202 · 38 岁 · 继发性不孕 2 年（肝肾阴虚证）",
    status: "已暂存",
    values: {
      case_1: "38",
      case_3: "2",
      case_4: "继发性不孕",
      case_10: "0.42",
      case_11: "16.8",
      case_14: "2",
      case_15: "26—30",
      case_23: "肝肾阴虚证",
    },
  },
  {
    id: "CASE-2026-203",
    originalId: "CASE-003",
    title: "病案 CASE-2026-203 · 31 岁 · 原发性不孕 1 年半（肝郁气滞证）",
    status: "已提交",
    values: {
      case_1: "31",
      case_3: "1.5",
      case_4: "原发性不孕",
      case_10: "0.86",
      case_11: "11.4",
      case_14: "5",
      case_15: "28—35",
      case_23: "肝郁气滞证",
    },
  },
  {
    id: "CASE-2026-204",
    originalId: "CASE-004",
    title: "病案 CASE-2026-204 · 40 岁 · 继发性不孕 4 年（脾肾阳虚证）",
    status: "已提交",
    values: {
      case_1: "40",
      case_3: "4",
      case_4: "继发性不孕",
      case_10: "0.35",
      case_11: "18.2",
      case_14: "2",
      case_15: "23—26",
      case_23: "脾肾阳虚证",
    },
  },
  {
    id: "CASE-2026-205",
    originalId: "CASE-005",
    title: "病案 CASE-2026-205 · 36 岁 · 原发性不孕 2 年（肾虚血瘀证）",
    status: "已暂存",
    values: {
      case_1: "36",
      case_3: "2",
      case_4: "原发性不孕",
      case_10: "0.55",
      case_11: "14.6",
      case_14: "3",
      case_15: "26—29",
      case_23: "肾虚血瘀证",
    },
  },
  {
    id: "CASE-2026-206",
    originalId: "CASE-006",
    title: "病案 CASE-2026-206 · 29 岁 · 原发性不孕 1 年（痰湿证）",
    status: "待标注",
    values: {},
  },
  {
    id: "CASE-2026-207",
    title: "病案 CASE-2026-207 · 33 岁 · 原发性不孕 2 年（肾虚肝郁证）",
    status: "待标注",
    values: {},
  },
  {
    id: "CASE-2026-208",
    title: "病案 CASE-2026-208 · 42 岁 · 继发性不孕 5 年（气血两虚证）",
    status: "待标注",
    values: {},
  },
]);

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

const activeTab = ref("lit");

const reworkTasks = computed(() => annotationStore.reworkTasks);

function resubmitRework(task) {
  annotationStore.resubmit(task.id);
  showToast(`任务 ${task.id} 已重新提交复核`, "ok");
}
const selectedLitId = ref("");
const selectedCaseId = ref("");
const form = ref({});
const confirmOpen = ref(false);
const originalFont = ref("md");
const workListCollapsed = ref(false);
const workListWidth = ref(270);
const listResizing = ref(false);

function startListResize() {
  listResizing.value = true;
  window.addEventListener("pointermove", onListResize);
  window.addEventListener("pointerup", stopListResize);
}

function onListResize(e) {
  if (!listResizing.value) return;
  workListWidth.value = Math.min(420, Math.max(200, e.clientX - 232 - 32));
}

function stopListResize() {
  listResizing.value = false;
  window.removeEventListener("pointermove", onListResize);
  window.removeEventListener("pointerup", stopListResize);
}

const toast = reactive({ show: false, message: "", tone: "ok" });
let toastTimer = null;

const activeItems = computed(() => {
  if (activeTab.value === "case") return caseItems;
  if (activeTab.value === "rework") return [];
  return litItems;
});

const scopeLabel = computed(() => {
  if (activeTab.value === "case") return "病案";
  if (activeTab.value === "records") return "全部";
  if (activeTab.value === "rework") return "返工箱";
  return "文献";
});

const currentId = computed(() =>
  activeTab.value === "case" ? selectedCaseId.value : selectedLitId.value,
);

const currentItem = computed(
  () => activeItems.value.find((item) => item.id === currentId.value) || null,
);

const currentOriginal = computed(() => {
  const item = currentItem.value;
  if (!item) return null;
  return ORIGINALS[item.originalId || item.id] || null;
});

const scopeItems = computed(() => {
  if (activeTab.value === "records") return [...litItems, ...caseItems];
  if (activeTab.value === "rework") return [];
  return activeItems.value;
});

const processed = computed(
  () => scopeItems.value.filter((item) => item.status !== "待标注").length,
);

const total = computed(() => scopeItems.value.length);

const progressPct = computed(() =>
  total.value ? Math.round((processed.value / total.value) * 100) : 0,
);

const stagedCount = computed(
  () => activeItems.value.filter((item) => item.status === "已暂存").length,
);

const visibleGroups = computed(() => {
  const groups = activeTab.value === "case" ? CASE_GROUPS : LIT_GROUPS;
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
  const item = (activeTab.value === "case" ? caseItems : litItems).find(
    (entry) => entry.id === id,
  );
  form.value = item ? { ...item.values } : {};
}

function switchTab(tab) {
  activeTab.value = tab;
  if (tab === "lit" || tab === "case") {
    hydrateAssignedItems();
    loadItem(tab === "case" ? selectedCaseId.value : selectedLitId.value);
  }
}

function selectItem(id) {
  if (activeTab.value === "case") {
    selectedCaseId.value = id;
  } else {
    selectedLitId.value = id;
  }
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

function docToItem(doc) {
  return {
    id: doc.id,
    originalId: doc.id,
    title: doc.name,
    status: "待标注",
    values: { ...doc.values },
  };
}

function hydrateAssignedItems() {
  const lit = annotationStore.assignedDocs("lit").map(docToItem);
  const cs = annotationStore.assignedDocs("case").map(docToItem);
  litItems.splice(0, litItems.length, ...lit);
  caseItems.splice(0, caseItems.length, ...cs);
  if (!litItems.some((i) => i.id === selectedLitId.value)) {
    selectedLitId.value = litItems[0]?.id || "";
  }
  if (!caseItems.some((i) => i.id === selectedCaseId.value)) {
    selectedCaseId.value = caseItems[0]?.id || "";
  }
}

hydrateAssignedItems();
if (selectedLitId.value) loadItem(selectedLitId.value);

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
  showToast(`本批${scopeLabel.value}待标注条目已全部处理`, "warn");
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
      ? `已提交${scopeLabel.value}整批 ${staged.length} 条标注`
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

.work-layout {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.list-resizer {
  flex: 0 0 7px; cursor: col-resize; background: #f0f2f2;
  border-left: 1px solid #e8e8e8; border-right: 1px solid #e8e8e8;
  border-radius: 4px; position: relative; touch-action: none;
}
.list-resizer::after {
  content: ""; position: absolute; top: 50%; left: 50%; width: 3px; height: 30px;
  transform: translate(-50%, -50%); border-radius: 3px; background: #c9d6d4;
}
.list-resizer:hover { background: #e0f2f1; }
.list-resizer:hover::after { background: #00796b; }
.task-list { flex: 0 0 auto; min-width: 0; }
.original-panel { flex: 0 0 32%; min-width: 0; }
.editor { flex: 1 1 auto; min-width: 0; }

.task-list {
  display: flex;
  flex-direction: column;
  height: 700px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
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
  height: 700px;
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
  height: 700px;
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

@media (max-width: 1280px) {
  .original-panel { flex-basis: 30%; }
}

@media (max-width: 1100px) {
  .work-layout { flex-wrap: wrap; }

  .task-list {
    flex: 1 1 100%;
    height: auto;
    max-height: 700px;
  }

  .original-panel {
    flex: 1 1 100%;
    height: 300px;
  }

  .editor {
    flex: 1 1 100%;
    height: 620px;
  }

  .list-resizer { display: none; }

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
