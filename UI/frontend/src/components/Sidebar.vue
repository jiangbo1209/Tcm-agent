<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-header">
      <div class="brand-row">
        <div class="brand">
          <div class="brand-mark"></div>
          <span v-if="!isCollapsed" class="brand-name">TCM Agent</span>
        </div>
        <button type="button" class="btn-collapse" :title="isCollapsed ? '展开侧栏' : '收起侧栏'" @click="toggleSidebar">
          <svg v-if="isCollapsed" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
      </div>
      <button class="btn-new-chat" :class="{ compact: isCollapsed }" :title="isCollapsed ? '新建对话' : undefined" @click="handleNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        <span v-if="!isCollapsed">新建对话</span>
      </button>
    </div>

    <nav class="sidebar-nav">
      <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }" :title="isCollapsed ? '对话助手' : undefined">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span v-if="!isCollapsed">对话助手</span>
      </router-link>

      <router-link
        v-if="authStore.isProfessional || authStore.isAdmin"
        to="/search"
        class="nav-item"
        :class="{ active: $route.path.startsWith('/search') }"
        :title="isCollapsed ? '智能搜索' : undefined"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <span v-if="!isCollapsed">智能搜索</span>
      </router-link>

      <router-link
        v-if="authStore.isAdmin"
        to="/admin"
        class="nav-item"
        :class="{ active: $route.path.startsWith('/admin') }"
        :title="isCollapsed ? '数据管理' : undefined"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
        </svg>
        <span v-if="!isCollapsed">数据管理</span>
      </router-link>

    </nav>

    <div v-if="!isCollapsed" class="sidebar-history">
      <div class="history-header">
        <span>历史记录</span>
      </div>
      <div class="history-list">
        <div
          v-for="conv in chatStore.conversations"
          :key="'conv-' + conv.id"
          class="history-item"
          :class="{ active: chatStore.currentConversationId === conv.id }"
          @click="handleSelectConversation(conv.id)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <span class="history-title">{{ conv.title }}</span>
          <button class="btn-delete" @click.stop="handleDeleteConversation(conv.id)" title="删除">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div v-if="chatStore.conversations.length === 0" class="history-empty">
          暂无对话记录
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="user-info">
        <div class="user-avatar">{{ avatarLetter }}</div>
        <span v-if="!isCollapsed" class="user-name">{{ userRoleLabel }}</span>
      </div>
      <button class="btn-logout" :class="{ compact: isCollapsed }" :title="isCollapsed ? '退出' : undefined" @click="handleLogout">
        <span v-if="!isCollapsed">退出</span>
        <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
          <polyline points="16 17 21 12 16 7"></polyline>
          <line x1="21" y1="12" x2="9" y2="12"></line>
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";

const router = useRouter();
const authStore = useAuthStore();
const chatStore = useChatStore();
const isCollapsed = ref(false);

const avatarLetter = computed(() => "U");

const userRoleLabel = computed(() => {
  switch (authStore.user?.role) {
    case "admin": return "管理员";
    case "professional": return "专业用户";
    default: return "普通用户";
  }
});

onMounted(() => {
  chatStore.fetchConversations();
});

async function handleNewChat() {
  await chatStore.newConversation();
  if (router.currentRoute.value.path !== "/") {
    router.push("/");
  }
}

async function handleSelectConversation(id) {
  await chatStore.selectConversation(id);
  if (router.currentRoute.value.path !== "/") {
    router.push("/");
  }
}

async function handleDeleteConversation(id) {
  await chatStore.removeConversation(id);
}

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value;
}

function handleLogout() {
  authStore.logout();
  router.push("/login");
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  color: #e0e0e0;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  transition: width 0.2s ease, min-width 0.2s ease;
}

.sidebar.collapsed {
  width: 68px;
  min-width: 68px;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar.collapsed .sidebar-header {
  padding: 14px 10px;
}

.brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: linear-gradient(135deg, var(--teal), #4db6ac);
}

.brand-name {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.btn-collapse {
  width: 28px;
  height: 28px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  color: #cfd5d7;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-collapse:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.btn-new-chat {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius);
  background: transparent;
  color: #e0e0e0;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.btn-new-chat:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.25);
}

.btn-new-chat.compact {
  width: 42px;
  height: 42px;
  padding: 0;
  margin: 0 auto;
}

.sidebar-nav {
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar.collapsed .sidebar-nav {
  align-items: center;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  color: #b0b0b0;
  font-size: 14px;
  text-decoration: none;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.sidebar.collapsed .nav-item {
  width: 44px;
  height: 44px;
  justify-content: center;
  padding: 0;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.nav-item.active {
  background: rgba(0, 121, 107, 0.25);
  color: #4db6ac;
}

.sidebar-history {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.history-header {
  padding: 12px 16px 8px;
  font-size: 12px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #b0b0b0;
  transition: background-color 0.2s ease;
}

.history-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.history-item.active {
  background: rgba(0, 121, 107, 0.2);
  color: #4db6ac;
}

.history-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-delete {
  display: none;
  border: none;
  background: transparent;
  color: #888;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
}

.history-item:hover .btn-delete {
  display: flex;
}

.btn-delete:hover {
  color: #ef5350;
  background: rgba(239, 83, 80, 0.15);
}

.history-empty {
  padding: 16px;
  text-align: center;
  font-size: 13px;
  color: #666;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar.collapsed .sidebar-footer {
  padding: 10px;
  flex-direction: column;
  gap: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar.collapsed .user-info {
  justify-content: center;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--teal), #4db6ac);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.user-name {
  font-size: 13px;
  color: #b0b0b0;
}

.btn-logout {
  border: none;
  background: transparent;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.2s ease;
}

.btn-logout.compact {
  width: 34px;
  height: 34px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-logout:hover {
  color: #ef5350;
}
</style>
