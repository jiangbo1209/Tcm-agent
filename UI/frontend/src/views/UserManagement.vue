<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>成员管理</h1>
      <button class="btn-create" @click="showCreate = true">添加成员</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="user-table-wrap">
      <table class="user-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id" :class="{ 'row-admin': user.role === 'admin' }">
            <td>{{ user.id }}</td>
            <td class="cell-username">{{ user.username }}</td>
            <td>{{ user.email }}</td>
            <td>
              <span class="role-badge" :class="'role-' + user.role">{{ roleLabel(user.role) }}</span>
            </td>
            <td>
              <span :class="user.is_active ? 'status-active' : 'status-inactive'">
                {{ user.is_active ? '正常' : '禁用' }}
              </span>
            </td>
            <td class="cell-time">{{ formatDate(user.created_at) }}</td>
            <td class="cell-actions">
              <template v-if="user.role !== 'admin'">
                <select
                  class="role-select"
                  :value="user.role"
                  @change="changeRole(user.id, $event.target.value)"
                >
                  <option value="normal">普通用户</option>
                  <option value="professional">专业用户</option>
                </select>
                <button class="btn-sm btn-reset" @click="openResetPwd(user)">重置密码</button>
                <button class="btn-sm btn-delete" @click="confirmDelete(user)">删除</button>
              </template>
              <span v-else class="admin-hint">无法修改管理员账号</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal-box">
        <div class="modal-header">
          <h2>添加成员</h2>
          <button class="modal-close" @click="showCreate = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-field">
            <label>用户名</label>
            <input v-model="form.username" type="text" placeholder="用户名" />
          </div>
          <div class="form-field">
            <label>邮箱</label>
            <input v-model="form.email" type="email" placeholder="邮箱" />
          </div>
          <div class="form-field">
            <label>密码</label>
            <input v-model="form.password" type="text" placeholder="密码" />
          </div>
          <div class="form-field">
            <label>角色</label>
            <select v-model="form.role">
              <option value="normal">普通用户</option>
              <option value="professional">专业用户</option>
            </select>
          </div>
          <p v-if="formError" class="form-error">{{ formError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="showCreate = false">取消</button>
          <button class="btn-save" :disabled="creating" @click="handleCreate">{{ creating ? '创建中...' : '创建' }}</button>
        </div>
      </div>
    </div>

    <div v-if="resetTarget" class="modal-overlay" @click.self="resetTarget = null">
      <div class="modal-box modal-sm">
        <div class="modal-header">
          <h2>重置密码 — {{ resetTarget.username }}</h2>
          <button class="modal-close" @click="resetTarget = null">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-field">
            <label>新密码</label>
            <input v-model="resetPassword" type="text" placeholder="输入新密码" />
          </div>
          <p v-if="resetError" class="form-error">{{ resetError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="resetTarget = null">取消</button>
          <button class="btn-save" :disabled="resetting" @click="handleResetPwd">{{ resetting ? '重置中...' : '确认重置' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { fetchUsers, createUser, updateUserRole, resetUserPassword, deleteUser } from "../api/users";

const users = ref([]);
const loading = ref(false);

const showCreate = ref(false);
const form = ref({ username: "", email: "", password: "", role: "normal" });
const formError = ref("");
const creating = ref(false);

const resetTarget = ref(null);
const resetPassword = ref("");
const resetError = ref("");
const resetting = ref(false);

function roleLabel(role) {
  return { admin: "管理员", professional: "专业用户", normal: "普通用户" }[role] || role;
}

function formatDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

async function loadUsers() {
  loading.value = true;
  try {
    const res = await fetchUsers();
    users.value = res.data.users;
  } catch (e) {
    console.error("Failed to load users:", e);
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  formError.value = "";
  const { username, email, password, role } = form.value;
  if (!username.trim() || !email.trim() || !password.trim()) {
    formError.value = "所有字段均为必填";
    return;
  }
  creating.value = true;
  try {
    await createUser({ username: username.trim(), email: email.trim(), password: password.trim(), role });
    showCreate.value = false;
    form.value = { username: "", email: "", password: "", role: "normal" };
    await loadUsers();
  } catch (e) {
    formError.value = e.response?.data?.detail || "创建失败";
  } finally {
    creating.value = false;
  }
}

async function changeRole(userId, newRole) {
  try {
    await updateUserRole(userId, newRole);
    await loadUsers();
  } catch (e) {
    alert(e.response?.data?.detail || "修改角色失败");
    await loadUsers();
  }
}

function openResetPwd(user) {
  resetTarget.value = user;
  resetPassword.value = "";
  resetError.value = "";
}

async function handleResetPwd() {
  resetError.value = "";
  if (!resetPassword.value.trim()) {
    resetError.value = "密码不能为空";
    return;
  }
  resetting.value = true;
  try {
    await resetUserPassword(resetTarget.value.id, resetPassword.value.trim());
    resetTarget.value = null;
  } catch (e) {
    resetError.value = e.response?.data?.detail || "重置失败";
  } finally {
    resetting.value = false;
  }
}

async function confirmDelete(user) {
  if (!confirm(`确定删除用户 "${user.username}" 吗？此操作不可撤销。`)) return;
  try {
    await deleteUser(user.id);
    await loadUsers();
  } catch (e) {
    alert(e.response?.data?.detail || "删除失败");
  }
}

onMounted(loadUsers);
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; }

.admin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.admin-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }
.btn-create { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-create:hover { background: #00695c; }

.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

.user-table-wrap { overflow-x: auto; }
.user-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.user-table th { text-align: left; padding: 10px 12px; background: #f5f5f5; color: #666; font-weight: 500; border-bottom: 2px solid #e0e0e0; white-space: nowrap; }
.user-table td { padding: 10px 12px; border-bottom: 1px solid #eee; color: #333; vertical-align: middle; }
.user-table tr:hover { background: #fafafa; }
.user-table .row-admin { background: #f8f9fa; }
.cell-username { font-weight: 500; }
.cell-time { color: #888; font-size: 12px; white-space: nowrap; }
.cell-actions { white-space: nowrap; display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; }

.role-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.role-admin { background: #ede7f6; color: #5e35b1; }
.role-professional { background: #e0f2f1; color: #00796b; }
.role-normal { background: #f5f5f5; color: #666; }

.status-active { color: #2e7d32; }
.status-inactive { color: #c62828; }

.role-select { padding: 3px 6px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; background: #fff; }

.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; cursor: pointer; background: #fff; }
.btn-reset { color: #00796b; border-color: #b2dfdb; }
.btn-reset:hover { background: #e0f2f1; }
.btn-delete { color: #c62828; border-color: #ef9a9a; }
.btn-delete:hover { background: #ffebee; }

.admin-hint { font-size: 12px; color: #999; font-style: italic; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; width: 440px; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.modal-sm { width: 360px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #e8e8e8; }
.modal-header h2 { font-size: 16px; font-weight: 600; margin: 0; }
.modal-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #999; cursor: pointer; border-radius: 4px; }
.modal-close:hover { background: #f0f0f0; color: #333; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid #e8e8e8; }

.form-field { margin-bottom: 14px; }
.form-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.form-field input, .form-field select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; }
.form-field input:focus, .form-field select:focus { border-color: #00796b; }
.form-error { color: #c62828; font-size: 12px; margin: 8px 0 0; }

.btn-cancel { padding: 8px 20px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; color: #666; }
.btn-cancel:hover { background: #f0f0f0; }
.btn-save { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-save:hover { background: #00695c; }
.btn-save:disabled { opacity: 0.6; cursor: default; }
</style>
