<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="brand">
        <div class="brand-mark"></div>
        <span class="brand-name">TCM Agent</span>
      </div>
      <button class="btn-new-chat" @click="handleNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        新建对话
      </button>
    </div>

    <nav class="sidebar-nav">
      <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        对话助手
      </router-link>

      <router-link
        v-if="authStore.isProfessional"
        to="/search"
        class="nav-item"
        :class="{ active: $route.path.startsWith('/search') }"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        智能搜索
      </router-link>
    </nav>

    <div class="sidebar-history">
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
        <span class="user-name">{{ authStore.user?.role === 'professional' ? '专业用户' : '普通用户' }}</span>
      </div>
      <button class="btn-logout" @click="handleLogout">退出</button>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";

const router = useRouter();
const authStore = useAuthStore();
const chatStore = useChatStore();

const avatarLetter = computed(() => "U");

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
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
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

.sidebar-nav {
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
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

.btn-logout:hover {
  color: #ef5350;
}
</style>
