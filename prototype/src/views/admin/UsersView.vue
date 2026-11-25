<template>
  <div class="admin-page">
    <!-- 角色页签 -->
    <div class="role-tabs" role="tablist" aria-label="角色筛选">
      <button
        v-for="role in ROLE_LIST"
        :key="role.key"
        class="role-tab"
        :class="{ active: activeRole === role.key }"
        type="button"
        role="tab"
        :aria-selected="activeRole === role.key"
        @click="activeRole = role.key"
      >
        <span class="tab-dot" :style="{ background: role.color }"></span>
        <span class="tab-label">{{ role.label }}</span>
        <span class="tab-count">{{ roleCount(role.key) }}</span>
      </button>
    </div>

    <div class="create-row">
      <button class="btn-primary" type="button" @click="openCreate">＋ 新增用户</button>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="search-wrap">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="searchQuery"
          class="filter-input search-input"
          type="text"
          placeholder="搜索用户名、姓名或邮箱..."
        />
        <button v-if="searchQuery" class="clear-btn" type="button" @click="searchQuery = ''">清除</button>
      </div>
      <div class="toolbar-meta">
        当前页签 <strong>{{ activeRoleMeta.label }}</strong>
        <span class="meta-sep">·</span>
        {{ filteredUsers.length }} / {{ roleCount(activeRole) }} 位
        <span class="role-desc">{{ activeRoleMeta.desc }}</span>
      </div>
    </div>

    <!-- 用户表 -->
    <div class="table-wrap">
      <table class="pool-table user-table">
        <thead>
          <tr>
            <th class="col-user">用户名</th>
            <th class="col-email">邮箱</th>
            <th class="col-role">角色</th>
            <th class="col-status">状态</th>
            <th class="col-time">创建时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in filteredUsers" :key="user.id">
            <td>
              <div class="user-cell">
                <span
                  class="avatar"
                  :style="{
                    background: roleMeta(user.role).color + '18',
                    color: roleMeta(user.role).color,
                  }"
                >
                  {{ avatarText(user) }}
                </span>
                <span class="user-info">
                  <strong>{{ user.name || user.username }}</strong>
                  <small>@{{ user.username }}</small>
                </span>
              </div>
            </td>
            <td class="cell-email" :title="user.email">{{ user.email }}</td>
            <td>
              <span class="badge role-badge" :class="'role-' + user.role">
                {{ roleMeta(user.role).label }}
              </span>
            </td>
            <td>
              <span class="badge" :class="user.status === 'active' ? 'badge-ok' : 'badge-muted'">
                {{ user.status === "active" ? "启用" : "禁用" }}
              </span>
            </td>
            <td class="cell-time">{{ user.created_at }}</td>
            <td class="col-actions">
              <button
                class="btn-sm"
                :class="{ danger: user.status === 'active' }"
                type="button"
                @click="toggleStatus(user)"
              >
                {{ user.status === "active" ? "禁用" : "启用" }}
              </button>
              <button class="btn-sm teal" type="button" @click="resetPassword(user)">
                重置密码
              </button>
            </td>
          </tr>
          <tr v-if="filteredUsers.length === 0">
            <td colspan="6" class="empty-row">
              未找到匹配用户
              <button v-if="searchQuery" class="empty-link" type="button" @click="searchQuery = ''">
                清除搜索
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="page-note">
      角色变更与账号启停即时生效；重置密码将向邮箱发送一次性链接（原型演示，不实际发送）。
    </p>

    <!-- 新增用户弹窗 -->
    <Teleport to="body">
      <transition name="modal-fade">
        <div v-if="modalOpen" class="modal-overlay" @click.self="closeCreate">
          <div class="modal" role="dialog" aria-modal="true" aria-labelledby="new-user-title">
            <header class="modal-head">
              <div>
                <h2 id="new-user-title" class="modal-title">新增用户</h2>
                <p class="modal-sub">创建后可随时调整角色或停用账号</p>
              </div>
              <button class="modal-close" type="button" title="关闭" @click="closeCreate">
                &times;
              </button>
            </header>

            <form class="modal-body" novalidate @submit.prevent="handleSubmit">
              <div class="form-field">
                <label class="form-label" for="new-username">用户名</label>
                <input
                  id="new-username"
                  v-model.trim="form.username"
                  class="form-control"
                  :class="{ invalid: errors.username }"
                  type="text"
                  placeholder="如：zhaolei（拼音，小写）"
                  autocomplete="off"
                />
                <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
              </div>

              <div class="form-field">
                <label class="form-label" for="new-email">邮箱</label>
                <input
                  id="new-email"
                  v-model.trim="form.email"
                  class="form-control"
                  :class="{ invalid: errors.email }"
                  type="email"
                  placeholder="name@tcm-dor.cn"
                  autocomplete="off"
                />
                <span v-if="errors.email" class="field-error">{{ errors.email }}</span>
              </div>

              <div class="form-field">
                <label class="form-label" for="new-password">初始密码</label>
                <div class="password-wrap">
                  <input
                    id="new-password"
                    v-model="form.password"
                    class="form-control"
                    :class="{ invalid: errors.password }"
                    :type="showPassword ? 'text' : 'password'"
                    placeholder="至少 6 位字符"
                    autocomplete="new-password"
                  />
                  <button class="password-toggle" type="button" @click="showPassword = !showPassword">
                    {{ showPassword ? "隐藏" : "显示" }}
                  </button>
                </div>
                <span v-if="errors.password" class="field-error">{{ errors.password }}</span>
              </div>

              <div class="form-field">
                <span class="form-label">角色</span>
                <div class="role-options">
                  <label
                    v-for="role in ROLE_LIST"
                    :key="role.key"
                    class="role-option"
                    :class="{ selected: form.role === role.key }"
                  >
                    <input v-model="form.role" class="sr-only" type="radio" :value="role.key" />
                    <span class="option-head">
                      <span class="option-dot" :style="{ background: role.color }"></span>
                      <strong>{{ role.label }}</strong>
                      <span v-if="form.role === role.key" class="option-check">✓</span>
                    </span>
                    <small>{{ role.desc }}</small>
                  </label>
                </div>
                <span v-if="errors.role" class="field-error">{{ errors.role }}</span>
              </div>

              <footer class="modal-foot">
                <button class="btn-cancel" type="button" @click="closeCreate">取消</button>
                <button class="btn-primary" type="submit">创建用户</button>
              </footer>
            </form>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

