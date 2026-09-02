<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>数据标注管理</h1>
    </div>

    <div class="mgmt-tabs">
      <router-link
        v-for="tab in TABS"
        :key="tab.key"
        :to="`/admin/annotation/${tab.key}`"
        class="mgmt-tab"
        :class="{ 'mgmt-tab-active': $route.path.startsWith(`/admin/annotation/${tab.key}`) }"
        :data-testid="tab.testid"
      >
        {{ tab.label }}
      </router-link>
    </div>

    <router-view />
  </div>
</template>

<script setup>
/* ───────── 页签 ───────── */
const TABS = [
  { key: "pools", label: "任务池", testid: "pools-tab" },
  { key: "review", label: "复核队列", testid: "review-tab" },
  { key: "board", label: "看板", testid: "board-tab" },
  { key: "export", label: "导出", testid: "export-tab" },
  { key: "logs", label: "操作记录", testid: "logs-tab" },
];
</script>

<style scoped>
.mgmt-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e0e0e0; }
.mgmt-tab {
  padding: 9px 18px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  position: relative;
  top: 2px;
  border-bottom: 2px solid transparent;
  text-decoration: none;
  display: inline-block;
}
.mgmt-tab:hover { color: #00796b; background: #f0f7f6; }
.mgmt-tab-active { color: #00796b; font-weight: 600; border-bottom-color: #00796b; background: transparent; }
</style>
