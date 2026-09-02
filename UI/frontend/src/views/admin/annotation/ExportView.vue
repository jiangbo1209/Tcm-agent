<template>
  <div class="export-view">
    <div class="wizard-card">
      <div class="wizard-body export-body">
        <div class="wizard-grid">
          <div class="form-field">
            <label>标注员</label>
            <select v-model="exportFilter.user_id">
              <option :value="null">全部</option>
              <option v-for="u in annotators" :key="u.id" :value="u.id">{{ u.username }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>任务池</label>
            <select v-model="exportFilter.pool_id">
              <option :value="null">全部</option>
              <option v-for="p in pools" :key="p.id" :value="p.id">
                #{{ p.id }} {{ tableLabel(p.table_name) }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label>开始时间</label>
            <input v-model="exportFilter.date_from" type="datetime-local" />
          </div>
          <div class="form-field">
            <label>结束时间</label>
            <input v-model="exportFilter.date_to" type="datetime-local" />
          </div>
        </div>
        <div class="wizard-actions">
          <button class="btn-create" :disabled="exporting" @click="handleExportCsv">
            {{ exporting ? "导出中..." : "导出 CSV" }}
          </button>
        </div>
        <p v-if="exportError" class="form-error">{{ exportError }}</p>
      </div>
    </div>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { fetchUsers } from "../../../api/users";
import { listPools, exportCsv } from "../../../api/annotation";

/* ───────── 字典 ───────── */
const TABLE_LABELS = { lit: "文献元数据", case: "病案元数据", guideline: "指南元数据" };

function tableLabel(name) {
  return TABLE_LABELS[name] || name;
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

/* ───────── 导出 ───────── */
const annotators = ref([]);
const pools = ref([]);
const exportFilter = ref({ user_id: null, pool_id: null, date_from: "", date_to: "" });
const exporting = ref(false);
const exportError = ref("");

async function loadExportOptions() {
  try {
    const res = await fetchUsers();
    annotators.value = (res.data.users || []).filter((u) => u.role === "annotator");
  } catch {
    annotators.value = [];
  }
  try {
    const res = await listPools();
    pools.value = res.data || [];
  } catch {
    pools.value = [];
  }
}

function handleExportCsv() {
  exportError.value = "";
  exporting.value = true;
  const f = exportFilter.value;
  const params = {};
  if (f.user_id != null) params.user_id = f.user_id;
  if (f.pool_id != null) params.pool_id = f.pool_id;
  if (f.date_from) params.date_from = f.date_from;
  if (f.date_to) params.date_to = f.date_to;
  exportCsv(params)
    .then((res) => {
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "workload.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast("导出成功：workload.csv 已开始下载");
    })
    .catch(() => {
      exportError.value = "导出失败，请稍后重试";
    })
    .finally(() => {
      exporting.value = false;
    });
}

onMounted(() => {
  loadExportOptions();
});
</script>

<style scoped>
.export-view { padding: 0; }

/* ── 向导卡片 ── */
.wizard-card { border: 1px solid #e0e0e0; border-radius: 10px; background: #fff; padding: 20px; }
.wizard-body { padding-top: 12px; }
.wizard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 16px; }

.form-field { margin-bottom: 0; }
.form-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.form-field input, .form-field select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; background: #fff; }
.form-field input:focus, .form-field select:focus { border-color: #00796b; }
.form-error { color: #c62828; font-size: 12px; margin: 10px 0 0; }

.wizard-actions { display: flex; justify-content: flex-end; }
.btn-create { padding: 8px 18px; background: #00796b; color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 500; }
.btn-create:hover { background: #00695c; }
.btn-create:disabled { opacity: 0.6; cursor: not-allowed; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
