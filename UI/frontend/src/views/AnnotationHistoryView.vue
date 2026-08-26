<template>
  <div class="annotation-history">
    <div class="history-header">
      <h1>标注记录</h1>
      <button type="button" class="btn-back" @click="$router.push('/annotate')">
        返回工作台
      </button>
    </div>

    <div v-if="loading" class="history-empty">加载中...</div>
    <div v-else-if="items.length === 0" class="history-empty">暂无标注记录</div>

    <template v-else>
      <div class="history-table-wrap">
        <table class="history-table">
          <thead>
            <tr>
              <th class="col-id">记录 ID</th>
              <th class="col-title">标题</th>
              <th class="col-table">数据表</th>
              <th class="col-status">状态</th>
              <th class="col-time">提交时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in items" :key="h.submission_id">
              <td class="col-id">#{{ h.record_id }}</td>
              <td class="col-title" :title="h.title || `病案#${h.record_id}`">
                {{ h.title || `病案#${h.record_id}` }}
              </td>
              <td class="col-table">
                <span class="table-badge">{{ h.table_name }}</span>
              </td>
              <td class="col-status">
                <span class="status-badge" :class="statusCls(h.status)">{{ statusLabel(h.status) }}</span>
              </td>
              <td class="col-time">{{ formatTime(h.submitted_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="total > pageSize" class="history-pagination">
        <button type="button" class="btn-page" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button type="button" class="btn-page" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { myAnnotationHistory } from "../api/annotation";

const loading = ref(true);
const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

async function loadData(p = 1) {
  loading.value = true;
  try {
    const res = await myAnnotationHistory({ page: p, page_size: pageSize });
    const data = res.data || {};
    items.value = Array.isArray(data.items) ? data.items : [];
    total.value = Number(data.total ?? items.value.length);
    page.value = Number(data.page ?? p);
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function goPage(p) {
  loadData(p);
}

function statusLabel(s) {
  const m = { approved: "已通过", rejected: "已驳回", pending: "待复核", expired: "已过期", draft: "草稿" };
  return m[s] || s;
}

function statusCls(s) {
  const m = { approved: "st-approved", rejected: "st-rejected", pending: "st-pending", expired: "st-expired", draft: "st-draft" };
  return m[s] || "st-other";
}

function formatTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

onMounted(() => loadData(1));
</script>

<style scoped>
.annotation-history { display: flex; flex-direction: column; width: 100%; padding: 24px 32px; height: 100vh; overflow-y: auto; box-sizing: border-box; }

.history-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.history-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }
.btn-back { padding: 6px 14px; border: 1px solid #00796b; border-radius: 6px; background: #fff; color: #00796b; font-size: 13px; cursor: pointer; font-family: inherit; }
.btn-back:hover { background: #e0f2f1; }

.history-empty { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

.history-table-wrap { overflow-x: auto; background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }

.history-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.history-table th { text-align: left; padding: 12px 16px; background: #fafafa; border-bottom: 1px solid #e8e8e8; color: #666; font-weight: 500; font-size: 12px; white-space: nowrap; }
.history-table td { padding: 10px 16px; border-bottom: 1px solid #f0f0f0; color: #333; }

.col-id { width: 90px; font-weight: 600; color: #1a1a2e; }
.col-title { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-table { width: 100px; }
.col-status { width: 90px; }
.col-time { width: 160px; color: #999; font-size: 12px; white-space: nowrap; }

.table-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; background: #e0f2f1; color: #00695c; font-size: 11px; font-weight: 500; }

.status-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.st-approved { background: #e8f5e9; color: #2e7d32; }
.st-rejected { background: #ffebee; color: #c62828; }
.st-pending { background: #fff8e1; color: #f57f17; }
.st-expired { background: #f0f0f0; color: #999; }
.st-draft { background: #e3f2fd; color: #1565c0; }
.st-other { background: #f0f0f0; color: #999; }

.history-pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding-top: 16px; }
.btn-page { padding: 5px 14px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; color: #333; font-size: 13px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
.btn-page:hover:not(:disabled) { border-color: #00796b; color: #00796b; }
.btn-page:disabled { opacity: 0.4; cursor: default; }
.page-info { font-size: 12px; color: #666; }
</style>
