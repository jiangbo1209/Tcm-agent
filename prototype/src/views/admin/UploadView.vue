<template>
  <div class="admin-page">
    <div class="admin-header">
      <div>
        <h1>数据上传</h1>
        <p class="header-sub">手动上传 · 队列上限 10 · 支持脚本批量导入</p>
      </div>
    </div>

    <!-- 上传区 -->
    <section class="panel upload-panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">上传文件</h2>
          <p class="panel-desc">支持 PDF / Word / TXT，可拖拽文件或点击选择，加入待上传队列</p>
        </div>
        <div class="queue-meter">
          <span class="queue-count">队列 {{ queue.length }} / {{ MAX_QUEUE }}</span>
          <div class="meter">
            <div class="meter-fill" :class="{ 'meter-full': queue.length >= MAX_QUEUE }" :style="{ width: queuePct + '%' }"></div>
          </div>
        </div>
      </div>

      <div
        class="dropzone"
        :class="{ 'dropzone-active': dragOver, 'dropzone-full': queue.length >= MAX_QUEUE }"
        @click="triggerPick"
        @dragover.prevent="dragOver = true"
        @dragenter.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
      >
        <div class="dropzone-icon">⇪</div>
        <p class="dropzone-title">拖拽文件到此处</p>
        <p class="dropzone-sub">或</p>
        <button type="button" class="btn-pick" @click.stop="triggerPick">选择文件</button>
        <p class="dropzone-tip">支持 .pdf / .doc / .docx / .txt，单次最多再添加 {{ remainingSlots }} 个</p>
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt"
          class="file-input"
          @change="onPick"
        />
      </div>
    </section>

    <!-- 待上传队列 -->
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">待上传队列</h2>
          <p class="panel-desc">可在上传前调整文件分类（文献 / 病案）</p>
        </div>
        <span class="queue-total">共 {{ queue.length }} 个文件</span>
      </div>

      <div v-if="queue.length" class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th class="col-name">文件名</th>
              <th class="col-size">大小 (KB)</th>
              <th class="col-type">类型</th>
              <th class="col-status">状态</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in queue" :key="item.id">
              <td class="cell-name" :title="item.name">{{ item.name }}</td>
              <td class="cell-size">{{ item.sizeKB }}</td>
              <td>
                <select v-model="item.type" class="filter-select row-select" :disabled="item.status === 'uploading'">
                  <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </td>
              <td>
                <span class="badge" :class="statusMeta(item.status).cls">{{ statusMeta(item.status).label }}</span>
              </td>
              <td>
                <button
                  class="btn-sm btn-remove"
                  :disabled="uploading || item.status === 'uploading'"
                  @click="removeQueueItem(item)"
                >
                  移除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-state">
        <div class="empty-icon">📄</div>
        <p class="empty-title">队列为空</p>
        <p class="empty-desc">从上方上传区选择文件后，将显示在这里</p>
      </div>

      <div class="queue-actions">
        <button class="btn-primary" :disabled="!queue.length || uploading" @click="startUpload">
          {{ uploading ? "上传中…" : "开始上传" }}
        </button>
        <button class="btn-ghost" :disabled="!queue.length || uploading" @click="clearQueue">清空队列</button>
        <span v-if="uploading" class="uploading-hint">正在逐个上传，请稍候…</span>
      </div>
    </section>

    <!-- 已上传文件 -->
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">已上传文件</h2>
          <p class="panel-desc">可调整分类或删除</p>
        </div>
      </div>

      <div class="uploaded-toolbar">
        <select v-model="filterType" class="filter-select">
          <option value="">全部类型</option>
          <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <input v-model="searchQuery" type="text" class="filter-input" placeholder="搜索文件名..." />
        <button v-if="searchQuery" class="btn-reset" @click="searchQuery = ''">清除</button>
        <span class="result-count">共 {{ filteredUploaded.length }} 条</span>
      </div>

      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th class="col-name">文件名</th>
              <th class="col-size">大小</th>
              <th class="col-type">类型</th>
              <th class="col-time">上传时间</th>
              <th class="col-uploader">上传人</th>
              <th class="col-status">状态</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in filteredUploaded" :key="file.id">
              <td class="cell-name" :title="file.name">{{ file.name }}</td>
              <td class="cell-size">{{ file.size }}</td>
              <td>
                <select v-model="file.type" class="filter-select row-select" @change="onUploadedTypeChange(file)">
                  <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </td>
              <td class="cell-time">{{ file.uploadedAt }}</td>
              <td class="cell-uploader">{{ file.uploader }}</td>
              <td>
                <span class="badge" :class="statusMeta(file.status).cls">{{ statusMeta(file.status).label }}</span>
              </td>
              <td>
                <button class="btn-sm btn-remove" @click="deleteUploaded(file)">删除</button>
              </td>
            </tr>
            <tr v-if="filteredUploaded.length === 0">
              <td colspan="7" class="empty-row">暂无匹配的已上传文件</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 批量脚本提示 -->
    <section class="script-card">
      <div class="script-icon">{ }</div>
      <div class="script-body">
        <h3 class="script-title">批量导入脚本</h3>
        <p class="script-desc">
          批量导入脚本：<code class="script-code">python scripts/upload_docs.py --dir ./pdfs --type lit|case --api ...</code>（原型仅展示，不执行）
        </p>
      </div>
    </section>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from "vue";

