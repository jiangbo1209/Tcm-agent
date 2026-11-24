<template>
  <div class="admin-page">
    <!-- 页头 -->
    <div class="admin-header">
      <div>
        <h1>数据源管理</h1>
        <p class="header-sub">管理文献 / 病案原始文件 · 队列上限 10 · 支持脚本批量导入</p>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-primary" @click="openUploadModal">上传文件</button>
        <button type="button" class="btn-secondary" @click="openQueueModal">
          上传队列（{{ queue.length }}/{{ MAX_QUEUE }}）
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div class="stat-card">
        <span class="stat-label">数据源总数</span>
        <span class="stat-value">{{ stats.total }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">文献</span>
        <span class="stat-value">{{ stats.lit }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">病案</span>
        <span class="stat-value">{{ stats.case }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">待上传</span>
        <span class="stat-value stat-muted">{{ stats.pending }}</span>
      </div>
    </div>

    <!-- 数据源列表 -->
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">数据源列表</h2>
          <p class="panel-desc">可调整分类或删除已上传的原始文件</p>
        </div>
      </div>

      <div class="toolbar">
        <div class="batch-menu" :class="{ 'is-disabled': selectedIds.size === 0 }">
          <button
            type="button"
            class="btn-batch-trigger"
            :disabled="selectedIds.size === 0"
            :title="selectedIds.size === 0 ? '请先勾选数据源' : '批量操作'"
          >
            批量操作<span v-if="selectedIds.size > 0" class="batch-num">（{{ selectedIds.size }}）</span>
            <span class="batch-caret">▾</span>
          </button>
          <div v-if="selectedIds.size > 0" class="batch-dropdown">
            <button type="button" class="batch-option danger" @click="askBatchDelete">批量删除</button>
            <button type="button" class="batch-option" @click="batchSetType('lit')">批量设为文献</button>
            <button type="button" class="batch-option" @click="batchSetType('case')">批量设为病案</button>
          </div>
        </div>
        <select v-model="filterType" class="filter-select">
          <option value="">全部类型</option>
          <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="filterStatus" class="filter-select">
          <option value="">全部状态</option>
          <option value="done">已完成</option>
          <option value="pending">待处理</option>
          <option value="failed">失败</option>
        </select>
        <input v-model="searchQuery" type="text" class="filter-input" placeholder="搜索文件名..." />
        <button v-if="searchQuery" type="button" class="btn-clear" @click="searchQuery = ''">清除</button>
        <span class="result-count">共 {{ filteredSources.length }} 条</span>
      </div>

      <div class="table-wrap">
        <table class="pool-table">
          <thead>
            <tr>
              <th class="col-check">
                <input
                  type="checkbox"
                  class="row-check"
                  :checked="isPageAllSelected"
                  :disabled="pagedList.length === 0"
                  title="全选本页"
                  @change="toggleSelectAllOnPage"
                />
              </th>
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
            <tr v-for="file in pagedList" :key="file.id" :class="{ 'row-selected': selectedIds.has(file.id) }">
              <td class="col-check">
                <input
                  type="checkbox"
                  class="row-check"
                  :checked="selectedIds.has(file.id)"
                  @change="toggleSelect(file.id)"
                />
              </td>
              <td class="cell-name" :title="file.name">{{ file.name }}</td>
              <td class="cell-size">{{ file.size }}</td>
              <td>
                <select
                  v-model="file.type"
                  class="filter-select row-select"
                  @change="onTypeChange(file)"
                >
                  <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </td>
              <td class="cell-time">{{ file.uploadedAt }}</td>
              <td class="cell-uploader">{{ file.uploader }}</td>
              <td>
                <span class="badge" :class="statusMeta(file.status).cls">{{ statusMeta(file.status).label }}</span>
              </td>
              <td>
                <button type="button" class="btn-sm btn-danger" @click="askDelete(file)">删除</button>
              </td>
            </tr>
            <tr v-if="filteredSources.length === 0">
              <td colspan="8" class="empty-row">暂无匹配的数据源</td>
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
        <span class="page-info">第 {{ page }} / {{ pageCount }} 页 · 共 {{ filteredSources.length }} 条</span>
        <div class="pager-btns">
          <button class="btn-sm" :disabled="page <= 1" @click="page--">上一页</button>
          <button class="btn-sm" :disabled="page >= pageCount" @click="page++">下一页</button>
        </div>
      </div>

    </section>

    <!-- 弹窗：批量删除 -->
    <div v-if="pendingBatchDelete" class="modal-mask" @click.self="pendingBatchDelete = false">
      <div class="modal modal-confirm">
        <div class="modal-head">
          <h3 class="modal-title">批量删除数据源</h3>
          <button type="button" class="modal-close" aria-label="关闭" @click="pendingBatchDelete = false">×</button>
        </div>
        <div class="confirm-body">
          <p class="confirm-text">确定删除选中的 <strong>{{ selectedIds.size }}</strong> 个数据源吗？此操作不可撤销。</p>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn-ghost" @click="pendingBatchDelete = false">取消</button>
          <div class="foot-right">
            <button type="button" class="btn-primary btn-danger-solid" @click="confirmBatchDelete">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗：上传文件 -->
    <div v-if="uploadModalOpen" class="modal-mask" @click.self="uploadModalOpen = false">
      <div class="modal modal-upload">
        <div class="modal-head">
          <h3 class="modal-title">上传文件</h3>
          <button type="button" class="modal-close" aria-label="关闭" @click="uploadModalOpen = false">×</button>
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
          <p class="dropzone-tip">
            支持 .pdf / .doc / .docx / .txt，队列还可添加 {{ remainingSlots }} 个
          </p>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt"
            class="file-input"
            @change="onPick"
          />
        </div>

        <div class="queue-mini">
          <span class="queue-mini-text">当前队列 {{ queue.length }} / {{ MAX_QUEUE }}</span>
          <div class="meter">
            <div
              class="meter-fill"
              :class="{ 'meter-full': queue.length >= MAX_QUEUE }"
              :style="{ width: queuePct + '%' }"
            ></div>
          </div>
        </div>

        <div class="modal-foot">
          <button type="button" class="btn-ghost" @click="uploadModalOpen = false">取消</button>
          <div class="foot-right">
            <button type="button" class="btn-ghost" @click="switchToQueue">查看上传队列</button>
            <button
              type="button"
              class="btn-primary"
              :disabled="!queue.length || uploading"
              @click="startFromUploadModal"
            >
              开始上传
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗：上传队列 -->
    <div v-if="queueModalOpen" class="modal-mask" @click.self="queueModalOpen = false">
      <div class="modal modal-queue">
        <div class="modal-head">
          <h3 class="modal-title">上传队列（{{ queue.length }}/{{ MAX_QUEUE }}）</h3>
          <button type="button" class="modal-close" aria-label="关闭" @click="queueModalOpen = false">×</button>
        </div>

        <div class="queue-progress">
          <div class="meter queue-meter">
            <div
              class="meter-fill"
              :class="{ 'meter-full': queue.length >= MAX_QUEUE }"
              :style="{ width: queuePct + '%' }"
            ></div>
          </div>
          <span class="queue-progress-text">{{ queue.length }} / {{ MAX_QUEUE }}</span>
        </div>

        <div v-if="queue.length" class="table-wrap queue-table-wrap">
          <table class="pool-table queue-table">
            <thead>
              <tr>
                <th class="col-name">文件名</th>
                <th class="col-size">大小</th>
                <th class="col-type">类型</th>
                <th class="col-status">状态</th>
                <th class="col-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in queue" :key="item.id">
                <td class="cell-name" :title="item.name">{{ item.name }}</td>
                <td class="cell-size">{{ formatBytes(item.sizeBytes) }}</td>
                <td>
                  <select
                    v-model="item.type"
                    class="filter-select row-select"
                    :disabled="item.status === 'uploading'"
                  >
                    <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </td>
                <td>
                  <span class="badge" :class="queueStatusMeta(item.status).cls">{{ queueStatusMeta(item.status).label }}</span>
                </td>
                <td>
                  <button
                    type="button"
                    class="btn-sm btn-danger"
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
          <p class="empty-desc">点击「上传文件」选择文件后，将显示在这里</p>
        </div>

        <div class="modal-foot">
          <button type="button" class="btn-ghost" :disabled="!queue.length || uploading" @click="clearQueue">
            清空队列
          </button>
          <div class="foot-right">
            <span v-if="uploading" class="uploading-hint">正在逐个上传，请稍候…</span>
            <button
              type="button"
              class="btn-primary"
              :disabled="!hasPendingInQueue || uploading"
              @click="startUpload"
            >
              {{ uploading ? "上传中…" : "开始上传" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗：删除确认 -->
    <div v-if="pendingDelete" class="modal-mask" @click.self="pendingDelete = null">
      <div class="modal modal-confirm">
        <div class="modal-head">
          <h3 class="modal-title">删除数据源</h3>
          <button type="button" class="modal-close" aria-label="关闭" @click="pendingDelete = null">×</button>
        </div>
        <div class="confirm-body">
          <p class="confirm-text">确定删除该数据源吗？此操作不可撤销。</p>
          <p class="confirm-name" :title="pendingDelete.name">{{ pendingDelete.name }}</p>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn-ghost" @click="pendingDelete = null">取消</button>
          <div class="foot-right">
            <button type="button" class="btn-primary btn-danger-solid" @click="confirmDelete">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount , watch} from "vue";

const MAX_QUEUE = 10;
const TYPE_OPTIONS = [
  { value: "lit", label: "文献" },
  { value: "case", label: "病案" },
];

const STATUS_META = {
  done: { label: "已完成", cls: "badge-ok" },
  pending: { label: "待处理", cls: "badge-muted" },
  failed: { label: "失败", cls: "badge-danger" },
};

const QUEUE_STATUS_META = {
  pending: { label: "待上传", cls: "badge-muted" },
  uploading: { label: "上传中", cls: "badge-warn" },
  done: { label: "已完成", cls: "badge-ok" },
  failed: { label: "失败", cls: "badge-danger" },
};

function statusMeta(status) {
  return STATUS_META[status] || { label: "—", cls: "badge-muted" };
}
function queueStatusMeta(status) {
  return QUEUE_STATUS_META[status] || { label: "—", cls: "badge-muted" };
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

/* ───────── 弹窗状态 ───────── */
const uploadModalOpen = ref(false);
const queueModalOpen = ref(false);
const pendingDelete = ref(null);

function openUploadModal() {
  uploadModalOpen.value = true;
}
function openQueueModal() {
  queueModalOpen.value = true;
}
function switchToQueue() {
  uploadModalOpen.value = false;
  queueModalOpen.value = true;
}

/* ───────── 数据源列表 ───────── */
let sourceSeed = 1042;
const sources = ref([
  {
    id: "DS-1042",
    name: "糖尿病中医证型分布研究_2023.pdf",
    size: "2.4 MB",
    type: "lit",
    source: "手动上传",
    uploadedAt: "2026-11-21 09:12",
    uploader: "张医师",
    status: "done",
  },
  {
    id: "DS-1041",
    name: "柴胡加龙骨牡蛎汤治疗失眠病案.docx",
    size: "0.6 MB",
    type: "case",
    source: "手动上传",
    uploadedAt: "2026-11-20 16:40",
    uploader: "李研究员",
    status: "done",
  },
  {
    id: "DS-1040",
    name: "针灸治疗偏头痛系统评价.pdf",
    size: "3.1 MB",
    type: "lit",
    source: "脚本批量",
    uploadedAt: "2026-11-20 10:05",
    uploader: "王医生",
    status: "done",
  },
  {
    id: "DS-1039",
    name: "慢性胃炎门诊病案汇总_01.docx",
    size: "1.2 MB",
    type: "case",
    source: "手动上传",
    uploadedAt: "2026-11-19 15:28",
    uploader: "陈医生",
    status: "failed",
  },
  {
    id: "DS-1038",
    name: "黄芪多糖免疫调节机制研究.pdf",
    size: "4.8 MB",
    type: "lit",
    source: "脚本批量",
    uploadedAt: "2026-11-19 11:02",
    uploader: "赵研究员",
    status: "done",
  },
  {
    id: "DS-1037",
    name: "冠心病PCI术后随访病案.pdf",
    size: "1.7 MB",
    type: "case",
    source: "手动上传",
    uploadedAt: "2026-11-18 17:20",
    uploader: "孙医生",
    status: "done",
  },
  {
    id: "DS-1036",
    name: "中医体质分类与判定标准.txt",
    size: "0.2 MB",
    type: "lit",
    source: "脚本批量",
    uploadedAt: "2026-11-18 09:46",
    uploader: "周老师",
    status: "done",
  },
  {
    id: "DS-1035",
    name: "肺结节中医辨治验案三则.docx",
    size: "0.9 MB",
    type: "case",
    source: "手动上传",
    uploadedAt: "2026-11-17 14:33",
    uploader: "吴医师",
    status: "done",
  },
]);


// 分页演示补充数据源（原型）
const EXTRA_SOURCES = Array.from({ length: 16 }, (_, i) => ({
  id: `DS-${String(2001 + i).padStart(4, "0")}`,
  name: [
    "补肾活血法治疗 DOR 病案汇编", "针灸治疗卵巢储备减退文献集", "DOR 证型分布调查数据",
    "IVF-ET 妊娠结局随访表", "中药复方配伍数据", "名老中医 DOR 验案集",
  ][i % 6] + `_${i + 1}.pdf`,
  size: `${(0.3 + (i % 7) * 0.4).toFixed(1)} MB`,
  type: i % 2 ? "case" : "lit",
  source: i % 3 === 0 ? "脚本批量" : "手动上传",
  uploadedAt: `2026-11-${String(10 + (i % 14)).padStart(2, "0")} ${String(8 + (i % 10)).padStart(2, "0")}:20`,
  uploader: ["张医师", "李研究员", "王医生", "陈医生"][i % 4],
  status: ["done", "done", "pending", "done"][i % 4],
}));
sources.value.push(...EXTRA_SOURCES);

const filterType = ref("");
const filterStatus = ref("");
const searchQuery = ref("");

const filteredSources = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return sources.value.filter((file) => {
    if (filterType.value && file.type !== filterType.value) return false;
    if (filterStatus.value && file.status !== filterStatus.value) return false;
    if (q && !file.name.toLowerCase().includes(q)) return false;
    return true;
  });
});

const PAGE_SIZES = [10, 20, 50, 100];
const page = ref(1);
const pageSize = ref(10);

const pageCount = computed(() =>
  Math.max(1, Math.ceil(filteredSources.value.length / pageSize.value))
);

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredSources.value.slice(start, start + pageSize.value);
});

watch([sources, pageSize], () => {
  page.value = 1;
});

watch(pageCount, (n) => {
  if (page.value > n) page.value = n;
});

const stats = computed(() => ({
  total: sources.value.length,
  lit: sources.value.filter((f) => f.type === "lit").length,
  case: sources.value.filter((f) => f.type === "case").length,
  pending: sources.value.filter((f) => f.status === "pending").length,
}));

function typeLabel(value) {
  return TYPE_OPTIONS.find((opt) => opt.value === value)?.label || value;
}

function shortName(name) {
  return name.length > 18 ? `${name.slice(0, 18)}…` : name;
}

/* ───────── 多选与批量操作 ───────── */
const selectedIds = ref(new Set());
const pendingBatchDelete = ref(false);

const isPageAllSelected = computed(
  () => pagedList.value.length > 0 && pagedList.value.every((f) => selectedIds.value.has(f.id)),
);

function toggleSelect(id) {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectedIds.value = next;
}

function toggleSelectAllOnPage() {
  const next = new Set(selectedIds.value);
  const all = isPageAllSelected.value;
  for (const f of pagedList.value) {
    if (all) next.delete(f.id);
    else next.add(f.id);
  }
  selectedIds.value = next;
}

watch([filterType, filterStatus, searchQuery], () => {
  selectedIds.value = new Set();
});

function askBatchDelete() {
  pendingBatchDelete.value = true;
}

function batchSetType(type) {
  const label = type === "lit" ? "文献" : "病案";
  const count = selectedIds.value.size;
  sources.value = sources.value.map((f) =>
    selectedIds.value.has(f.id) ? { ...f, type } : f,
  );
  selectedIds.value = new Set();
  showToast(`已将 ${count} 个数据源设置为${label}`);
}

function confirmBatchDelete() {
  const count = selectedIds.value.size;
  sources.value = sources.value.filter((f) => !selectedIds.value.has(f.id));
  selectedIds.value = new Set();
  pendingBatchDelete.value = false;
  if (page.value > pageCount.value) page.value = pageCount.value;
  showToast(`已删除 ${count} 个数据源`);
}

function onTypeChange(file) {
  showToast(`已将「${shortName(file.name)}」分类为${typeLabel(file.type)}`);
}

function askDelete(file) {
  pendingDelete.value = file;
}

function confirmDelete() {
  if (!pendingDelete.value) return;
  const target = pendingDelete.value;
  sources.value = sources.value.filter((f) => f.id !== target.id);
  pendingDelete.value = null;
  showToast("已删除该数据源");
}

/* ───────── 上传队列（页面级状态，关闭弹窗不清空） ───────── */
const queue = ref([]);
const uploading = ref(false);
const dragOver = ref(false);
const fileInput = ref(null);
let queueSeed = 0;

const queuePct = computed(() => Math.round((queue.value.length / MAX_QUEUE) * 100));
const remainingSlots = computed(() => Math.max(0, MAX_QUEUE - queue.value.length));
const hasPendingInQueue = computed(() =>
  queue.value.some((i) => i.status === "pending" || i.status === "failed")
);

function triggerPick() {
  fileInput.value?.click();
}

function addFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;

  const room = MAX_QUEUE - queue.value.length;
  if (room <= 0 || files.length > room) {
    showToast("上传队列最多 10 个文件", "error");
    return;
  }

  files.forEach((file) => {
    queue.value.push({
      id: `q-${++queueSeed}`,
      name: file.name,
      sizeBytes: file.size,
      type: "lit",
      status: "pending",
      added: false,
    });
  });
  showToast("已加入上传队列");
}

