import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const ROLE_LABELS = {
  normal: "普通用户",
  professional: "专业用户",
  annotator: "数据标注员",
  admin: "超级管理员",
  super_admin: "超级管理员",
};

export const useAuthStore = defineStore("auth", () => {
  const storedToken = localStorage.getItem("token") || "";
  let storedUser = null;
  try {
    storedUser = JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    storedUser = null;
  }
  if (!storedToken || !storedUser) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }

  const token = ref(storedToken && storedUser ? storedToken : "");
  const user = ref(storedToken && storedUser ? storedUser : null);

  const isLoggedIn = computed(() => !!token.value);
  const isProfessional = computed(() => user.value?.role === "professional");
  // 四角色体系：normal / professional / annotator / super_admin（存量数据值为 admin）
  const isSuperAdmin = computed(
    () => user.value?.role === "admin" || user.value?.role === "super_admin",
  );
  const isAdmin = computed(() => isSuperAdmin.value);
  const isAnnotator = computed(() => user.value?.role === "annotator");
  const roleLabel = computed(() => ROLE_LABELS[user.value?.role] || user.value?.role || "");

  function setAuth(tokenValue, userValue) {
    token.value = tokenValue;
    user.value = userValue;
    localStorage.setItem("token", tokenValue);
    localStorage.setItem("user", JSON.stringify(userValue));
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }

  return { token, user, isLoggedIn, isProfessional, isAdmin, isSuperAdmin, isAnnotator, roleLabel, setAuth, logout };
});