const MAX_QUEUE = 10;
const TYPE_OPTIONS = [
  { value: "lit", label: "文献" },
  { value: "case", label: "病案" },
];

const STATUS_META = {
  pending: { label: "待上传", cls: "badge-muted" },
  uploading: { label: "上传中", cls: "badge-warn" },
  done: { label: "已完成", cls: "badge-ok" },
  failed: { label: "失败", cls: "badge-danger" },
};

function statusMeta(status) {
  return STATUS_META[status] || { label: "—", cls: "badge-muted" };
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 2800);
}

/* ───────── 待上传队列 ───────── */
const queue = ref([]);
const uploading = ref(false);
const dragOver = ref(false);
const fileInput = ref(null);
let queueSeed = 0;

const queuePct = computed(() => Math.round((queue.value.length / MAX_QUEUE) * 100));
const remainingSlots = computed(() => Math.max(0, MAX_QUEUE - queue.value.length));

function triggerPick() {
  fileInput.value?.click();
}

function addFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;

  const room = MAX_QUEUE - queue.value.length;
  if (room <= 0) {
    showToast("上传队列最多 10 个文件", "error");
    return;
  }

  const accepted = files.slice(0, room);
  accepted.forEach((file) => {
    queue.value.push({
      id: `q-${++queueSeed}`,
      name: file.name,
      sizeKB: formatKB(file.size),
      type: "lit",
      status: "pending",
    });
  });

  if (files.length > room) {
    showToast("上传队列最多 10 个文件", "error");
  } else {
    showToast(`已加入 ${accepted.length} 个文件`);
  }
}

function onPick(e) {
  addFiles(e.target.files);
  e.target.value = "";
}

function onDrop(e) {
  dragOver.value = false;
  addFiles(e.dataTransfer?.files);
}

function formatKB(bytes) {
  const num = Number(bytes);
  if (!Number.isFinite(num) || num <= 0) return "0.0";
  return (num / 1024).toFixed(1);
}

function removeQueueItem(item) {
  if (uploading.value) return;
  queue.value = queue.value.filter((i) => i.id !== item.id);
  showToast("已从队列移除");
}