function onPick(e) {
  addFiles(e.target.files);
  e.target.value = "";
}

function onDrop(e) {
  dragOver.value = false;
  addFiles(e.dataTransfer?.files);
}

function formatBytes(bytes) {
  const num = Number(bytes);
  if (!Number.isFinite(num) || num <= 0) return "0 KB";
  if (num >= 1024 * 1024) return `${(num / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(num / 1024))} KB`;
}

function removeQueueItem(item) {
  if (uploading.value || item.status === "uploading") return;
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

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function addSourceFromQueue(item) {
  if (item.added) return;
  item.added = true;
  sources.value.unshift({
    id: `DS-${++sourceSeed}`,
    name: item.name,
    size: formatBytes(item.sizeBytes),
    type: item.type,
    source: "手动上传",
    uploadedAt: nowStamp(),
    uploader: "当前用户",
    status: "done",
  });
}

async function startUpload() {
  if (uploading.value) return;
  const pending = queue.value.filter((i) => i.status === "pending" || i.status === "failed");
  if (!pending.length) {
    showToast("队列中没有待上传的文件", "error");
    return;
  }

  uploading.value = true;
  for (const item of pending) {
    item.status = "uploading";
    await wait(300);
    item.status = "done";
    addSourceFromQueue(item);
  }
  uploading.value = false;
  showToast(`${pending.length} 个文件上传完成`);
}

function startFromUploadModal() {
  if (!queue.value.length || uploading.value) return;
  uploadModalOpen.value = false;
  showToast(`已开始上传 ${queue.value.length} 个文件，可在上传队列查看进度`);
  startUpload();
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

/* ───────── 页头 ───────── */
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
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
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* ───────── 按钮 ───────── */
.btn-primary {
  padding: 8px 18px;
  border: none;
  border-radius: 6px;
  background: var(--teal);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) {
  background: var(--teal-dark);
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-secondary {
  padding: 8px 16px;
  border: 1px solid var(--teal-border);
  border-radius: 6px;
  background: #fff;
  color: var(--teal-dark);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-secondary:hover {
  background: var(--teal-soft);
}
.btn-ghost {
  padding: 8px 16px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-ghost:hover:not(:disabled) {
  background: #f5f5f5;
}
.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ───────── 统计卡片 ───────── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.stat-label {
  font-size: 12px;
  color: var(--ink-500);
}
.stat-value {
  font-size: 26px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--teal-dark);
}
.stat-muted {
  color: var(--ink-700);
}

/* ───────── 面板 ───────── */
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

/* ───────── 工具栏 ───────── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.filter-select {
  padding: 7px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: var(--ink-700);
  outline: none;
}
.filter-input {
  padding: 7px 10px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  width: 220px;
  color: var(--ink-700);
}
.filter-select:focus,
.filter-input:focus {
  border-color: var(--teal);
}
.btn-clear {
  padding: 7px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 12px;
  cursor: pointer;
}
.btn-clear:hover {
  background: #f5f5f5;
}
.result-count {
  font-size: 12px;
  color: var(--ink-400);
  margin-left: auto;
  white-space: nowrap;
}

/* ───────── 表格 ───────── */
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
  min-width: 280px;
}
.col-size {
  width: 96px;
}
.col-type {
  width: 116px;
}
.col-source {
  width: 110px;
}
.col-status {
  width: 96px;
}
.col-time {
  width: 146px;
}
.col-uploader {
  width: 108px;
}
.col-actions {
  width: 84px;
}
.cell-name {
  max-width: 400px;
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
  color: var(--ink-500);
  font-size: 12px;
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

.source-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f3f4f6;
  color: var(--ink-500);
  font-size: 12px;
  white-space: nowrap;
}
.source-script {
  background: var(--teal-soft);
  color: var(--teal-dark);
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
  transition: background 0.15s;
}
.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-danger {
  color: var(--danger);
  border-color: #f3c8c8;
}
.btn-danger:not(:disabled):hover {
  background: #ffebee;
}
.btn-danger-solid {
  background: var(--danger);
}
.btn-danger-solid:hover:not(:disabled) {
  background: #a51f1f;
}
.empty-row {
  text-align: center;
  color: #999;
  padding: 40px 12px !important;
}

/* ───────── 弹窗 ───────── */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 24px;
}
.modal {
  background: var(--card);
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
  width: 100%;
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  padding: 20px;
}
.modal-upload {
  max-width: 540px;
}
.modal-queue {
  max-width: 760px;
}
.modal-confirm {
  max-width: 420px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-900);
}
.modal-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-400);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.modal-close:hover {
  background: #f3f4f6;
  color: var(--ink-700);
}
.modal-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}
.foot-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