const ROLE_LIST = [
  { key: "normal", label: "普通用户", desc: "仅开放智能问答", color: "#6b7280" },
  { key: "professional", label: "专业用户", desc: "问答 / 搜索 / 图谱", color: "#1565c0" },
  { key: "annotator", label: "数据标注员", desc: "标注工作台与提交", color: "#00796b" },
  { key: "admin", label: "超级管理员", desc: "全平台数据治理", color: "#c62828" },
];

const USERS = ref([
  {
    id: "u-001",
    username: "zhangli",
    name: "张丽",
    email: "zhangli@tcm-dor.cn",
    role: "normal",
    status: "active",
    created_at: "2025-01-12 09:20",
  },
  {
    id: "u-002",
    username: "wangfang",
    name: "王芳",
    email: "wangfang@tcm-dor.cn",
    role: "normal",
    status: "active",
    created_at: "2025-01-16 14:05",
  },
  {
    id: "u-003",
    username: "chenxi",
    name: "陈曦",
    email: "chenxi@tcm-dor.cn",
    role: "professional",
    status: "active",
    created_at: "2025-01-20 10:32",
  },
  {
    id: "u-004",
    username: "liuyang",
    name: "刘洋",
    email: "liuyang@tcm-dor.cn",
    role: "professional",
    status: "disabled",
    created_at: "2025-02-02 16:48",
  },
  {
    id: "u-005",
    username: "zhaomin",
    name: "赵敏",
    email: "zhaomin@tcm-dor.cn",
    role: "professional",
    status: "active",
    created_at: "2025-02-08 09:15",
  },
  {
    id: "u-006",
    username: "sunhao",
    name: "孙浩",
    email: "sunhao@tcm-dor.cn",
    role: "annotator",
    status: "active",
    created_at: "2025-02-14 11:27",
  },
  {
    id: "u-007",
    username: "zhoujing",
    name: "周静",
    email: "zhoujing@tcm-dor.cn",
    role: "annotator",
    status: "active",
    created_at: "2025-02-18 15:03",
  },
  {
    id: "u-008",
    username: "wuqi",
    name: "吴琦",
    email: "wuqi@tcm-dor.cn",
    role: "annotator",
    status: "disabled",
    created_at: "2025-02-21 13:36",
  },
  {
    id: "u-009",
    username: "huangwei",
    name: "黄伟",
    email: "huangwei@tcm-dor.cn",
    role: "admin",
    status: "active",
    created_at: "2025-01-02 08:50",
  },
  {
    id: "u-010",
    username: "linshu",
    name: "林舒",
    email: "linshu@tcm-dor.cn",
    role: "admin",
    status: "active",
    created_at: "2025-01-05 09:10",
  },
]);

