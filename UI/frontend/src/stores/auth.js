import { defineStore } from "pinia";
import { ref, computed } from "vue";

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
  const isAdmin = computed(() => user.value?.role === "admin");
  const isAnnotator = computed(() => user.value?.role === "annotator");

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

  return { token, user, isLoggedIn, isProfessional, isAdmin, isAnnotator, setAuth, logout };
});
