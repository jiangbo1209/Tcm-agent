<template>
  <div class="board-view">
    <div v-if="boardLoading" class="loading">加载中...</div>
    <template v-else>
      <div class="coverage-grid">
        <div v-for="t in COVERAGE_TABLES" :key="t.key" class="coverage-card">
          <h3>{{ t.label }}</h3>
          <p class="coverage-num">已标注 {{ coverageOf(t.key).annotated }} / 共 {{ coverageOf(t.key).total }}</p>
          <div class="progress-track coverage-track">
            <div class="progress-fill" :style="{ width: coveragePct(t.key) + '%' }"></div>
          </div>
        </div>
      </div>

      <h2 class="board-section-title">标注员工作量</h2>
      <div class="table-wrap">
        <table class="pool-table" data-testid="board-users">
          <thead>
            <tr>
              <th>标注员</th>
              <th>已完成</th>
              <th>驳回率</th>
              <th>待返工</th>
              <th>在办任务</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in stats.users" :key="u.user_id">
              <td>{{ u.username }}</td>
              <td>{{ u.completed }}</td>
              <td>
                <span :class="'rate-' + rateLevel(u.rejected_rate)">{{ formatRate(u.rejected_rate) }}</span>
              </td>
              <td>{{ u.pending_rework }}</td>
              <td>{{ u.in_progress ? "是" : "否" }}</td>
            </tr>
            <tr v-if="stats.users.length === 0">
              <td colspan="5" class="empty-row">暂无标注员</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { dashboardStats } from "../../../api/annotation";

/* ───────── 看板 ───────── */
const COVERAGE_TABLES = [
  { key: "lit", label: "文献元数据" },
  { key: "case", label: "病案元数据" },
  { key: "guideline", label: "指南元数据" },
];
const boardLoading = ref(false);
const stats = ref({ pools: [], coverage: {}, users: [] });

function coverageOf(key) {
  const c = stats.value.coverage?.[key];
  return { annotated: c?.annotated ?? 0, total: c?.total ?? 0 };
}

function coveragePct(key) {
  const { annotated, total } = coverageOf(key);
  if (!total) return 0;
  return Math.min(100, Math.round((annotated / total) * 100));
}

function formatRate(rate) {
  return `${Math.round((rate ?? 0) * 100)}%`;
}

function rateLevel(rate) {
  const r = rate ?? 0;
  if (r > 0.3) return "high";
  if (r > 0.1) return "mid";
  return "low";
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

async function loadBoard() {
  boardLoading.value = true;
  try {
    const res = await dashboardStats();
    stats.value = {
      pools: Array.isArray(res.data?.pools) ? res.data.pools : [],
      coverage: res.data?.coverage || {},
      users: Array.isArray(res.data?.users) ? res.data.users : [],
    };
  } catch (e) {
    showToast(e.response?.data?.detail || "加载看板失败", "error");
  } finally {
    boardLoading.value = false;
  }
}

onMounted(() => {
  loadBoard();
});
</script>

<style scoped>
.board-view { padding: 0; }

.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

/* ── 覆盖率卡片 ── */
.coverage-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 4px; }
.coverage-card { border: 1px solid #e0e0e0; border-radius: 10px; background: #fff; padding: 16px; }
.coverage-card h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #666; }
.coverage-num { margin: 0 0 10px; font-size: 15px; font-weight: 600; color: #00796b; }
.coverage-track { height: 10px; }
.board-section-title { margin: 22px 0 10px; font-size: 15px; font-weight: 600; color: #1a1a2e; }

/* ── 工作量表格 ── */
.table-wrap { overflow-x: auto; }
.pool-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pool-table th, .pool-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e8e8e8; }
.pool-table th { font-weight: 600; color: #666; background: #fafafa; }
.pool-table td { color: #333; }
.empty-row { text-align: center; color: #999; padding: 24px 0; }

/* ── 驳回率色阶 ── */
.rate-high { color: #c62828; font-weight: 600; }
.rate-mid { color: #f57f17; font-weight: 600; }
.rate-low { color: #2e7d32; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