/* ───────── 上传弹窗 ───────── */
.dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 26px 20px;
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
.queue-mini {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.queue-mini-text {
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}

/* ───────── 进度条 ───────── */
.meter {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: #e8f1ef;
  overflow: hidden;
}
.queue-meter {
  min-width: 160px;
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
.queue-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.queue-progress-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--teal-dark);
  white-space: nowrap;
}
.queue-table-wrap {
  max-height: 46vh;
  overflow-y: auto;
}
.queue-table .col-name {
  min-width: 220px;
}
.uploading-hint {
  font-size: 12px;
  color: var(--teal-dark);
  white-space: nowrap;
}

/* ───────── 空状态 ───────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
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

/* ───────── 删除确认 ───────── */
.confirm-body {
  padding: 2px 0 4px;
}
.confirm-text {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--ink-700);
}
.confirm-name {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f7f8f8;
  border: 1px solid var(--line);
  font-size: 13px;
  color: var(--ink-900);
  word-break: break-all;
}

/* ───────── toast ───────── */
.toast {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 3000;
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

/* ───────── 响应式 ───────── */
@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .admin-page {
    padding: 18px 16px;
  }
  .header-actions {
    width: 100%;
  }
  .filter-input {
    width: 100%;
  }
  .result-count {
    margin-left: 0;
  }
  .modal-mask {
    padding: 12px;
  }
  .modal-foot {
    flex-direction: column;
    align-items: stretch;
  }
  .foot-right {
    margin-left: 0;
  }
}

