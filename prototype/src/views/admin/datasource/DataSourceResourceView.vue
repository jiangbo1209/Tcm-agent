<template>
  <div class="resource-page">
    <div class="toolbar">
      <select
        v-model="batchAction"
        class="filter-select batch-select"
        :disabled="selectedIds.size === 0"
        :title="selectedIds.size === 0 ? '请先勾选资源' : '批量操作'"
        @change="onBatchAction"
      >
        <option value="" disabled hidden>{{ selectedIds.size > 0 ? `批量操作（${selectedIds.size}）` : "批量操作" }}</option>
        <option value="delete">删除</option>
        <option value="settings">设置</option>
        <option value="extract">抽取</option>
        <option value="cancel">取消抽取</option>
      </select>
      <select v-model="stateFilter" class="filter-select">
        <option value="">全部状态</option>
        <option v-for="s in STATE_OPTIONS" :key="s.key" :value="s.key">{{ s.label }}</option>
      </select>
      <select v-model="kindFilter" class="filter-select">
        <option value="">全部类型</option>
        <option value="lit">文献</option>
        <option value="case">病案</option>
      </select>
      <input v-model="searchQuery" class="filter-input" placeholder="搜索文档 / 编号..." />
      <button v-if="searchQuery" class="btn-clear" type="button" @click="searchQuery = ''">清除</button>
      <div class="toolbar-actions">
        <button class="btn-primary upload-btn" type="button" @click="uploadModalOpen = true">上传文件</button>
        <button class="btn-sm upload-btn" type="button" @click="queueModalOpen = true">
          上传队列（{{ queue.length }}/{{ MAX_QUEUE }}）
        </button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="pool-table">
        <thead>
          <tr>
            <th class="col-check">
              <input type="checkbox" class="row-check" :checked="allSelected" :disabled="paged.length === 0" @change="toggleAll" />
            </th>
            <th>文档</th>
            <th class="col-type">类型</th>
            <th class="col-state">状态</th>
            <th class="col-conf">置信度</th>
            <th class="col-reason">失败原因</th>
            <th class="col-time">上传时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in paged" :key="doc.id" :class="{ 'row-selected': selectedIds.has(doc.id) }">
            <td class="col-check">
              <input type="checkbox" class="row-check" :checked="selectedIds.has(doc.id)" @change="toggleOne(doc.id)" />
            </td>
            <td>
              <div class="doc-cell">
                <span class="doc-id">{{ doc.id }}</span>
                <span class="doc-name" :title="doc.name">{{ doc.name }}</span>
              </div>
            </td>
            <td>
              <select v-model="doc.kind" class="filter-select row-select" @change="onKindChange(doc)">
                <option value="lit">文献</option>
                <option value="case">病案</option>
              </select>
            </td>
            <td><span class="badge" :class="stateCls(doc.state)">{{ stateLabel(doc.state) }}</span></td>
            <td><span class="conf" :class="confCls(doc.confidence)">{{ doc.confidence ? Math.round(doc.confidence * 100) + "%" : "—" }}</span></td>
            <td class="cell-reason">{{ doc.errors?.[0]?.message || "—" }}</td>
            <td class="muted">{{ doc.uploadedAt }}</td>
            <td class="col-actions">
              <button
                v-if="['pending', 'failed'].includes(doc.state)"
                class="btn-sm teal"
                type="button"
                @click="extractDocs([doc.id])"
              >抽取</button>
              <button
                v-if="doc.state === 'extracting'"
                class="btn-sm"
                type="button"
                @click="cancelDocs([doc.id])"
              >取消抽取</button>
              <button class="btn-sm" type="button" @click="openDetail(doc)">详情</button>
              <button class="btn-sm danger" type="button" @click="askDelete([doc.id])">删除</button>
            </td>
          </tr>
          <tr v-if="paged.length === 0">
            <td colspan="8" class="empty-row">暂无资源</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pager-bar">
      <div class="page-size">
        <span>每页</span>
        <select v-model.number="pageSize" class="filter-select">
          <option v-for="n in PAGE_SIZES" :key="n" :value="n">{{ n }}</option>
        </select>
        <span>条</span>
      </div>
      <span class="page-info">第 {{ page }} / {{ pageCount }} 页 · 共 {{ filtered.length }} 条</span>
      <div class="pager-btns">
        <button class="btn-sm" :disabled="page <= 1" @click="page--">上一页</button>
        <button class="btn-sm" :disabled="page >= pageCount" @click="page++">下一页</button>
      </div>
    </div>

    <!-- 上传文件 -->
    <div v-if="uploadModalOpen" class="modal-mask" @click.self="uploadModalOpen = false">
      <div class="modal-box">
        <div class="modal-head">
          <h3>上传文件</h3>
          <div class="head-actions">
            <button class="btn-ghost" type="button" @click="uploadModalOpen = false">取消</button>
            <button class="btn-primary" type="button" :disabled="!hasPending || uploading" @click="startUpload">
              {{ uploading ? "上传中…" : "开始上传" }}
            </button>
          </div>
        </div>
        <div
          class="dropzone"
          :class="{ over: dragOver }"
          @click="pickFiles"
          @dragover.prevent="dragOver = true"
          @dragenter.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <div class="dz-icon">⇪</div>
          <p class="dz-title">拖拽文件到此处</p>
          <p class="dz-sub">或</p>
          <button class="btn-sm" type="button" @click.stop="pickFiles">选择文件</button>
          <p class="dz-tip">支持 .pdf / .doc / .docx / .txt，队列还可添加 {{ remainingSlots }} 个</p>
          <input ref="fileInput" type="file" multiple accept=".pdf,.doc,.docx,.txt" class="file-input" @change="onPick" />
        </div>
        <div class="queue-mini">当前队列 {{ queue.length }} / {{ MAX_QUEUE }}</div>
        <div class="modal-extra">
          <button class="btn-ghost" type="button" @click="uploadModalOpen = false; queueModalOpen = true">查看上传队列</button>
        </div>
      </div>
    </div>

    <!-- 上传队列 -->
    <div v-if="queueModalOpen" class="modal-mask" @click.self="queueModalOpen = false">
      <div class="modal-box">
        <div class="modal-head">
          <h3>上传队列（{{ queue.length }}/{{ MAX_QUEUE }}）</h3>
          <button class="modal-close" type="button" @click="queueModalOpen = false">×</button>
        </div>
        <div v-if="queue.length" class="table-wrap">
          <table class="pool-table">
            <thead><tr><th>文件名</th><th>大小</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in queue" :key="item.id">
                <td class="doc-name">{{ item.name }}</td>
                <td>{{ fmtSize(item.sizeBytes) }}</td>
                <td>
                  <select v-model="item.type" class="filter-select row-select" :disabled="item.status === 'uploading'">
                    <option value="lit">文献</option>
                    <option value="case">病案</option>
                  </select>
                </td>
                <td><span class="badge" :class="qStatus(item.status).cls">{{ qStatus(item.status).label }}</span></td>
                <td><button class="btn-sm danger" type="button" @click="removeQueue(item)">移除</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-box">队列为空，请先上传文件</div>
        <div class="modal-extra between">
          <button class="btn-ghost" type="button" :disabled="!queue.length" @click="queue = []">清空队列</button>
          <button class="btn-primary" type="button" :disabled="!hasPending || uploading" @click="startUpload">
            {{ uploading ? "上传中…" : "开始上传" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 批量设置类型 -->
    <div v-if="settingsOpen" class="modal-mask" @click.self="settingsOpen = false">
      <div class="modal-box small">
        <div class="modal-head">
          <h3>批量设置类型</h3>
          <button class="modal-close" type="button" @click="settingsOpen = false">×</button>
        </div>
        <label class="settings-field">
          <span>设置为</span>
          <select v-model="settingsType" class="filter-select">
            <option value="lit">文献</option>
            <option value="case">病案</option>
          </select>
        </label>
        <p class="settings-hint">将对已选 {{ selectedIds.size }} 条资源生效</p>
        <div class="modal-extra">
          <button class="btn-ghost" type="button" @click="settingsOpen = false">取消</button>
          <button class="btn-primary" type="button" @click="applySettings">确定</button>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="pendingDeleteIds.length" class="modal-mask" @click.self="pendingDeleteIds = []">
      <div class="modal-box small">
        <div class="modal-head">
          <h3>删除资源</h3>
          <button class="modal-close" type="button" @click="pendingDeleteIds = []">×</button>
        </div>
        <p class="settings-hint">确定删除选中的 {{ pendingDeleteIds.length }} 条资源吗？此操作不可撤销。</p>
        <div class="modal-extra">
          <button class="btn-ghost" type="button" @click="pendingDeleteIds = []">取消</button>
          <button class="btn-primary danger-solid" type="button" @click="confirmDelete">删除</button>
        </div>
      </div>
    </div>

    <transition name="toast"><div v-if="toast.visible" class="toast">{{ toast.message }}</div></transition>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { etlStore, ETL_STATE_MAP } from "../../../stores/etl";

const router = useRouter();
const MAX_QUEUE = 10;
const PAGE_SIZES = [10, 20, 50, 100];
const STATE_OPTIONS = [
  { key: "pending", label: "待抽取" },
  { key: "extracting", label: "抽取中" },
  { key: "failed", label: "抽取失败" },
  { key: "graphed", label: "已完成" },
];

const docs = computed(() => etlStore.docs);
const stateFilter = ref("");
const kindFilter = ref("");
const searchQuery = ref("");
const page = ref(1);
const pageSize = ref(10);
const selectedIds = ref(new Set());
const batchAction = ref("");

const toast = reactive({ visible: false, message: "" });
let timer = null;
function showToast(msg) {
  toast.message = msg;
  toast.visible = true;
  clearTimeout(timer);
  timer = setTimeout(() => (toast.visible = false), 2600);
}

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return docs.value.filter((d) => {
    if (!["pending", "extracting", "failed", "graphed"].includes(d.state)) return false;
    if (stateFilter.value && d.state !== stateFilter.value) return false;
    if (kindFilter.value && d.kind !== kindFilter.value) return false;
    if (q && !`${d.id} ${d.name}`.toLowerCase().includes(q)) return false;
    return true;
  });
});

