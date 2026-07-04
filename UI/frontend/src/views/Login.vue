<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark"></div>
        <h1>TCM Agent</h1>
      </div>
      <p class="auth-subtitle">中医文献与病案智能平台</p>

      <form @submit.prevent="handleLogin" class="auth-form">
        <div class="form-group">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            class="input-field"
            placeholder="请输入用户名"
            required
          />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            class="input-field"
            placeholder="请输入密码"
            required
          />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" class="btn-primary auth-btn" :disabled="loading">
          {{ loading ? "登录中..." : "登录" }}
        </button>
      </form>

      <p class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { login } from "../api/auth";

const router = useRouter();
const authStore = useAuthStore();

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function handleLogin() {
  error.value = "";
  loading.value = true;
  try {
    const { data } = await login(username.value, password.value);
    const token = data.access_token;

    const payload = JSON.parse(atob(token.split(".")[1]));
    const user = { id: payload.sub, role: payload.role };

    authStore.setAuth(token, user);
    router.push(user.role === "admin" ? "/admin" : "/");
  } catch (e) {
    error.value = e.response?.data?.error || "登录失败，请重试";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background:
    radial-gradient(900px 420px at 90% -10%, rgba(15, 93, 92, 0.08), transparent 60%),
    linear-gradient(180deg, #ffffff, #f5f7f8);
}

.auth-card {
  width: 400px;
  padding: 40px;
  background: var(--panel);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.auth-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.brand-mark {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(135deg, var(--teal), var(--teal-deep));
}

.auth-brand h1 {
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}

.auth-subtitle {
  color: var(--ink-500);
  font-size: 14px;
  margin-bottom: 28px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-700);
}

.auth-btn {
  width: 100%;
  padding: 12px;
  margin-top: 4px;
}

.auth-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--ink-500);
}
</style>
