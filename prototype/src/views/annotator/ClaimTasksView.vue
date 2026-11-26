<template>
  <div class="admin-page">
    <div class="stat-row">
      <div class="stat-card">
        <span class="stat-label">可领取文献</span>
        <strong class="stat-value">{{ avail.lit }}</strong>
        <span class="stat-hint">条</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">可领取病案</span>
        <strong class="stat-value">{{ avail.case }}</strong>
        <span class="stat-hint">条</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">我的进行中任务</span>
        <strong class="stat-value">{{ myActive.length }}</strong>
        <span class="stat-hint">个</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">返工任务</span>
        <strong class="stat-value warn">{{ myRework.length }}</strong>
        <span class="stat-hint">个</span>
      </div>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h2>可领取任务</h2>
        <span class="panel-hint">每批最多 {{ BATCH_SIZE }} 条 · 截止 7 天</span>
      </div>

      <div v-if="batches.length === 0" class="empty-block">
        暂无可领取任务，请等待管理员下发或稍后再试。
      </div>
      <div v-else class="task-grid">
        <article v-for="task in batches" :key="task.id" class="claim-card">
          <div class="claim-top">
            <span class="mono claim-id">{{ task.id }}</span>
            <span class="badge" :class="task.kind === 'lit' ? 'badge-teal' : 'badge-warn'">
              {{ task.kind === "lit" ? "文献" : "病案" }}
            </span>
          </div>
          <div class="claim-meta">
            <span>{{ task.count }} 条</span>
            <span>来源：DOR 抽取复核</span>
          </div>
          <p class="claim-deadline">建议截止 {{ task.deadline }}</p>
          <button class="btn-primary claim-btn" type="button" @click="claim(task)">领取任务</button>
        </article>
      </div>
    </section>

    <section class="panel my-tasks-panel">
      <div class="panel-head">
        <h2>我的任务</h2>
        <span class="panel-hint">含进行中与返工</span>
      </div>
      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr><th>任务号</th><th>类型</th><th>条目</th><th>状态</th><th>领取时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in myTasks" :key="t.id">
              <td class="mono">{{ t.id }}</td>
              <td>{{ t.kind === "lit" ? "文献" : "病案" }}</td>
              <td>{{ t.docIds.length }}</td>
              <td><span class="badge" :class="statusCls(t.status)">{{ statusLabel(t.status) }}</span></td>
              <td class="mono">{{ t.createdAt }}</td>
              <td><button class="btn-sm teal" type="button" @click="goWorkbench">去标注</button></td>
            </tr>
            <tr v-if="myTasks.length === 0">
              <td colspan="6" class="empty-row">暂无已领取任务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <transition name="toast"><div v-if="toast.visible" class="toast">{{ toast.message }}</div></transition>
  </div>
</template>

<script setup>
import { computed, reactive } from "vue";
import { useRouter } from "vue-router";
import { annotationStore } from "../../stores/annotation";

const router = useRouter();
const BATCH_SIZE = 5;

const toast = reactive({ visible: false, message: "" });
let timer = null;
function showToast(msg) {
  toast.message = msg;
  toast.visible = true;
  clearTimeout(timer);
  timer = setTimeout(() => (toast.visible = false), 2600);
}

const available = computed(() => annotationStore.availableDocs());
const avail = computed(() => ({
  lit: available.value.filter((d) => d.kind === "lit").length,
  case: available.value.filter((d) => d.kind === "case").length,
}));

const batches = computed(() => {
  const out = [];
  for (const kind of ["lit", "case"]) {
    const docs = available.value.filter((d) => d.kind === kind);
    for (let i = 0; i < docs.length; i += BATCH_SIZE) {
      const chunk = docs.slice(i, i + BATCH_SIZE);
      out.push({
        id: `TASK-${kind === "lit" ? "LIT" : "CASE"}-${String(out.length + 1).padStart(3, "0")}`,
        kind,
        count: chunk.length,
        docIds: chunk.map((d) => d.id),
        deadline: "2026-12-02",
      });
    }
  }
  return out;
});

const myTasks = computed(() =>
  annotationStore.tasks.filter((t) => ["assigned", "drafting", "rework"].includes(t.status)),
);
const myActive = computed(() => myTasks.value.filter((t) => t.status !== "rework"));
const myRework = computed(() => myTasks.value.filter((t) => t.status === "rework"));

function claim(task) {
  const created = annotationStore.assign(task.docIds, "demo_annotator");
  if (created) showToast(`已领取 ${created.id}（${created.docIds.length} 条）`);
}

function statusLabel(status) {
  return (
    { assigned: "待标注", drafting: "标注中", rework: "返工中", submitted: "待复核", approved: "已通过" }[status] ||
    status
  );
}
function statusCls(status) {
  if (status === "rework") return "badge-danger";
  if (status === "drafting") return "badge-teal";
  if (status === "submitted") return "badge-warn";
  return "badge-muted";
}
function goWorkbench() {
  router.push("/annotate/workbench");
}
</script>

<style scoped>
.stat-row { flex-shrink: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.stat-card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 2px; }
.stat-label { font-size: 12px; color: var(--ink-400); }
.stat-value { font-size: 22px; color: var(--teal-dark); }
.stat-value.warn { color: #b06a00; }
.stat-hint { font-size: 11px; color: var(--ink-400); }

.admin-page { height: 100%; display: flex; flex-direction: column; }
.panel { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
.my-tasks-panel { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; margin-bottom: 0; }
.my-tasks-panel .table-wrap { flex: 1 1 auto; min-height: 0; overflow: auto; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 12px; }
.panel-head h2 { margin: 0; font-size: 14px; }
.panel-hint { font-size: 11px; color: var(--ink-400); }

.task-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.claim-card { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.claim-top { display: flex; align-items: center; justify-content: space-between; }
.claim-id { font-size: 11px; color: var(--ink-400); }
.claim-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--ink-500); }
.claim-deadline { margin: 0; font-size: 11px; color: var(--ink-400); }
.claim-btn { margin-top: 4px; padding: 7px 0; }

.empty-block { padding: 36px 12px; text-align: center; color: var(--ink-400); font-size: 13px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.toast { position: fixed; top: 24px; right: 24px; z-index: 200; background: var(--teal); color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 13px; box-shadow: 0 6px 18px rgba(0,0,0,.18); }
.toast-enter-active, .toast-leave-active { transition: opacity .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; }
</style>