const activeRole = ref("normal");
const searchQuery = ref("");

const activeRoleMeta = computed(
  () => ROLE_LIST.find((r) => r.key === activeRole.value) || ROLE_LIST[0],
);

const filteredUsers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return USERS.value.filter((user) => {
    if (user.role !== activeRole.value) return false;
    if (!q) return true;
    return [user.username, user.name, user.email]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
});

function roleCount(key) {
  return USERS.value.filter((user) => user.role === key).length;
}

function roleMeta(key) {
  return ROLE_LIST.find((r) => r.key === key) || { label: key, color: "#6b7280" };
}

function avatarText(user) {
  const source = user.name || user.username || "?";
  return source.slice(0, 1).toUpperCase();
}

/* ───────── 行操作 ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;

function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 3000);
}

function toggleStatus(user) {
  user.status = user.status === "active" ? "disabled" : "active";
  showToast(
    `已${user.status === "active" ? "启用" : "禁用"}用户 ${user.username}（mock）`,
    user.status === "active" ? "success" : "error",
  );
}

function resetPassword(user) {
  showToast(`重置密码链接已发送至 ${user.email}（mock）`);
}

/* ───────── 新增用户 ───────── */
const modalOpen = ref(false);
const showPassword = ref(false);
const errors = ref({});
const form = reactive({
  username: "",
  email: "",
  password: "",
  role: "normal",
});

function openCreate() {
  form.username = "";
  form.email = "";
  form.password = "";
  form.role = "normal";
  errors.value = {};
  showPassword.value = false;
  modalOpen.value = true;
  document.body.style.overflow = "hidden";
}

function closeCreate() {
  modalOpen.value = false;
  document.body.style.overflow = "";
}

function validate() {
  const next = {};
  const username = form.username.trim().toLowerCase();
  const email = form.email.trim().toLowerCase();

  if (!username) {
    next.username = "请输入用户名";
  } else if (!/^[a-z][a-z0-9_]{2,19}$/.test(username)) {
    next.username = "3–20 位小写字母、数字或下划线，需字母开头";
  } else if (USERS.value.some((u) => u.username.toLowerCase() === username)) {
    next.username = "该用户名已被占用";
  }

  if (!email) {
    next.email = "请输入邮箱";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    next.email = "邮箱格式不正确";
  }

  if (!form.password) {
    next.password = "请输入初始密码";
  } else if (form.password.length < 6) {
    next.password = "密码至少 6 位字符";
  }

  if (!ROLE_LIST.some((r) => r.key === form.role)) {
    next.role = "请选择角色";
  }

  errors.value = next;
  return Object.keys(next).length === 0;
}

