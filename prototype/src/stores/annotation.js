import { reactive } from "vue";
import { etlStore } from "./etl";

/**
 * 统一标注任务模型（原型）：
 * ETL review 文档 → 管理员建任务下发 → 标注员标注 → 提交 → 复核
 * 通过 → 文档 graphed；驳回 → 任务进入返工箱。
 */

const now = () => new Date().toISOString().slice(0, 16).replace("T", " ");

let seq = 9;

const STORAGE_KEY = "tcm-dor-annotation-tasks-v2";

const initialTasks = [
  {
    id: "AT-2026-001",
    kind: "lit",
    assignee: "demo_annotator",
    status: "rework",
    docIds: ["LIT-017"],
    createdAt: "2026-11-23 09:20",
    rejectedAt: "2026-11-24 10:12",
    deadline: "2026-11-30",
  },
  {
    id: "AT-2026-002",
    kind: "lit",
    assignee: "demo_annotator",
    status: "assigned",
    docIds: ["LIT-020"],
    createdAt: "2026-11-24 14:05",
    rejectedAt: "",
    deadline: "2026-12-01",
  },
  {
    id: "AT-2026-003",
    kind: "case",
    assignee: "demo_annotator",
    status: "assigned",
    docIds: ["CASE-001", "CASE-002", "CASE-003"],
    createdAt: "2026-11-24 15:30",
    rejectedAt: "",
    deadline: "2026-12-01",
  },
  {
    id: "AT-2026-004",
    kind: "case",
    assignee: "demo_annotator",
    status: "submitted",
    docIds: ["CASE-004", "CASE-005", "CASE-006"],
    createdAt: "2026-11-23 11:00",
    rejectedAt: "",
    deadline: "2026-11-29",
  },
  {
    id: "AT-2026-005",
    kind: "lit",
    assignee: "demo_annotator",
    status: "assigned",
    docIds: ["LIT-018", "LIT-019"],
    createdAt: "2026-11-24 16:10",
    rejectedAt: "",
    deadline: "2026-12-03",
  },
  {
    id: "AT-2026-006",
    kind: "case",
    assignee: "demo_annotator",
    status: "assigned",
    docIds: ["CASE-007", "CASE-008"],
    createdAt: "2026-11-24 16:25",
    rejectedAt: "",
    deadline: "2026-12-03",
  },
  {
    id: "AT-2026-007",
    kind: "case",
    assignee: "demo_annotator",
    status: "drafting",
    docIds: ["CASE-009", "CASE-010", "CASE-011"],
    createdAt: "2026-11-24 17:00",
    rejectedAt: "",
    deadline: "2026-12-04",
  },
  {
    id: "AT-2026-008",
    kind: "case",
    assignee: "demo_annotator",
    status: "assigned",
    docIds: ["CASE-012"],
    createdAt: "2026-11-25 09:15",
    rejectedAt: "",
    deadline: "2026-12-05",
  },
];

let restored = null;
try {
  restored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
} catch {
  restored = null;
}

const tasks = reactive(Array.isArray(restored) && restored.length ? restored : initialTasks);

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  } catch {
    /* ignore */
  }
}

const ACTIVE = ["assigned", "drafting", "rework", "submitted"];

export const annotationStore = {
  tasks,

  /** review 且未被任何活跃任务占用的文档 */
  availableDocs() {
    const busy = new Set(
      tasks.filter((t) => ACTIVE.includes(t.status)).flatMap((t) => t.docIds),
    );
    return etlStore.docs.filter((d) => d.state === "review" && !busy.has(d.id));
  },

  /** 某类已下发给标注员的文档（assigned/drafting） */
  assignedDocs(kind) {
    const ids = new Set(
      tasks
        .filter((t) => t.kind === kind && ["assigned", "drafting"].includes(t.status))
        .flatMap((t) => t.docIds),
    );
    return etlStore.docs.filter((d) => ids.has(d.id) && d.state === "review");
  },

  tasksOfDoc(docId) {
    return tasks.filter((t) => t.docIds.includes(docId));
  },

  assign(docIds, assignee = "demo_annotator") {
    if (!docIds.length) return null;
    const docs = docIds.map((id) => etlStore.get(id)).filter(Boolean);
    if (!docs.length) return null;
    const kind = docs[0].kind;
    const task = {
      id: `AT-2026-${String(seq++).padStart(3, "0")}`,
      kind,
      assignee,
      status: "assigned",
      docIds: docs.filter((d) => d.kind === kind).map((d) => d.id),
      createdAt: now(),
      rejectedAt: "",
      deadline: "2026-12-05",
    };
    tasks.unshift(task);
    persist();
    return task;
  },

  /** 标注员提交：把包含这些文档的 assigned/drafting/rework 任务标记为 submitted */
  submitByDocs(docIds) {
    const set = new Set(docIds);
    let changed = 0;
    for (const t of tasks) {
      if (!["assigned", "drafting", "rework"].includes(t.status)) continue;
      if (t.docIds.some((id) => set.has(id))) {
        t.status = "submitted";
        changed += 1;
      }
    }
    persist();
    return changed;
  },

  markDrafting(docIds) {
    const set = new Set(docIds);
    for (const t of tasks) {
      if (t.status === "assigned" && t.docIds.some((id) => set.has(id))) {
        t.status = "drafting";
      }
    }
    persist();
  },

  approve(taskId) {
    const t = tasks.find((x) => x.id === taskId);
    if (!t) return;
    etlStore.setState(t.docIds, "graphed", "标注复核通过并入图");
    t.status = "approved";
    persist();
  },

  reject(taskId) {
    const t = tasks.find((x) => x.id === taskId);
    if (!t) return;
    t.status = "rework";
    t.rejectedAt = now();
    persist();
  },

  resubmit(taskId) {
    const t = tasks.find((x) => x.id === taskId);
    if (!t) return;
    t.status = "submitted";
    persist();
  },

  get reworkTasks() {
    return tasks.filter((t) => t.status === "rework");
  },

  get reviewTasks() {
    return tasks.filter((t) => t.status === "submitted");
  },

  get pendingAssignCount() {
    return this.availableDocs().length;
  },
};
