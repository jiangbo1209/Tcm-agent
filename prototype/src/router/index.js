import { createRouter, createWebHistory } from "vue-router";
import { session } from "../stores/session";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    meta: { public: true },
  },
  {
    path: "/",
    component: () => import("../components/AppShell.vue"),
    redirect: "/chat",
    children: [
      {
        path: "chat",
        name: "Chat",
        component: () => import("../views/chat/ChatView.vue"),
        meta: { roles: ["normal", "professional"] },
      },
      {
        path: "search",
        name: "Search",
        component: () => import("../views/professional/SearchView.vue"),
        meta: { roles: ["professional"] },
      },
      {
        path: "graph",
        name: "Graph",
        component: () => import("../views/professional/GraphView.vue"),
        meta: { roles: ["professional"] },
      },
      {
        path: "annotate",
        name: "Annotate",
        component: () => import("../views/annotator/WorkbenchView.vue"),
        meta: { roles: ["annotator"] },
      },
      {
        path: "admin",
        name: "AdminDashboard",
        component: () => import("../views/admin/DashboardView.vue"),
        meta: { roles: ["admin"] },
      },
      {
        path: "admin/data",
        name: "AdminDataManage",
        component: () => import("../views/admin/DataManageView.vue"),
        meta: { roles: ["admin"] },
      },
      // 兼容旧入口
      { path: "admin/literature", redirect: "/admin/data?kind=literature" },
      { path: "admin/cases", redirect: "/admin/data?kind=case" },
      {
        path: "admin/upload",
        name: "AdminUpload",
        component: () => import("../views/admin/UploadView.vue"),
        meta: { roles: ["admin"] },
      },
      {
        path: "admin/users",
        name: "AdminUsers",
        component: () => import("../views/admin/UsersView.vue"),
        meta: { roles: ["admin"] },
      },
      {
        path: "admin/tasks",
        name: "AdminTasks",
        component: () => import("../views/admin/AnnotationTasksView.vue"),
        meta: { roles: ["admin"] },
      },
      {
        path: "admin/etl",
        name: "AdminEtl",
        component: () => import("../views/admin/EtlView.vue"),
        meta: { roles: ["admin"] },
      },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/login" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  if (to.meta.public) {
    return true;
  }
  if (!session.isLoggedIn.value) {
    return "/login";
  }
  const allowed = to.meta.roles;
  if (Array.isArray(allowed) && !allowed.includes(session.state.role)) {
    return "/login";
  }
  if (to.path === "/") {
    return session.state.role === "admin"
      ? "/admin"
      : session.state.role === "annotator"
        ? "/annotate"
        : "/chat";
  }
  return true;
});

export default router;
