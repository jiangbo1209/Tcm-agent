<template>
  <div class="etl-page">
    <header class="etl-header">
      <div>
        <h1>ETL 管理</h1>
      </div>
    </header>

    <nav class="etl-nav">
      <router-link to="/admin/etl/resources" class="etl-tab" :class="{ active: $route.path.startsWith('/admin/etl/resources') }">资源管理</router-link>
      <router-link to="/admin/etl/quality" class="etl-tab" :class="{ active: $route.path.startsWith('/admin/etl/quality') }">质检看板</router-link>
      <router-link to="/admin/etl/settings" class="etl-tab" :class="{ active: $route.path.startsWith('/admin/etl/settings') }">基础配置</router-link>
    </nav>

    <router-view />
  </div>
</template>

<style scoped>
.etl-page { padding: 24px 32px 40px; }
.etl-header { margin-bottom: 14px; }
.etl-header h1 { font-size: 22px; font-weight: 600; color: var(--ink-900); margin: 0 0 4px; }
.header-sub { margin: 0; font-size: 12px; color: var(--ink-400); }

.etl-nav { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--line); }
.etl-tab {
  position: relative; display: inline-flex; align-items: center; gap: 7px;
  padding: 9px 16px 11px; font-size: 13px; color: var(--ink-500);
  text-decoration: none; border: none; background: transparent;
  transition: color 0.15s ease;
}
.etl-tab:hover { color: var(--ink-700); }
.etl-tab.active { color: var(--teal-dark); font-weight: 600; }
.etl-tab.active::after {
  content: ""; position: absolute; left: 10px; right: 10px; bottom: -1px;
  height: 2px; border-radius: 2px 2px 0 0; background: var(--teal);
}
</style>
