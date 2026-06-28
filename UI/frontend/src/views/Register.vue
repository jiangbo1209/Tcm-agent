<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark"></div>
        <h1>TCM Agent</h1>
      </div>
      <p class="auth-subtitle">创建新账号</p>

      <form @submit.prevent="handleRegister" class="auth-form">
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
          <label>邮箱</label>
          <input
            v-model="email"
            type="email"
            class="input-field"
            placeholder="请输入邮箱"
            required
          />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            class="input-field"
            placeholder="请输入密码（至少6位）"
            minlength="6"
            required
          />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" class="btn-primary auth-btn" :disabled="loading">
          {{ loading ? "注册中..." : "注册" }}
        </button>
      </form>

      <p class="auth-footer">
        已有账号？<router-link to="/login">立即登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { register } from "../api/auth";

const router = useRouter();

const username = ref("");
const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function handleRegister() {
  error.value = "";
  loading.value = true;
  try {
    await register(username.value, email.value, password.value);
    router.push("/login");
  } catch (e) {
    error.value = e.response?.data?.error || "注册失败，请重试";
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