const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)));
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filtered.value.slice(start, start + pageSize.value);
});
const allSelected = computed(() => paged.value.length > 0 && paged.value.every((d) => selectedIds.value.has(d.id)));

watch([stateFilter, kindFilter, searchQuery, pageSize], () => {
  page.value = 1;
  selectedIds.value = new Set();
  batchAction.value = "";
});
watch(pageCount, (n) => { if (page.value > n) page.value = n; });

const ELIGIBLE_STATES = ["pending", "extracting", "failed", "graphed"];
const eligibleDocs = computed(() => docs.value.filter((d) => ELIGIBLE_STATES.includes(d.state)));
const eligibleCount = computed(() => eligibleDocs.value.length);
function countKind(kind) {
  return eligibleDocs.value.filter((d) => d.kind === kind).length;
}
function stateLabel(s) { return ETL_STATE_MAP[s]?.label || s; }
function stateCls(s) {
  if (s === "graphed") return "badge-ok";
  if (s === "failed") return "badge-danger";
  if (s === "extracting") return "badge-warn";
  return "badge-muted";
}
function confCls(v) {
  if (v >= 0.85) return "conf-high";
  if (v >= 0.65) return "conf-mid";
  return "conf-low";
}

function toggleOne(id) {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectedIds.value = next;
}
function toggleAll() {
  const next = new Set(selectedIds.value);
  const all = allSelected.value;
  for (const d of paged.value) {
    if (all) next.delete(d.id);
    else next.add(d.id);
  }
  selectedIds.value = next;
}

