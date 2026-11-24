<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark"></div>
        <div>
          <h1>TCM-DOR 知识图谱原型</h1>
          <p>卵巢储备功能减退（DOR）文献与病案数据平台</p>
        </div>
      </div>

      <p class="pick-hint">选择角色进入原型（纯前端演示，无需账号密码）</p>

      <div class="role-grid">
        <button
          v-for="(meta, key) in ROLE_META"
          :key="key"
          class="role-card"
          :style="{ '--role-color': meta.color }"
          @click="enter(key)"
        >
          <span class="role-badge">{{ meta.label }}</span>
          <span class="role-desc">{{ meta.desc }}</span>
          <span class="role-enter">进入 →</span>
        </button>
      </div>

      <div class="login-foot">
        <span>原型说明：所有数据为本地 mock，不连接后端</span>
        <span>字段依据《DOR 文献库母版》65 + 41 列</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { session, ROLE_META } from "../stores/session";

const router = useRouter();

function enter(role) {
  session.login(role);
  router.push(ROLE_META[role].home);
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(1200px 600px at 15% 0%, #e6f4f1 0%, transparent 60%),
    radial-gradient(900px 500px at 100% 100%, #eef2ff 0%, transparent 55%),
    #f7f9f9;
}
.login-card { width: 720px; max-width: 100%; background: #fff; border: 1px solid var(--line); border-radius: 18px; padding: 34px 38px 26px; box-shadow: 0 24px 60px rgba(20, 60, 55, 0.08); }
.brand { display: flex; align-items: center; gap: 14px; margin-bottom: 26px; }
.brand-mark { width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #00a896, #00796b); flex-shrink: 0; }
.brand h1 { margin: 0 0 4px; font-size: 21px; color: var(--ink-900); }
.brand p { margin: 0; font-size: 12px; color: var(--ink-400); }

.pick-hint { font-size: 12px; color: var(--ink-500); margin: 0 0 14px; }

.role-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.role-card {
  text-align: left;
  border: 1px solid var(--line);
  border-left: 4px solid var(--role-color);
  border-radius: 10px;
  padding: 14px 16px;
  background: #fff;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.role-card:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(20, 60, 55, 0.1); border-color: var(--role-color); }
.role-badge { font-size: 14px; font-weight: 600; color: var(--ink-900); }
.role-desc { font-size: 11px; color: var(--ink-400); }
.role-enter { margin-top: 6px; font-size: 11px; color: var(--role-color); font-weight: 600; }

.login-foot { display: flex; justify-content: space-between; gap: 10px; margin-top: 24px; padding-top: 14px; border-top: 1px dashed var(--line); font-size: 10px; color: var(--ink-400); }
</style>
