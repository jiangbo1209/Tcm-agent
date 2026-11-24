<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"></div>
        <div class="brand-text">
          <strong>TCM-DOR</strong>
          <span>知识图谱原型</span>
        </div>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="role-card">
          <span class="role-dot" :style="{ background: roleMeta.color }"></span>
          <div class="role-text">
            <strong>{{ roleMeta.label }}</strong>
            <span>{{ roleMeta.desc }}</span>
          </div>
        </div>
        <button class="btn-switch" @click="switchRole">切换角色</button>
      </div>
    </aside>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { session, ROLE_META } from "../stores/session";

const route = useRoute();
const router = useRouter();

const roleMeta = computed(() => ROLE_META[session.state.role] || ROLE_META.normal);

const ICONS = {
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  graph: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="5" cy="12" r="3"/><circle cx="19" cy="5" r="3"/><circle cx="19" cy="19" r="3"/><line x1="8" y1="11" x2="16" y2="6"/><line x1="8" y1="13" x2="16" y2="18"/></svg>',
  annotate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  case: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"/><path d="M9 7h6M9 11h6M9 15h4"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  tasks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  etl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
};

const NAV = {
  normal: [{ to: "/chat", label: "智能问答", icon: "chat" }],
  professional: [
    { to: "/chat", label: "智能问答", icon: "chat" },
    { to: "/search", label: "智能搜索", icon: "search" },
    { to: "/graph", label: "知识图谱", icon: "graph" },
  ],
  annotator: [{ to: "/annotate", label: "标注工作台", icon: "annotate" }],
  admin: [
    { to: "/admin", label: "平台总览", icon: "dashboard" },
    { to: "/admin/sources", label: "数据源管理", icon: "upload" },
    { to: "/admin/etl", label: "ETL管理", icon: "etl" },
    { to: "/admin/data", label: "数据管理", icon: "book" },
    { to: "/admin/tasks", label: "标注管理", icon: "tasks" },
    { to: "/admin/users", label: "用户管理", icon: "users" },
  ],
};

const navItems = computed(() =>
  (NAV[session.state.role] || []).map((i) => ({ ...i, icon: ICONS[i.icon] })),
);

function isActive(to) {
  if (to === "/admin") return route.path === "/admin";
  return route.path === to || route.path.startsWith(to + "/");
}

function switchRole() {
  session.logout();
  router.push("/login");
}
</script>

<style scoped>
.shell { display: flex; height: 100vh; overflow: hidden; }

.sidebar {
  width: 232px;
  flex-shrink: 0;
  background: var(--sidebar);
  color: var(--sidebar-ink);
  display: flex;
  flex-direction: column;
  padding: 18px 12px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 18px; }
.brand-mark { width: 28px; height: 28px; border-radius: 8px; background: linear-gradient(135deg, #00a896, #00796b); }
.brand-text { display: flex; flex-direction: column; line-height: 1.2; }
.brand-text strong { color: #fff; font-size: 14px; letter-spacing: 0.5px; }
.brand-text span { font-size: 10px; color: #7f8c9b; }

.nav { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  color: #aab4c0;
  text-decoration: none;
  font-size: 13px;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover { background: rgba(255, 255, 255, 0.06); color: #fff; }
.nav-item.active { background: rgba(0, 121, 107, 0.22); color: #7ff0df; }
.nav-icon { width: 16px; height: 16px; display: inline-flex; }
.nav-icon :deep(svg) { width: 16px; height: 16px; }

.sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.role-card { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.05); }
.role-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.role-text { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
.role-text strong { color: #fff; font-size: 12px; font-weight: 600; }
.role-text span { color: #8494a3; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.btn-switch { border: 1px solid rgba(255, 255, 255, 0.16); background: transparent; color: #c9d1d9; border-radius: 6px; padding: 6px; font-size: 12px; cursor: pointer; }
.btn-switch:hover { border-color: #7ff0df; color: #7ff0df; }

.main { flex: 1; min-width: 0; overflow-y: auto; background: var(--bg); }
</style>
