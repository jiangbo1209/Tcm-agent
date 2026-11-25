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
        path: "annotate/tasks",
        name: "AnnotateTasks",
        component: () => import("../views/annotator/ClaimTasksView.vue"),
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
        path: "admin/sources",
        component: () => import("../views/admin/datasource/DataSourceLayout.vue"),
        meta: { roles: ["admin"] },
        redirect: "/admin/sources/resources",
        children: [
          { path: "resources", name: "DataSourceResources", component: () => import("../views/admin/datasource/DataSourceResourceView.vue") },
          { path: "quality", name: "DataSourceQuality", component: () => import("../views/admin/EtlQualityView.vue") },
          { path: "settings", name: "DataSourceSettings", component: () => import("../views/admin/etl/EtlSettingsView.vue") },
        ],
      },
      // 兼容旧入口
      { path: "admin/upload", redirect: "/admin/sources" },
      { path: "admin/etl", redirect: "/admin/sources" },
      { path: "admin/etl/resources", redirect: "/admin/sources/resources" },
      { path: "admin/etl/quality", redirect: "/admin/sources/quality" },
      { path: "admin/etl/settings", redirect: "/admin/sources/settings" },
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
