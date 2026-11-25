<template>
  <div class="shell">
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="brand">
        <div class="brand-mark"></div>
        <div v-if="!isCollapsed" class="brand-text">
          <strong>TCM-DOR</strong>
          <span>知识图谱原型</span>
        </div>
        <button
          class="btn-collapse"
          :title="isCollapsed ? '展开侧栏' : '折叠侧栏'"
          @click="toggleCollapse"
        >
          <svg v-if="isCollapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
          :title="isCollapsed ? item.label : undefined"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span v-if="!isCollapsed">{{ item.label }}</span>
        </router-link>
      </nav>

      <div v-if="showChatHistory && !isCollapsed" class="chat-history">
        <div class="ch-head">
          <span>对话历史</span>
          <button class="ch-new" type="button" title="新建对话" @click="newChat">＋</button>
        </div>
        <div class="ch-scroll">
          <div v-for="group in grouped" :key="group.label" class="ch-group">
            <div v-if="group.items.length" class="ch-group-label">{{ group.label }}</div>
            <button
              v-for="conv in group.items"
              :key="conv.id"
              class="ch-item"
              :class="{ active: route.path === '/chat' && conv.id === chatStore.state.activeId }"
              type="button"
              :title="conv.title"
              @click="selectChat(conv.id)"
            >
              <span class="ch-title">{{ conv.title }}</span>
              <span class="ch-del" title="删除" @click.stop="deleteChat(conv.id)">×</span>
            </button>
          </div>
          <p v-if="chatStore.conversations.length === 0" class="ch-empty">暂无对话</p>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="role-card" :title="isCollapsed ? roleMeta.label : undefined">
          <span class="role-dot" :style="{ background: roleMeta.color }"></span>
          <div v-if="!isCollapsed" class="role-text">
            <strong>{{ roleMeta.label }}</strong>
            <span>{{ roleMeta.desc }}</span>
          </div>
        </div>
        <button class="btn-switch" :title="isCollapsed ? '切换角色' : undefined" @click="switchRole">
          <span v-if="!isCollapsed">切换角色</span>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 1l4 4-4 4" /><path d="M3 11V9a4 4 0 0 1 4-4h14" />
            <path d="M7 23l-4-4 4-4" /><path d="M21 13v2a4 4 0 0 1-4 4H3" />
          </svg>
        </button>
      </div>
    </aside>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { session, ROLE_META } from "../stores/session";
import { chatStore } from "../stores/chat";

const route = useRoute();
const router = useRouter();

const roleMeta = computed(() => ROLE_META[session.state.role] || ROLE_META.normal);
const showChatHistory = computed(() =>
  ["normal", "professional"].includes(session.state.role),
);
const grouped = computed(() => {
  const g = chatStore.group();
  return [
    { label: "今天", items: g.today },
    { label: "昨天", items: g.yesterday },
    { label: "更早", items: g.earlier },
  ];
});

function newChat() {
  chatStore.create([]);
  router.push("/chat");
}

function selectChat(id) {
  chatStore.select(id);
  router.push("/chat");
}

function deleteChat(id) {
  chatStore.remove(id);
  if (chatStore.conversations.length === 0) chatStore.create([]);
  if (route.path !== "/chat") router.push("/chat");
}

const COLLAPSE_KEY = "tcm-dor-proto-sidebar-collapsed";
const isCollapsed = ref(false);
try {
  isCollapsed.value = localStorage.getItem(COLLAPSE_KEY) === "1";
} catch {
  isCollapsed.value = false;
}
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value;
  try {
    localStorage.setItem(COLLAPSE_KEY, isCollapsed.value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

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
  annotator: [
    { to: "/annotate", label: "标注工作台", icon: "annotate" },
    { to: "/annotate/tasks", label: "任务领取", icon: "tasks" },
  ],
  admin: [
    { to: "/admin", label: "平台总览", icon: "dashboard" },
    { to: "/admin/sources", label: "数据源管理", icon: "upload" },
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
  transition: width 0.18s ease, padding 0.18s ease;
  overflow: hidden;
  background: var(--sidebar);
  color: var(--sidebar-ink);
  display: flex;
  flex-direction: column;
  padding: 18px 12px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 18px; }
.btn-collapse { margin-left: auto; width: 24px; height: 24px; border: 1px solid rgba(255,255,255,.14); background: transparent; color: #9fb0c0; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.btn-collapse:hover { color: #7ff0df; border-color: #7ff0df; }
.btn-collapse svg { width: 14px; height: 14px; }
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

.chat-history { flex: 1; min-height: 0; display: flex; flex-direction: column; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.08); }
.ch-head { display: flex; align-items: center; justify-content: space-between; padding: 0 6px 6px; font-size: 11px; color: #7f8c9b; }
.ch-new { width: 20px; height: 20px; border: 1px solid rgba(255,255,255,0.14); border-radius: 5px; background: transparent; color: #c9d1d9; cursor: pointer; font-size: 12px; line-height: 1; }
.ch-new:hover { color: #7ff0df; border-color: #7ff0df; }
.ch-scroll { flex: 1; overflow-y: auto; }
.ch-group { margin-bottom: 8px; }
.ch-group-label { padding: 4px 8px; font-size: 10px; color: #6b7885; }
.ch-item {
  position: relative; display: flex; align-items: center; width: 100%;
  padding: 6px 22px 6px 8px; border: none; border-radius: 6px;
  background: transparent; color: #aab4c0; cursor: pointer; text-align: left;
}
.ch-item:hover { background: rgba(255,255,255,0.06); color: #fff; }
.ch-item.active { background: rgba(0,121,107,0.22); color: #7ff0df; }
.ch-title { flex: 1; min-width: 0; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ch-del { position: absolute; right: 4px; width: 16px; height: 16px; line-height: 14px; text-align: center; border-radius: 4px; color: #6b7885; font-size: 12px; opacity: 0; }
.ch-item:hover .ch-del { opacity: 1; }
.ch-del:hover { background: rgba(198,40,40,0.25); color: #ff8a80; }
.ch-empty { margin: 10px 8px; font-size: 11px; color: #6b7885; }

.sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 12px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; }
.role-card { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.05); }
.role-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.role-text { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
.role-text strong { color: #fff; font-size: 12px; font-weight: 600; }
.role-text span { color: #8494a3; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.btn-switch svg { width: 14px; height: 14px; }

/* 折叠态 */
.sidebar.collapsed { width: 64px; padding-left: 8px; padding-right: 8px; }
.sidebar.collapsed .brand { justify-content: center; padding-left: 0; padding-right: 0; }
.sidebar.collapsed .brand-mark { width: 24px; height: 24px; border-radius: 7px; }
.sidebar.collapsed .btn-collapse { margin-left: 4px; }
.sidebar.collapsed .nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
.sidebar.collapsed .nav-icon { width: 18px; height: 18px; }
.sidebar.collapsed .nav-icon :deep(svg) { width: 18px; height: 18px; }
.sidebar.collapsed .role-card { justify-content: center; padding-left: 0; padding-right: 0; }
.sidebar.collapsed .btn-switch { display: flex; align-items: center; justify-content: center; padding: 6px 0; }
.btn-switch { border: 1px solid rgba(255, 255, 255, 0.16); background: transparent; color: #c9d1d9; border-radius: 6px; padding: 6px; font-size: 12px; cursor: pointer; }
.btn-switch:hover { border-color: #7ff0df; color: #7ff0df; }

.main { flex: 1; min-width: 0; overflow-y: auto; background: var(--bg); }
</style>
