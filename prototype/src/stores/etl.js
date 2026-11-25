import { reactive, computed } from "vue";
import { LIT_RECORDS, CASE_RECORDS } from "../data/dorMock";

/**
 * ETL 文档状态机（原型）：
 * pending → extracting → review → validated → graphed
 *                      ↘ failed →（重试）extracting
 * review →（退回）pending；validated →（退回）review；graphed →（重抽）pending
 */
export const ETL_STATES = [
  { key: "pending", label: "待抽取", color: "#6b7280", desc: "已入队，等待开始抽取" },
  { key: "extracting", label: "抽取中", color: "#1565c0", desc: "LLM 正在解析文档" },
  { key: "failed", label: "抽取失败", color: "#c62828", desc: "超时 / 版式 / 字段异常" },
  { key: "review", label: "待校验", color: "#f57f17", desc: "抽取完成，等待人工确认" },
  { key: "validated", label: "待入图", color: "#00796b", desc: "校验通过，等待建图" },
  { key: "graphed", label: "已完成", color: "#2e7d32", desc: "已入知识图谱" },
  { key: "ignored", label: "已忽略", color: "#9ca3af", desc: "不参与处理流程" },
];

export const ETL_STATE_MAP = Object.fromEntries(ETL_STATES.map((s) => [s.key, s]));

export const ALL_KIND_META = {
  lit: { label: "文献", cls: "badge-teal" },
  case: { label: "病案", cls: "badge-warn" },
};

const ERROR_POOL = {
  lit: [
    { code: "REQUIRED_MISSING", field: "lit_7", message: "必填字段「DOR诊断标准」缺失" },
    { code: "ENUM_MISMATCH", field: "lit_15", message: "证型存在同义候选（肾虚 / 肾虚证），需人工归一" },
    { code: "UNIT_UNKNOWN", field: "lit_33", message: "AMH 单位无法识别（缺单位）" },
    { code: "LOW_CONFIDENCE", field: "lit_19", message: "字段置信度低于阈值 0.60" },
  ],
  case: [
    { code: "REQUIRED_MISSING", field: "case_3", message: "必填字段「不孕年限」缺失" },
    { code: "ENUM_MISMATCH", field: "case_23", message: "证型存在同义候选（肾虚 / 肾虚证），需人工归一" },
    { code: "UNIT_UNKNOWN", field: "case_10", message: "AMH 单位无法识别（缺单位）" },
    { code: "LOW_CONFIDENCE", field: "case_26", message: "字段置信度低于阈值 0.60" },
  ],
};

function buildDoc(record, index) {
  const kind = record.id.startsWith("LIT") ? "lit" : "case";
  const title = kind === "lit" ? record.values.lit_1 : `病案 ${record.id}`;
  return {
    id: record.id,
    name: title || record.id,
    kind,
    state: "pending",
    confidence: Number(record.confidence ?? 0.9),
    values: { ...record.values },
    errors: [],
    version: 1,
    uploadedAt: record.updated_at || "2025-03-18 10:00",
    operator: "系统",
    history: [{ at: "2025-03-18 10:00", action: "上传", by: "data@tcm" }],
  };
}

const baseDocs = [...LIT_RECORDS, ...CASE_RECORDS].map(buildDoc);

// 便于演示：按区段分配状态（40 份文档）
const STATE_PLAN = [
  ...Array(8).fill("pending"),
  ...Array(3).fill("extracting"),
  ...Array(5).fill("failed"),
  ...Array(16).fill("review"),
  ...Array(6).fill("graphed"),
  ...Array(2).fill("ignored"),
];

baseDocs.forEach((doc, i) => {
  const state = STATE_PLAN[i] || "pending";
  doc.state = state;
  const pool = ERROR_POOL[doc.kind] || ERROR_POOL.lit;
  if (state === "failed") {
    doc.errors = [pool[i % pool.length]];
  } else if (state === "review") {
    doc.errors = [pool[(i + 1) % pool.length]];
    if (i % 3 === 0) doc.errors.push(pool[(i + 2) % pool.length]);
  } else if (state === "validated" || state === "graphed") {
    doc.errors = [];
  } else {
    doc.errors = [];
  }
});

const docs = reactive(baseDocs);

/* 跨页面/刷新保留状态（原型演示） */
const STATE_KEY = "tcm-dor-etl-doc-states-v1";
try {
  const saved = JSON.parse(localStorage.getItem(STATE_KEY) || "{}");
  for (const d of docs) {
    if (saved[d.id]) d.state = saved[d.id];
  }
} catch {
  /* ignore */
}
function persistStates() {
  try {
    const map = {};
    for (const d of docs) map[d.id] = d.state;
    localStorage.setItem(STATE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export const etlStore = {
  docs,
  counts: computed(() => {
    const out = {};
    for (const s of ETL_STATES) out[s.key] = 0;
    for (const d of docs) out[d.state] = (out[d.state] || 0) + 1;
    return out;
  }),
  byState(state) {
    return docs.filter((d) => d.state === state);
  },
  get(id) {
    return docs.find((d) => d.id === id) || null;
  },
  setState(ids, state, actionLabel) {
    const set = new Set(ids);
    for (const d of docs) {
      if (!set.has(d.id)) continue;
      d.state = state;
      d.history.push({
        at: new Date().toISOString().slice(0, 16).replace("T", " "),
        action: actionLabel,
        by: "demo_admin",
      });
    }
    persistStates();
  },
  startExtraction(ids) {
    this.setState(ids, "extracting", "开始抽取");
  },
  retry(ids) {
    this.setState(ids, "extracting", "重试抽取");
  },
  ignore(ids) {
    this.setState(ids, "ignored", "忽略");
  },
  approve(ids) {
    this.setState(ids, "validated", "校验通过");
  },
  reject(ids) {
    this.setState(ids, "pending", "退回重抽");
  },
  buildGraph(ids) {
    this.setState(ids, "graphed", "执行入图");
  },
  backToReview(ids) {
    this.setState(ids, "review", "退回校验");
  },
  reextract(ids) {
    this.setState(ids, "pending", "重新抽取");
  },
  moveOut(ids) {
    this.setState(ids, "uploaded", "移出队列");
  },
};