function nowText() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function handleSubmit() {
  if (!validate()) return;

  const username = form.username.trim().toLowerCase();
  USERS.value.unshift({
    id: `u-${Date.now()}`,
    username,
    name: "",
    email: form.email.trim().toLowerCase(),
    role: form.role,
    status: "active",
    created_at: nowText(),
  });

  activeRole.value = form.role;
  const roleLabel = roleMeta(form.role).label;
  closeCreate();
  showToast(`用户 ${username} 已创建，角色：${roleLabel}（mock）`);
}

/* ───────── 快捷键 ───────── */
function handleKeydown(e) {
  if (e.key === "Escape" && modalOpen.value) closeCreate();
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  clearTimeout(toastTimer);
  window.removeEventListener("keydown", handleKeydown);
  document.body.style.overflow = "";
});
</script>

<style scoped>
.admin-page {
  width: 100%;
  min-height: 100%;
  padding: 24px 32px 40px;
  box-sizing: border-box;
}

/* ── 页头 ── */
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.header-text h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}
.header-sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}

/* ── 角色页签 ── */
.role-tabs {
  display: flex;
  align-items: stretch;
  gap: 4px;
  width: fit-content;
  max-width: 100%;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  margin-bottom: 12px;
  overflow-x: auto;
}
.create-row { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.role-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 15px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.16s ease, color 0.16s ease;
}
.role-tab:hover {
  background: #f5f8f7;
  color: var(--ink-700);
}
.role-tab.active {
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-weight: 600;
}
.tab-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  opacity: 0.55;
}
.role-tab.active .tab-dot {
  opacity: 1;
}
.tab-count {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #f1f3f4;
  color: var(--ink-500);
  font-size: 11px;
  font-weight: 600;
  text-align: center;
}
.role-tab.active .tab-count {
  background: #fff;
  color: var(--teal);
}

/* ── 工具栏 ── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 10px;
  width: 15px;
  height: 15px;
  color: var(--ink-400);
  pointer-events: none;
}
.search-input {
  width: 280px;
  padding-left: 33px;
  padding-right: 58px;
  background: #fff;
}
.clear-btn {
  position: absolute;
  right: 5px;
  padding: 3px 7px;
  border: none;
  border-radius: 4px;
  background: #f0f2f3;
  color: var(--ink-500);
  font-size: 11px;
  cursor: pointer;
}
.clear-btn:hover {
  background: #e6e9eb;
}
.toolbar-meta {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-500);
}
.toolbar-meta strong {
  color: var(--ink-700);
  font-weight: 600;
}
.meta-sep {
  color: #cfd4d8;
}
.role-desc {
  margin-left: 6px;
  padding-left: 8px;
  border-left: 1px solid var(--line);
  color: var(--ink-400);
  font-size: 11px;
}

/* ── 表格 ── */
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
}
.user-table {
  min-width: 780px;
}
.user-table th {
  background: #fafbfb;
}
.user-table tbody tr:last-child td {
  border-bottom: none;
}
.col-user {
  width: 210px;
}
.col-email {
  min-width: 210px;
}
.col-role {
  width: 118px;
}
.col-status {
  width: 82px;
}
.col-time {
  width: 138px;
}
.col-actions {
  width: 168px;
  text-align: right;
  white-space: nowrap;
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.user-info strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
}
.user-info small {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  color: var(--ink-400);
}
.cell-email {
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-500);
  font-size: 12px;
}
.cell-time {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  color: var(--ink-400);
  white-space: nowrap;
}
.role-badge {
  font-weight: 500;
}
.role-normal {
  background: #f5f5f5;
  color: #616161;
}
.role-professional {
  background: #e8f1fb;
  color: #1565c0;
}
.role-annotator {
  background: var(--teal-soft);
  color: var(--teal-dark);
}
.role-admin {
  background: #ffebee;
  color: var(--danger);
}

.btn-sm + .btn-sm {
  margin-left: 6px;
}
.btn-sm.danger {
  color: var(--danger);
  border-color: #f0c7c7;
}
.btn-sm.danger:hover {
  background: #fff5f5;
  border-color: var(--danger);
}
.empty-link {
  margin-left: 8px;
  border: none;
  background: transparent;
  color: var(--teal);
  font-size: 13px;
  cursor: pointer;
  text-decoration: underline;
}

