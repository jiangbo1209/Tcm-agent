<template>
  <div class="etl-page">
    <header class="etl-header">
      <div>
        <h1>ETL 管理</h1>
        <p class="header-sub">资源抽取 · 质量校验 · 参数配置</p>
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

.etl-nav { display: flex; gap: 4px; margin-bottom: 18px; border-bottom: 1px solid var(--line); }
.etl-tab {
  padding: 8px 16px; font-size: 13px; color: var(--ink-500); text-decoration: none;
  border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color 0.15s, border-color 0.15s;
}
.etl-tab:hover { color: var(--teal-dark); }
.etl-tab.active { color: var(--teal-dark); font-weight: 600; border-bottom-color: var(--teal); }
</style>
