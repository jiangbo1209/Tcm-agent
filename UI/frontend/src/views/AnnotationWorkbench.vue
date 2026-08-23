<template>
  <div class="annotation-workbench">
    <div class="wb-header">
      <h1>标注工作台</h1>
      <span
        v-if="reworkCount > 0"
        class="rework-badge"
        data-testid="rework-badge"
      >
        待返工 {{ reworkCount }}
      </span>
    </div>

    <!-- 初始加载 -->
    <div v-if="view === 'loading'" class="wb-loading">加载中...</div>

    <!-- 功能总闸未开启（503，A5） -->
    <div v-else-if="view === 'disabled'" class="wb-empty" data-testid="feature-disabled">
      <p class="empty-title">功能未开启</p>
      <p class="empty-hint">数据标注功能尚未开放，请联系管理员。</p>
    </div>

    <!-- 领取面板：无进行中任务时展示 -->
    <div v-else-if="view === 'claim'" class="claim-panel" data-testid="claim-panel">
      <div class="panel-card">
        <h2>领取标注任务</h2>
        <p class="panel-hint">
          点击下方按钮领取一批待标注数据（每次最多 50 条），
          领取后须在截止时间内完成并提交。
        </p>
        <p v-if="claimError" class="panel-error">{{ claimError }}</p>
        <button class="btn-primary" :disabled="claiming" @click="handleClaim">
          {{ claiming ? "领取中..." : "领取任务" }}
        </button>
      </div>
    </div>

    <!-- 任务卡片：有进行中任务时展示 -->
    <div v-else class="task-card" data-testid="task-card">
      <div class="task-meta">
        <span class="meta-label">所属表</span>
        <span class="meta-value">{{ task.table_name }}</span>
      </div>
      <div class="task-meta">
        <span class="meta-label">进度</span>
        <span class="meta-value">{{ completedCount }}/{{ task.count }}</span>
      </div>
      <div class="task-meta">
        <span class="meta-label">剩余时间</span>
        <span class="meta-value countdown" :class="{ expired }">{{ countdownText }}</span>
      </div>
    </div>

    <!-- 条目列表占位（T14 提供真实渲染） -->
    <div class="item-list" data-testid="item-list">
      <p class="item-empty">
        {{ view === "task" ? "任务条目将在后续版本中在此展示" : "领取任务后在此查看待标注条目" }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { claimTask, getMyTask, getMyRework } from "../api/annotation";

// 视图状态：loading | disabled | claim | task
const view = ref("loading");
const task = ref(null);
const completedCount = ref(0); // 本地进度 x；T14 接入真实条目状态前恒为 0
const claiming = ref(false);
const claimError = ref("");
const reworkCount = ref(0);

const nowMs = ref(Date.now());
let countdownTimer = null;
let reworkTimer = null;
const REWORK_POLL_MS = 30_000;

function applyTask(data) {
  // 契约对齐后端 claim / my-task 响应：{ task_id, count, deadline_at, table_name }
  task.value = {
    task_id: data.task_id,
    count: Number(data.count ?? 0),
    deadline_at: data.deadline_at,
    table_name: data.table_name,
  };
  completedCount.value = 0;
}

/* ---------- 截止时间倒计时（每秒跳动） ---------- */

const remainingMs = computed(() => {
  if (!task.value?.deadline_at) return null;
  return new Date(task.value.deadline_at).getTime() - nowMs.value;
});

const expired = computed(() => remainingMs.value != null && remainingMs.value <= 0);

const countdownText = computed(() => {
  if (remainingMs.value == null) return "—";
  if (expired.value) return "已超时";
  const total = Math.floor(remainingMs.value / 1000);
  const hh = String(Math.floor(total / 3600)).padStart(2, "0");
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
});

function startCountdown() {
  stopCountdown();
  nowMs.value = Date.now();
  countdownTimer = setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

/* ---------- 返工徽标轮询（30s） ---------- */

async function pollRework() {
  try {
    const res = await getMyRework();
    // T7 契约未定，兼容 { count } 与数组两种返回形状
    const data = res.data;
    reworkCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? 0) || 0;
  } catch {
    // T7 落地前端点缺失（404）/网络失败：徽标隐藏，不打扰用户
    reworkCount.value = 0;
  }
}

function startReworkPolling() {
  stopReworkPolling();
  pollRework();
  reworkTimer = setInterval(pollRework, REWORK_POLL_MS);
}

function stopReworkPolling() {
  if (reworkTimer) {
    clearInterval(reworkTimer);
    reworkTimer = null;
  }
}

/* ---------- 当前任务加载与领取 ---------- */

async function loadCurrentTask() {
  view.value = "loading";
  try {
    const res = await getMyTask();
    // T7 契约：{ task: {...} | null }；落地前不会走到这里
    const current = res.data?.task ?? null;
    if (current) {
      applyTask(current);
      view.value = "task";
      startCountdown();
    } else {
      view.value = "claim";
    }
  } catch (e) {
    if (e.response?.status === 503) {
      // A5：ANNOTATION_ENABLED 总闸关闭 → 友好空态
      view.value = "disabled";
    } else {
      // T7 落地前 /my/task 不存在（404），403/网络失败同理：
      // 一律降级为“无进行中任务”，回退领取面板。T7 接入真实数据后可细化分支。
      view.value = "claim";
    }
  }
}

async function handleClaim() {
  claiming.value = true;
  claimError.value = "";
  try {
    const res = await claimTask();
    applyTask(res.data);
    view.value = "task";
    startCountdown();
  } catch (e) {
    if (e.response?.status === 503) {
      claimError.value = "功能未开启";
    } else {
      claimError.value = e.response?.data?.detail || "领取失败，请稍后重试";
    }
  } finally {
    claiming.value = false;
  }
}

onMounted(async () => {
  startReworkPolling();
  await loadCurrentTask();
});

onBeforeUnmount(() => {
  stopCountdown();
  stopReworkPolling();
});
</script>

<style scoped>
.annotation-workbench { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; box-sizing: border-box; }

.wb-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.wb-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }

.rework-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; background: #ffebee; color: #c62828; font-size: 12px; font-weight: 500; }

.wb-loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

.wb-empty { text-align: center; padding: 64px 0; }
.empty-title { font-size: 16px; font-weight: 600; color: #666; margin: 0 0 8px; }
.empty-hint { font-size: 13px; color: #999; margin: 0; }

.claim-panel { display: flex; justify-content: center; padding: 32px 0; }
.panel-card { width: 420px; background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 28px 32px; text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.panel-card h2 { font-size: 16px; font-weight: 600; color: #1a1a2e; margin: 0 0 10px; }
.panel-hint { font-size: 13px; color: #888; line-height: 1.6; margin: 0 0 18px; }
.panel-error { font-size: 12px; color: #c62828; margin: 0 0 12px; }

.btn-primary { padding: 9px 32px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-primary:hover { background: #00695c; }
.btn-primary:disabled { opacity: 0.6; cursor: default; }

.task-card { display: flex; gap: 32px; background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.task-meta { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.meta-label { font-size: 12px; color: #999; }
.meta-value { font-size: 15px; font-weight: 600; color: #333; word-break: break-all; }
.countdown { font-variant-numeric: tabular-nums; color: #00796b; }
.countdown.expired { color: #c62828; }

.item-list { background: #fff; border: 1px solid #e8e8e8; border-radius: 12px; padding: 48px 24px; text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.item-empty { font-size: 13px; color: #999; margin: 0; }
</style>