.page-note {
  margin: 12px 0 0;
  padding-left: 10px;
  border-left: 3px solid var(--teal-border);
  font-size: 11px;
  line-height: 1.7;
  color: var(--ink-400);
}

/* ── 弹窗 ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(18, 26, 28, 0.44);
  backdrop-filter: blur(2px);
}
.modal {
  width: 520px;
  max-width: 100%;
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 18px 52px rgba(0, 0, 0, 0.24);
  overflow: hidden;
}
.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
  background: #fbfcfc;
}
.modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--ink-900);
}
.modal-sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}
.modal-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-400);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}
.modal-close:hover {
  background: #f0f2f3;
  color: var(--ink-700);
}
.modal-body {
  padding: 18px 20px 0;
  overflow-y: auto;
}
.form-field {
  margin-bottom: 15px;
}
.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700);
}
.form-control {
  width: 100%;
  box-sizing: border-box;
  padding: 9px 11px;
  border: 1px solid #d5d9dc;
  border-radius: 7px;
  font-family: inherit;
  font-size: 13px;
  color: var(--ink-900);
  background: #fff;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.form-control:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(0, 121, 107, 0.08);
}
.form-control.invalid {
  border-color: var(--danger);
}
.form-control.invalid:focus {
  box-shadow: 0 0 0 3px rgba(198, 40, 40, 0.08);
}
.password-wrap {
  position: relative;
}
.password-wrap .form-control {
  padding-right: 58px;
}
.password-toggle {
  position: absolute;
  top: 50%;
  right: 6px;
  transform: translateY(-50%);
  padding: 4px 7px;
  border: none;
  border-radius: 4px;
  background: #f3f5f5;
  color: var(--ink-500);
  font-size: 11px;
  cursor: pointer;
}
.password-toggle:hover {
  color: var(--teal);
}
.field-error {
  display: block;
  margin-top: 5px;
  font-size: 11px;
  color: var(--danger);
}

.role-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.role-option {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 9px 11px;
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.role-option:hover {
  border-color: #b9c6c3;
}
.role-option.selected {
  border-color: var(--teal);
  background: #f4faf9;
  box-shadow: 0 0 0 2px rgba(0, 121, 107, 0.06);
}
.option-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.option-head strong {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-900);
}
.option-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.option-check {
  margin-left: auto;
  color: var(--teal);
  font-size: 11px;
  font-weight: 700;
}
.role-option small {
  padding-left: 13px;
  font-size: 10px;
  color: var(--ink-400);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin: 4px -20px 0;
  padding: 14px 20px;
  border-top: 1px solid var(--line);
  background: #fbfcfc;
}
.btn-cancel {
  padding: 8px 18px;
  border: 1px solid #d5d9dc;
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
}
.btn-cancel:hover {
  background: #f5f6f7;
}

/* ── 过渡 ── */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-active .modal,
.modal-fade-leave-active .modal {
  transition: transform 0.2s ease;
}
.modal-fade-enter-from .modal,
.modal-fade-leave-to .modal {
  transform: translateY(10px) scale(0.98);
}

/* ── toast ── */
.toast {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 2000;
  padding: 12px 18px;
  border-radius: 8px;
  font-size: 13px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  max-width: 420px;
}
.toast-success {
  background: var(--teal);
  color: #fff;
}
.toast-error {
  background: var(--danger);
  color: #fff;
}
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── 响应式 ── */
@media (max-width: 760px) {
  .admin-page {
    padding: 16px;
  }
  .admin-header {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input {
    width: 100%;
  }
  .search-wrap {
    width: 100%;
  }
  .role-tabs {
    gap: 2px;
  }
  .role-tab {
    padding: 8px 10px;
  }
  .role-desc {
    display: none;
  }
  .role-options {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