function extractDocs(ids) {
  etlStore.setState(ids, "extracting", "开始抽取");
  showToast(`已开始抽取 ${ids.length} 条`);
}
function cancelDocs(ids) {
  etlStore.setState(ids, "pending", "取消抽取");
  showToast(`已取消抽取 ${ids.length} 条`);
}
function onKindChange(doc) {
  showToast(`已将 ${doc.id} 设置为${doc.kind === "lit" ? "文献" : "病案"}`);
}

function onBatchAction() {
  const ids = [...selectedIds.value];
  if (!ids.length) { batchAction.value = ""; return; }
  if (batchAction.value === "delete") {
    askDelete(ids);
  } else if (batchAction.value === "settings") {
    settingsOpen.value = true;
  } else if (batchAction.value === "extract") {
    const targets = ids.filter((id) => {
      const d = etlStore.get(id);
      return d && ["pending", "failed"].includes(d.state);
    });
    if (targets.length) extractDocs(targets);
    selectedIds.value = new Set();
  } else if (batchAction.value === "cancel") {
    const targets = ids.filter((id) => etlStore.get(id)?.state === "extracting");
    if (targets.length) cancelDocs(targets);
    selectedIds.value = new Set();
  }
  batchAction.value = "";
}

const pendingDeleteIds = ref([]);
function askDelete(ids) { pendingDeleteIds.value = ids; }
function confirmDelete() {
  etlStore.removeDocs(pendingDeleteIds.value);
  showToast(`已删除 ${pendingDeleteIds.value.length} 条资源`);
  pendingDeleteIds.value = [];
  selectedIds.value = new Set();
}

