<template>
  <div class="ds-page">
    <header class="page-head">
      <h1>数据源管理</h1>
    </header>

    <nav class="tabs">
      <router-link to="/admin/sources/resources" class="tab" :class="{ active: $route.path.startsWith('/admin/sources/resources') }">资源管理</router-link>
      <router-link to="/admin/sources/quality" class="tab" :class="{ active: $route.path.startsWith('/admin/sources/quality') }">质检看板</router-link>
      <router-link to="/admin/sources/settings" class="tab" :class="{ active: $route.path.startsWith('/admin/sources/settings') }">基础配置</router-link>
    </nav>

    <router-view />
  </div>
</template>

<style scoped>
.ds-page { padding: 24px 32px 0; }
.page-head { margin-bottom: 14px; }
.page-head h1 { margin: 0; font-size: 22px; font-weight: 600; color: var(--ink-900); }

.tabs { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--line); }
.tab {
  position: relative; display: inline-flex; align-items: center; padding: 9px 16px 11px;
  font-size: 13px; color: var(--ink-500); text-decoration: none;
}
.tab:hover { color: var(--ink-700); }
.tab.active { color: var(--teal-dark); font-weight: 600; }
.tab.active::after {
  content: ""; position: absolute; left: 10px; right: 10px; bottom: -1px;
  height: 2px; border-radius: 2px 2px 0 0; background: var(--teal);
}
</style>