/* ── 多选与批量 ── */
.col-check { width: 40px; text-align: center; }
.row-check { width: 15px; height: 15px; accent-color: var(--teal); cursor: pointer; }
.row-selected td { background: #f0f7f6; }

.batch-menu { position: relative; display: inline-flex; }
.btn-batch-trigger {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 6px; font-size: 13px; cursor: pointer;
  border: 1px solid var(--teal-border); background: #fff; color: var(--teal-dark);
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.btn-batch-trigger:hover { background: var(--teal-soft); }
.batch-menu.is-disabled .btn-batch-trigger,
.btn-batch-trigger:disabled {
  background: #f3f4f4; border-color: #e0e0e0; color: #9ca3af; cursor: not-allowed;
}
.batch-num { font-weight: 600; }
.batch-caret { font-size: 10px; opacity: 0.8; }

.batch-dropdown {
  position: absolute; left: 0; top: calc(100% + 6px); min-width: 168px; z-index: 40;
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  box-shadow: 0 10px 28px rgba(20, 60, 55, 0.14); padding: 6px;
  display: none;
}
.batch-menu:hover .batch-dropdown,
.batch-menu:focus-within .batch-dropdown { display: block; }
.batch-option {
  display: block; width: 100%; text-align: left; padding: 8px 10px;
  border: none; background: transparent; border-radius: 6px;
  font-size: 13px; color: var(--ink-700); cursor: pointer;
}
.batch-option:hover { background: var(--teal-soft); color: var(--teal-dark); }
.batch-option.danger { color: #c62828; }
.batch-option.danger:hover { background: #ffebee; color: #b71c1c; }

/* ── 分页 ── */
.pager-bar { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
.page-size { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-500); }
.page-size .filter-select { padding: 4px 8px; }
.page-info { font-size: 12px; color: var(--ink-400); margin-left: auto; }
.pager-btns { display: flex; gap: 8px; }
.pager-btns .btn-sm:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
