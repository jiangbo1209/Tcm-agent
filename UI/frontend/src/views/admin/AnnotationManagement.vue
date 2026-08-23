<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>数据标注管理</h1>
    </div>

    <div class="mgmt-tabs">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="mgmt-tab"
        :class="{ 'mgmt-tab-active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ═══════════ 任务池 ═══════════ -->
    <template v-if="activeTab === 'pools'">
      <!-- 建池向导 -->
      <div class="wizard-card">
        <div class="wizard-header" @click="wizardOpen = !wizardOpen">
          <h2>建池向导</h2>
          <button class="btn-sm btn-wizard-toggle" type="button">
            {{ wizardOpen ? "收起 ▲" : "展开 ▼" }}
          </button>
        </div>
        <div v-show="wizardOpen" class="wizard-body">
          <div class="wizard-grid">
            <div class="form-field">
              <label>表类型</label>
              <select v-model="wizard.table_name">
                <option value="lit">文献元数据</option>
                <option value="case">病案元数据</option>
                <option value="guideline">指南元数据</option>
              </select>
            </div>
            <div class="form-field">
              <label>搜索词</label>
              <input v-model="wizard.q" type="text" placeholder="标题 / 关键词等，留空不过滤" />
            </div>
            <div class="form-field">
              <label>爬取状态</label>
              <select v-model="wizard.crawl_status">
                <option value="">全部</option>
                <option value="success">成功</option>
                <option value="partial">部分成功</option>
                <option value="failed">失败</option>
              </select>
            </div>
            <div class="form-field">
              <label>年份区间</label>
              <div class="year-range">
                <input v-model.number="wizard.year_min" type="number" placeholder="起始年份" />
                <span class="year-sep">—</span>
                <input v-model.number="wizard.year_max" type="number" placeholder="截止年份" />
              </div>
            </div>
            <div class="form-field">
              <label>截止天数</label>
              <input v-model.number="wizard.deadline_days" type="number" min="1" placeholder="留空使用全局默认" />
            </div>
          </div>
          <div class="wizard-actions">
            <button class="btn-create" :disabled="previewing" @click="handlePreview">
              {{ previewing ? "预览中..." : "预览" }}
            </button>
            <button class="btn-create btn-confirm" :disabled="!canCreate || creating" @click="handleCreatePool">
              {{ creating ? "建池中..." : "确认建池" }}
            </button>
          </div>
          <p v-if="previewText" class="preview-result" data-testid="pool-preview">{{ previewText }}</p>
          <p v-if="wizardError" class="form-error">{{ wizardError }}</p>
        </div>
      </div>

      <!-- 池列表 -->
      <div v-if="poolsLoading" class="loading">加载中...</div>
      <div v-else class="table-wrap">
        <table class="pool-table" data-testid="pool-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>表类型</th>
              <th>状态</th>
              <th>优先级</th>
              <th>余量</th>
              <th>截止天数</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pool in pools" :key="pool.id">
              <td>{{ pool.id }}</td>
              <td>{{ tableLabel(pool.table_name) }}</td>
              <td>
                <span class="badge" :class="statusMeta(pool.status).cls">
                  {{ statusMeta(pool.status).label }}
                </span>
              </td>
              <td class="cell-priority">{{ pool.priority }}</td>
              <td>
                <div class="progress-cell">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: progressPct(pool) + '%' }"></div>
                  </div>
                  <span class="progress-text">{{ pool.remaining_items }}/{{ pool.total_items }}</span>
                </div>
              </td>
              <td class="cell-time">{{ pool.deadline_days ?? "默认" }}</td>
              <td class="cell-time">{{ formatDate(pool.created_at) }}</td>
              <td class="cell-actions">
                <button class="btn-sm btn-assign" @click="openAssign(pool)">指派</button>
                <button
                  v-if="pool.status === 'active'"
                  class="btn-sm btn-toggle"
                  @click="pausePool(pool)"
                >
                  暂停
                </button>
                <button v-if="pool.status !== 'closed'" class="btn-sm btn-delete" @click="closePool(pool)">
                  关闭
                </button>
                <button class="btn-sm btn-priority" @click="changePriority(pool, 1)">优先级+1</button>
                <button class="btn-sm btn-priority" @click="changePriority(pool, -1)">优先级-1</button>
              </td>
            </tr>
            <tr v-if="pools.length === 0">
              <td colspan="8" class="empty-row">暂无任务池</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ═══════════ 其他页签占位（T16/T17 落地） ═══════════ -->
    <div v-else class="placeholder-card">建设中</div>

    <!-- ═══════════ 指派对话框 ═══════════ -->
    <div v-if="assignTarget" class="modal-overlay" @click.self="closeAssign">
      <div class="modal-box" data-testid="assign-dialog">
        <div class="modal-header">
          <h2>指派任务 — 池 #{{ assignTarget.id }}（{{ tableLabel(assignTarget.table_name) }}）</h2>
          <button class="modal-close" @click="closeAssign">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="annotatorsLoading" class="loading">加载标注员中...</div>
          <template v-else>
            <p class="annotator-hint">
              勾选要代派的标注员（每人随机抽取一批条目；余量 {{ assignTarget.remaining_items }}/{{ assignTarget.total_items }}）
            </p>
            <div v-if="annotators.length === 0" class="empty-hint">暂无可指派的标注员</div>
            <label v-for="u in annotators" :key="u.id" class="annotator-row">
              <input v-model="selectedUserIds" type="checkbox" :value="u.id" :disabled="!!assignResults" />
              <span class="annotator-name">{{ u.username }}</span>
              <span class="annotator-email">{{ u.email }}</span>
            </label>
          </template>

          <div v-if="assignError" class="form-error">{{ assignError }}</div>

          <div v-if="assignResults" class="assign-results">
            <h3>指派结果</h3>
            <p
              v-for="(r, idx) in assignResults"
              :key="idx"
              :class="r.ok ? 'result-ok' : 'result-fail'"
            >
              <template v-if="r.ok">✓ {{ userName(r.user_id) }}：已派 {{ r.count }} 条</template>
              <template v-else>✗ {{ userName(r.user_id) }}：{{ r.error }}</template>
            </p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="closeAssign">{{ assignResults ? "关闭" : "取消" }}</button>
          <button
            v-if="!assignResults"
            class="btn-save"
            :disabled="assigning || selectedUserIds.length === 0"
            @click="confirmAssign"
          >
            {{ assigning ? "指派中..." : `确认指派（${selectedUserIds.length}）` }}
          </button>
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
import { ref, computed, watch, onMounted } from "vue";
import {
  listPools,
  previewPool,
  createPool,
  updatePool,
  assignTasks,
} from "../../api/annotation";
import { fetchUsers } from "../../api/users";