const settingsOpen = ref(false);
const settingsType = ref("lit");
function applySettings() {
  etlStore.setKind([...selectedIds.value], settingsType.value);
  showToast(`已设置 ${selectedIds.value.size} 条资源为${settingsType.value === "lit" ? "文献" : "病案"}`);
  settingsOpen.value = false;
  selectedIds.value = new Set();
}

function openDetail(doc) {
  const kind = doc.kind === "lit" ? "literature" : "case";
  router.push(`/admin/data?kind=${kind}&record=${doc.id}`);
}

/* ── 上传 ── */
const uploadModalOpen = ref(false);
const queueModalOpen = ref(false);
const queue = ref([]);
const uploading = ref(false);
const dragOver = ref(false);
const fileInput = ref(null);
let queueSeed = 0;
const remainingSlots = computed(() => Math.max(0, MAX_QUEUE - queue.value.length));
const hasPending = computed(() => queue.value.some((q) => q.status === "pending"));
function qStatus(s) {
  return {
    pending: { label: "待上传", cls: "badge-muted" },
    uploading: { label: "上传中", cls: "badge-warn" },
    done: { label: "已完成", cls: "badge-ok" },
    failed: { label: "失败", cls: "badge-danger" },
  }[s] || { label: s, cls: "badge-muted" };
}
function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
function pickFiles() { fileInput.value?.click(); }
function addFiles(files) {
  const list = Array.from(files || []);
  const slots = remainingSlots.value;
  if (!slots) { showToast("上传队列最多 10 个文件"); return; }
  const accepted = list.slice(0, slots);
  for (const f of accepted) {
    queueSeed += 1;
    queue.value.push({ id: `q-${queueSeed}`, name: f.name, sizeBytes: f.size || 1024, type: "lit", status: "pending" });
  }
  if (list.length > slots) showToast("上传队列最多 10 个文件");
  else if (accepted.length) showToast(`已加入上传队列（${accepted.length} 个）`);
}
function onPick(e) { addFiles(e.target.files); e.target.value = ""; }
function onDrop(e) { dragOver.value = false; addFiles(e.dataTransfer.files); }
function removeQueue(item) { queue.value = queue.value.filter((q) => q.id !== item.id); }
async function startUpload() {
  if (uploading.value) return;
  const pending = queue.value.filter((q) => q.status === "pending");
  if (!pending.length) return;
  uploading.value = true;
  for (const item of queue.value) {
    if (item.status !== "pending") continue;
    item.status = "uploading";
    await new Promise((r) => setTimeout(r, 120));
    item.status = "done";
  }
  etlStore.addDocs(pending.map((q) => ({ name: q.name, kind: q.type })));
  uploading.value = false;
  queue.value = [];
  uploadModalOpen.value = false;
  queueModalOpen.value = false;
  showToast(`${pending.length} 个文件上传完成，已进入待抽取`);
}
</script>

<style scoped>
.resource-page { width: 100%; padding: 0 0 40px; }
.page-head { display: flex; align-items: center; justify-content: flex-end; margin-bottom: 12px; }
.page-head h1 { margin: 0; font-size: 22px; font-weight: 600; color: var(--ink-900); }
.head-actions { display: flex; align-items: center; gap: 8px; }

