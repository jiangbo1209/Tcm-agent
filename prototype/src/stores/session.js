import { reactive, computed } from "vue";

/**
 * 纯前端原型会话：角色来自登录页选择，持久化到 localStorage。
 * 无后端、无 token、无 API。
 */
export const ROLE_META = {
  normal: { label: "普通用户", desc: "智能问答", home: "/chat", color: "#00796b" },
  professional: { label: "专业用户", desc: "智能问答 · 智能搜索 · 知识图谱", home: "/chat", color: "#1565c0" },
  annotator: { label: "数据标注员", desc: "标注工作台", home: "/annotate", color: "#6a1b9a" },
  admin: { label: "超级管理员", desc: "用户权限 · 标注任务 · 数据管理", home: "/admin", color: "#b86a00" },
};

const STORAGE_KEY = "tcm-dor-proto-role";

function readRole() {
  try {
    const role = localStorage.getItem(STORAGE_KEY);
    return ROLE_META[role] ? role : "";
  } catch {
    return "";
  }
}

const state = reactive({
  role: readRole(),
  username: readRole() ? "demo_" + readRole() : "",
});

export const session = {
  state,
  isLoggedIn: computed(() => !!state.role),
  roleLabel: computed(() => ROLE_META[state.role]?.label || ""),
  login(role) {
    if (!ROLE_META[role]) return;
    state.role = role;
    state.username = "demo_" + role;
    try {
      localStorage.setItem(STORAGE_KEY, role);
    } catch {
      /* ignore */
    }
  },
  logout() {
    state.role = "";
    state.username = "";
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  },
};