/* ───────── 页签 ───────── */
const TABS = [
  { key: "pools", label: "任务池" },
  { key: "review", label: "复核队列" },
  { key: "board", label: "看板" },
  { key: "export", label: "导出" },
  { key: "rollback", label: "回滚" },
];
const activeTab = ref("pools");

/* ───────── 字典 ───────── */
const TABLE_LABELS = { lit: "文献元数据", case: "病案元数据", guideline: "指南元数据" };
const STATUS_META = {
  active: { label: "进行中", cls: "badge-active" },
  paused: { label: "已暂停", cls: "badge-paused" },
  closed: { label: "已关闭", cls: "badge-closed" },
};

function tableLabel(name) {
  return TABLE_LABELS[name] || name;
}
function statusMeta(status) {
  return STATUS_META[status] || { label: status, cls: "badge-closed" };
}
function formatDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 4000);
}

/* ───────── 建池向导 ───────── */
const wizardOpen = ref(true);
const wizard = ref({
  table_name: "lit",
  q: "",
  crawl_status: "",
  year_min: null,
  year_max: null,
  deadline_days: null,
});
const previewing = ref(false);
const creating = ref(false);
const previewResult = ref(null); // { total_matched, eligible }
const wizardError = ref("");

// 任一筛选条件变化后旧预览失效，需重新预览才能建池
watch(
  () => [
    wizard.value.table_name,
    wizard.value.q,
    wizard.value.crawl_status,
    wizard.value.year_min,
    wizard.value.year_max,
  ],
  () => {
    previewResult.value = null;
  }
);

const previewText = computed(() => {
  if (!previewResult.value) return "";
  const { total_matched, eligible } = previewResult.value;
  let text = `命中 ${total_matched} 条，可加入 ${eligible} 条`;
  if (eligible < total_matched) {
    text += `（另有 ${total_matched - eligible} 条已被占用或已完成标注）`;
  }
  return text;
});

const canCreate = computed(() => !!previewResult.value && previewResult.value.eligible > 0);