.toolbar-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.upload-btn { height: 33px; padding: 0 16px; display: inline-flex; align-items: center; justify-content: center; }

.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.batch-select { width: 132px; font-variant-numeric: tabular-nums; cursor: pointer; }
.batch-select:disabled { background: #f3f4f4; border-color: #e0e0e0; color: #9ca3af; cursor: not-allowed; }
.btn-clear { padding: 7px 12px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; color: var(--ink-500); font-size: 12px; cursor: pointer; }

.col-check { width: 40px; text-align: center; }
.row-check { width: 15px; height: 15px; accent-color: var(--teal); cursor: pointer; }
.row-selected td { background: #f0f7f6; }
.col-type { width: 90px; }
.col-state { width: 90px; }
.col-conf { width: 80px; }
.col-reason { max-width: 220px; font-size: 12px; color: var(--danger); }
.col-time { width: 140px; font-size: 12px; color: var(--ink-400); }
.col-actions { width: 240px; white-space: nowrap; }
.doc-cell { display: flex; flex-direction: column; gap: 2px; min-width: 240px; }
.doc-id { font-size: 11px; color: var(--ink-400); font-family: ui-monospace, Consolas, monospace; }
.doc-name { font-size: 13px; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted { color: var(--ink-400); font-size: 12px; }
.row-select { padding: 3px 6px; font-size: 12px; }
.conf { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.conf-high { background: #e8f5e9; color: var(--ok); }
.conf-mid { background: #fff8e1; color: var(--warn); }
.conf-low { background: #ffebee; color: var(--danger); }

.pager-bar { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
.page-size { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-500); }
.page-info { font-size: 12px; color: var(--ink-400); margin-left: auto; }
.pager-btns { display: flex; gap: 8px; }
.pager-btns .btn-sm:disabled { opacity: 0.45; cursor: not-allowed; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.42); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 24px; }
.modal-box { width: 720px; max-width: 96vw; max-height: 88vh; overflow-y: auto; background: #fff; border-radius: 12px; padding: 16px 18px; box-shadow: 0 24px 60px rgba(0,0,0,.22); }
.modal-box.small { width: 420px; }
.modal-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.modal-head h3 { margin: 0; font-size: 15px; }
.modal-close { border: none; background: transparent; font-size: 20px; color: var(--ink-400); cursor: pointer; }
.modal-extra { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.modal-extra.between { justify-content: space-between; }
.btn-ghost { padding: 7px 14px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; color: var(--ink-500); font-size: 12px; cursor: pointer; }
.btn-primary { padding: 7px 16px; border: none; border-radius: 6px; background: var(--teal); color: #fff; font-size: 13px; cursor: pointer; }
.btn-primary:disabled { opacity: .5; cursor: default; }
.btn-primary.danger-solid { background: #c62828; }
.btn-sm.danger { color: #c62828; border-color: #ef9a9a; }
.btn-sm.danger:hover { background: #ffebee; }

.dropzone { border: 2px dashed #cfdedd; border-radius: 12px; padding: 28px; text-align: center; cursor: pointer; background: #fbfdfc; }
.dropzone.over { border-color: var(--teal); background: #f2faf8; }
.dz-icon { font-size: 26px; color: var(--teal); }
.dz-title { margin: 8px 0 2px; font-size: 14px; font-weight: 600; }
.dz-sub { margin: 0 0 8px; font-size: 11px; color: var(--ink-400); }
.dz-tip { margin: 10px 0 0; font-size: 11px; color: var(--ink-400); }
.file-input { display: none; }
.queue-mini { margin-top: 10px; font-size: 12px; color: var(--ink-500); }

.settings-field { display: flex; align-items: center; gap: 10px; font-size: 13px; margin: 8px 0; }
.settings-hint { font-size: 12px; color: var(--ink-400); margin: 8px 0 0; }
.empty-box { padding: 32px; text-align: center; color: var(--ink-400); font-size: 13px; }
.toast { position: fixed; top: 24px; right: 24px; z-index: 200; background: var(--teal); color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 13px; }
.toast-enter-active, .toast-leave-active { transition: opacity .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; }
</style>