function clearQueue() {
  if (uploading.value || !queue.value.length) return;
  queue.value = [];
  showToast("队列已清空");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function startUpload() {
  if (uploading.value) return;
  const pending = queue.value.filter((i) => i.status === "pending" || i.status === "failed");
  if (!pending.length) {
    showToast("没有待上传的文件", "error");
    return;
  }

  uploading.value = true;
  for (const item of pending) {
    item.status = "uploading";
    await wait(300);
    item.status = "done";
  }
  uploading.value = false;
  showToast(`上传完成，共 ${pending.length} 个文件`);
}

/* ───────── 已上传文件 ───────── */
const uploaded = ref([
  {
    id: "UP-1042",
    name: "糖尿病中医证型分布研究_2023.pdf",
    size: "2.4 MB",
    type: "lit",
    uploadedAt: "2026-11-21 09:12",
    uploader: "张医师",
    status: "done",
  },
  {
    id: "UP-1041",
    name: "柴胡加龙骨牡蛎汤治疗失眠病案.docx",
    size: "0.6 MB",
    type: "case",
    uploadedAt: "2026-11-20 16:40",
    uploader: "李研究员",
    status: "done",
  },
  {
    id: "UP-1040",
    name: "针灸治疗偏头痛系统评价.pdf",
    size: "3.1 MB",
    type: "lit",
    uploadedAt: "2026-11-20 10:05",
    uploader: "王医生",
    status: "done",
  },
  {
    id: "UP-1039",
    name: "慢性胃炎门诊病案汇总_01.docx",
    size: "1.2 MB",
    type: "case",
    uploadedAt: "2026-11-19 15:28",
    uploader: "陈医生",
    status: "failed",
  },
  {
    id: "UP-1038",
    name: "黄芪多糖免疫调节机制研究.pdf",
    size: "4.8 MB",
    type: "lit",
    uploadedAt: "2026-11-19 11:02",
    uploader: "赵研究员",
    status: "done",
  },
  {
    id: "UP-1037",
    name: "冠心病PCI术后随访病案.pdf",
    size: "1.7 MB",
    type: "case",
    uploadedAt: "2026-11-18 17:20",
    uploader: "孙医生",
    status: "done",
  },
  {
    id: "UP-1036",
    name: "中医体质分类与判定标准.txt",
    size: "0.2 MB",
    type: "lit",
    uploadedAt: "2026-11-18 09:46",
    uploader: "周老师",
    status: "done",
  },
  {
    id: "UP-1035",
    name: "肺结节中医辨治验案三则.docx",
    size: "0.9 MB",
    type: "case",
    uploadedAt: "2026-11-17 14:33",
    uploader: "吴医师",
    status: "done",
  },
]);

const filterType = ref("");
const searchQuery = ref("");

const filteredUploaded = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return uploaded.value.filter((file) => {
    if (filterType.value && file.type !== filterType.value) return false;
    if (q && !file.name.toLowerCase().includes(q)) return false;
    return true;
  });
});

function typeLabel(value) {
  return TYPE_OPTIONS.find((opt) => opt.value === value)?.label || value;
}

function shortName(name) {
  return name.length > 18 ? `${name.slice(0, 18)}…` : name;
}

function onUploadedTypeChange(file) {
  showToast(`已将「${shortName(file.name)}」分类为${typeLabel(file.type)}`);
}

function deleteUploaded(file) {
  uploaded.value = uploaded.value.filter((f) => f.id !== file.id);
  showToast("已删除（mock）");
}

onBeforeUnmount(() => {
  clearTimeout(toastTimer);
});
</script>

<style scoped>
.admin-page {
  width: 100%;
  padding: 24px 32px;
  min-height: 100%;
}

.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.admin-header h1 {
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
  margin: 0 0 4px;
}
.header-sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}

.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 18px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
  margin: 0 0 3px;
}
.panel-desc {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}
.queue-total {
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}

/* ───────── 上传区 ───────── */
.upload-panel {
  background: linear-gradient(180deg, #f3fbfa 0%, #fff 100%);
}
.queue-meter {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.queue-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--teal-dark);
  white-space: nowrap;
}
.meter {
  width: 140px;
  height: 8px;
  border-radius: 999px;
  background: #e8f1ef;
  overflow: hidden;
}
.meter-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--teal);
  transition: width 0.25s ease;
}
.meter-full {
  background: var(--warn);
}

.dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 20px;
  border: 2px dashed var(--teal-border);
  border-radius: 10px;
  background: #fbfefd;
  cursor: pointer;
  text-align: center;
  transition: background 0.15s, border-color 0.15s;
}
.dropzone:hover {
  background: #f2faf8;
  border-color: var(--teal);
}
.dropzone-active {
  background: var(--teal-soft);
  border-color: var(--teal);
}
.dropzone-full {
  opacity: 0.72;
}
.dropzone-icon {
  font-size: 26px;
  line-height: 1;
  color: var(--teal);
  margin-bottom: 8px;
}
.dropzone-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-900);
}
.dropzone-sub {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--ink-400);
}
.btn-pick {
  padding: 7px 20px;
  border: 1px solid var(--teal-border);
  border-radius: 6px;
  background: #fff;
  color: var(--teal);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-pick:hover {
  background: var(--teal-soft);
}
.dropzone-tip {
  margin: 10px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}
.file-input {
  display: none;
}

/* ───────── 表格通用 ───────── */
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.pool-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.pool-table th {
  text-align: left;
  padding: 10px 12px;
  background: #f5f7f7;
  color: var(--ink-500);
  font-weight: 500;
  border-bottom: 2px solid #e4e8e8;
  white-space: nowrap;
}
.pool-table td {
  padding: 9px 12px;
  border-bottom: 1px solid #eee;
  color: var(--ink-700);
  vertical-align: middle;
}
.pool-table tbody tr:last-child td {
  border-bottom: none;
}
.pool-table tbody tr:hover {
  background: #f7fbfa;
}

.col-name {
  min-width: 300px;
}
.col-size {
  width: 100px;
}
.col-type {
  width: 120px;
}
.col-status {
  width: 100px;
}
.col-time {
  width: 150px;
}
.col-uploader {
  width: 110px;
}
.col-actions {
  width: 90px;
}

.cell-name {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-900);
}
.cell-size,
.cell-time {
  white-space: nowrap;
  color: var(--ink-500);
  font-size: 12px;
}
.cell-uploader {
  white-space: nowrap;
}

.row-select {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--ink-700);
}
select.row-select:disabled {
  background: #f5f5f5;
  color: var(--ink-400);
  cursor: not-allowed;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}
.badge-ok {
  background: #e8f5e9;
  color: var(--ok);
}
.badge-warn {
  background: #fff8e1;
  color: var(--warn);
}
.badge-danger {
  background: #ffebee;
  color: var(--danger);
}
.badge-muted {
  background: #f5f5f5;
  color: #666;
}

.btn-sm {
  padding: 3px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
  white-space: nowrap;
}
.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-remove {
  color: var(--danger);
  border-color: #f3c8c8;
}
.btn-remove:not(:disabled):hover {
  background: #ffebee;
}

.btn-ghost {
  padding: 8px 18px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-ghost:not(:disabled):hover {
  background: #f5f5f5;
}
.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ───────── 队列空状态与操作 ───────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 44px 16px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  background: #fcfdfd;
  text-align: center;
}
.empty-icon {
  font-size: 28px;
  line-height: 1;
  margin-bottom: 10px;
  opacity: 0.75;
}
.empty-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-700);
}
.empty-desc {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}

.queue-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.uploading-hint {
  font-size: 12px;
  color: var(--teal-dark);
}

/* ───────── 已上传筛选 ───────── */
.uploaded-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.btn-reset {
  padding: 7px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 12px;
  cursor: pointer;
}
.btn-reset:hover {
  background: #f5f5f5;
}
.result-count {
  font-size: 12px;
  color: var(--ink-400);
  margin-left: auto;
  white-space: nowrap;
}

/* ───────── 脚本提示 ───────── */
.script-card {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--teal-border);
  border-radius: 10px;
  background: #f2faf8;
}
.script-icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.script-title {
  margin: 0 0 5px;
  font-size: 13px;
  font-weight: 600;
  color: var(--teal-dark);
}
.script-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-500);
}
.script-code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #fff;
  border: 1px solid var(--teal-border);
  color: var(--teal-dark);
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  word-break: break-all;
}

/* ───────── toast ───────── */
.toast {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 2000;
  padding: 12px 18px;
  border-radius: 8px;
  font-size: 13px;
  color: #fff;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  max-width: 420px;
}
.toast-success {
  background: var(--teal);
}
.toast-error {
  background: var(--danger);
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

@media (max-width: 720px) {
  .admin-page {
    padding: 18px 16px;
  }
  .panel-head {
    flex-direction: column;
  }
  .queue-meter {
    width: 100%;
  }
  .meter {
    flex: 1;
  }
}
</style>