function numOrNull(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function filterPayload() {
  const w = wizard.value;
  return {
    table_name: w.table_name,
    q: String(w.q || "").trim() || null,
    crawl_status: w.crawl_status || null,
    year_min: numOrNull(w.year_min),
    year_max: numOrNull(w.year_max),
  };
}

async function handlePreview() {
  wizardError.value = "";
  previewing.value = true;
  try {
    const res = await previewPool(filterPayload());
    previewResult.value = res.data;
  } catch (e) {
    previewResult.value = null;
    wizardError.value = e.response?.data?.detail || "预览失败";
  } finally {
    previewing.value = false;
  }
}

async function handleCreatePool() {
  if (!canCreate.value) return;
  wizardError.value = "";
  creating.value = true;
  try {
    const res = await createPool({ ...filterPayload(), deadline_days: numOrNull(wizard.value.deadline_days) });
    const d = res.data || {};
    let msg = `建池成功：入池 ${d.total} 条`;
    if (d.shortfall > 0) msg += `，另有 ${d.shortfall} 条已被占用或已完成标注未能入池`;
    showToast(msg);
    previewResult.value = null;
    await loadPools();
  } catch (e) {
    wizardError.value = e.response?.data?.detail || "建池失败";
  } finally {
    creating.value = false;
  }
}

/* ───────── 池列表 ───────── */
const pools = ref([]);
const poolsLoading = ref(false);

async function loadPools() {
  poolsLoading.value = true;
  try {
    const res = await listPools();
    pools.value = Array.isArray(res.data) ? res.data : [];
  } catch (e) {
    console.error("Failed to load pools:", e);
  } finally {
    poolsLoading.value = false;
  }
}

function progressPct(pool) {
  if (!pool.total_items) return 0;
  return Math.min(100, Math.round((pool.remaining_items / pool.total_items) * 100));
}

async function changePriority(pool, delta) {
  try {
    await updatePool(pool.id, { priority: pool.priority + delta });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "调整优先级失败");
    await loadPools();
  }
}

async function pausePool(pool) {
  try {
    await updatePool(pool.id, { status: "paused" });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "暂停失败");
    await loadPools();
  }
}

async function closePool(pool) {
  if (!confirm(`确定关闭任务池 #${pool.id} 吗？关闭后不再参与派发。`)) return;
  try {
    await updatePool(pool.id, { status: "closed" });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "关闭失败");
    await loadPools();
  }
}

/* ───────── 指派对话框 ───────── */
const assignTarget = ref(null); // 当前指派的池行
const annotators = ref([]);
const annotatorsLoading = ref(false);
const selectedUserIds = ref([]);
const assigning = ref(false);
const assignResults = ref(null); // 后端逐用户结果数组
const assignError = ref("");

function userName(userId) {
  const u = annotators.value.find((a) => a.id === userId);
  return u ? u.username : `用户#${userId}`;
}

async function openAssign(pool) {
  assignTarget.value = pool;
  selectedUserIds.value = [];
  assignResults.value = null;
  assignError.value = "";
  annotatorsLoading.value = true;
  try {
    const res = await fetchUsers();
    annotators.value = (res.data.users || []).filter((u) => u.role === "annotator");
  } catch (e) {
    annotators.value = [];
    assignError.value = e.response?.data?.detail || "加载标注员失败";
  } finally {
    annotatorsLoading.value = false;
  }
}

function closeAssign() {
  assignTarget.value = null;
  assignResults.value = null;
  assignError.value = "";
}

async function confirmAssign() {
  if (!assignTarget.value || selectedUserIds.value.length === 0) return;
  assignError.value = "";
  assigning.value = true;
  try {
    const res = await assignTasks(assignTarget.value.id, [...selectedUserIds.value]);
    assignResults.value = res.data?.results || [];
    selectedUserIds.value = [];
    await loadPools(); // 代派消耗余量，刷新列表
  } catch (e) {
    assignError.value = e.response?.data?.detail || "指派失败";
  } finally {
    assigning.value = false;
  }
}

onMounted(loadPools);
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; }

.admin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.admin-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }

.mgmt-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e0e0e0; }
.mgmt-tab { padding: 9px 18px; border: none; background: transparent; font-size: 13px; color: #666; cursor: pointer; border-radius: 6px 6px 0 0; position: relative; top: 2px; border-bottom: 2px solid transparent; }
.mgmt-tab:hover { color: #00796b; background: #f0f7f6; }
.mgmt-tab-active { color: #00796b; font-weight: 600; border-bottom-color: #00796b; background: transparent; }

.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

/* ── 建池向导 ── */
.wizard-card { border: 1px solid #e0e0e0; border-radius: 10px; margin-bottom: 20px; background: #fff; overflow: hidden; }
.wizard-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; cursor: pointer; user-select: none; }
.wizard-header:hover { background: #f0f7f6; }
.wizard-header h2 { font-size: 15px; font-weight: 600; color: #1a1a2e; margin: 0; }
.btn-wizard-toggle { color: #00796b; border-color: #b2dfdb; }
.btn-wizard-toggle:hover { background: #e0f2f1; }
.wizard-body { padding: 4px 16px 16px; border-top: 1px solid #eee; }

.wizard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px 16px; margin-top: 12px; }
.form-field { margin-bottom: 0; }
.form-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.form-field input, .form-field select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; background: #fff; }
.form-field input:focus, .form-field select:focus { border-color: #00796b; }

.year-range { display: flex; align-items: center; gap: 6px; }
.year-range input { min-width: 0; }
.year-sep { color: #999; }

.wizard-actions { display: flex; gap: 10px; margin-top: 14px; }
.btn-create { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-create:hover { background: #00695c; }
.btn-create:disabled { opacity: 0.5; cursor: default; }
.btn-confirm { background: #ff8f00; }
.btn-confirm:hover { background: #f57c00; }
.btn-confirm:disabled { opacity: 0.5; cursor: default; }

.preview-result { margin: 12px 0 0; padding: 8px 12px; border-radius: 6px; background: #e0f2f1; color: #00695c; font-size: 13px; }
.form-error { color: #c62828; font-size: 12px; margin: 10px 0 0; }

/* ── 占位页签 ── */
.placeholder-card { border: 1px dashed #d0d0d0; border-radius: 10px; padding: 64px 0; text-align: center; color: #999; font-size: 14px; background: #fafafa; }

/* ── 池列表 ── */
.table-wrap { overflow-x: auto; }
.pool-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pool-table th { text-align: left; padding: 10px 12px; background: #f5f5f5; color: #666; font-weight: 500; border-bottom: 2px solid #e0e0e0; white-space: nowrap; }
.pool-table td { padding: 10px 12px; border-bottom: 1px solid #eee; color: #333; vertical-align: middle; }
.pool-table tr:hover { background: #fafafa; }
.cell-priority { font-weight: 600; color: #00796b; }
.cell-time { color: #888; font-size: 12px; white-space: nowrap; }
.cell-actions { white-space: nowrap; }
.empty-row { text-align: center; color: #999; padding: 40px 12px !important; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-active { background: #e8f5e9; color: #2e7d32; }
.badge-paused { background: #fff8e1; color: #f57f17; }
.badge-closed { background: #f5f5f5; color: #666; }

.progress-cell { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.progress-track { flex: 1; height: 8px; border-radius: 4px; background: #eeeeee; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 4px; background: #00796b; transition: width 0.3s ease; }
.progress-text { font-size: 12px; color: #666; white-space: nowrap; }

.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; cursor: pointer; background: #fff; }
.btn-assign { color: #00796b; border-color: #b2dfdb; }
.btn-assign:hover { background: #e0f2f1; }
.btn-toggle { color: #e65100; border-color: #ffcc80; }
.btn-toggle:hover { background: #fff3e0; }
.btn-delete { color: #c62828; border-color: #ef9a9a; }
.btn-delete:hover { background: #ffebee; }
.btn-priority { color: #5e35b1; border-color: #d1c4e9; }
.btn-priority:hover { background: #ede7f6; }

/* ── 指派对话框 ── */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; width: 480px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #e8e8e8; }
.modal-header h2 { font-size: 15px; font-weight: 600; margin: 0; }
.modal-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #999; cursor: pointer; border-radius: 4px; }
.modal-close:hover { background: #f0f0f0; color: #333; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid #e8e8e8; }

.annotator-hint { font-size: 12px; color: #888; margin: 0 0 10px; }
.empty-hint { text-align: center; color: #999; font-size: 13px; padding: 24px 0; }
.annotator-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.annotator-row:hover { background: #f0f7f6; }
.annotator-row input[type="checkbox"] { accent-color: #00796b; }
.annotator-name { font-weight: 500; color: #333; }
.annotator-email { color: #999; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.assign-results { margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e0e0e0; }
.assign-results h3 { font-size: 13px; font-weight: 600; color: #666; margin: 0 0 8px; }
.assign-results p { margin: 4px 0; font-size: 13px; }
.result-ok { color: #2e7d32; }
.result-fail { color: #c62828; }

.btn-cancel { padding: 8px 20px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; color: #666; }
.btn-cancel:hover { background: #f0f0f0; }
.btn-save { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-save:hover { background: #00695c; }
.btn-save:disabled { opacity: 0.6; cursor: default; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
