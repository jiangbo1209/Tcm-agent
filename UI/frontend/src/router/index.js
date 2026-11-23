import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/auth/Login.vue"),
    meta: { guest: true },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("../views/auth/Register.vue"),
    meta: { guest: true },
  },
  {
    path: "/",
    component: () => import("../components/Layout.vue"),
    meta: { requiresAuth: true },
    children: [
      {
        path: "",
        name: "Chat",
        component: () => import("../views/chat/Chat.vue"),
      },
      {
        path: "search",
        name: "Search",
        component: () => import("../views/professional/search/Search.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "search/results",
        name: "SearchResults",
        component: () => import("../views/professional/search/SearchResults.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "graph",
        name: "Graph",
        component: () => import("../views/professional/graph/Graph.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "admin",
        name: "Admin",
        component: () => import("../views/admin/data/DataEdit.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "admin/dor/literature",
        name: "AdminDorLiterature",
        component: () => import("../views/admin/dor/LiteratureLibrary.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "admin/dor/cases",
        name: "AdminDorCases",
        component: () => import("../views/admin/dor/CaseLibrary.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "admin/etl",
        name: "AdminEtlQuality",
        component: () => import("../views/admin/etl/QualityDashboard.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "users",
        name: "Users",
        component: () => import("../views/admin/users/UserManagement.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "annotate",
        name: "AnnotateWorkbench",
        component: () => import("../views/annotator/Workbench.vue"),
        meta: { requiresAnnotator: true },
      },
      {
        path: "annotate/history",
        name: "AnnotationHistory",
        component: () => import("../views/annotator/HistoryView.vue"),
        meta: { requiresAnnotator: true },
      },
      {
        path: "admin/annotation",
        name: "AdminAnnotation",
        component: () => import("../views/admin/annotation/AnnotationLayout.vue"),
        meta: { requiresAdmin: true },
        redirect: { name: "AnnotationPools" },
        children: [
          {
            path: "pools",
            name: "AnnotationPools",
            component: () => import("../views/admin/annotation/PoolManageView.vue"),
          },
          {
            path: "review",
            name: "AnnotationReview",
            component: () => import("../views/admin/annotation/ReviewQueueView.vue"),
          },
          {
            path: "board",
            name: "AnnotationBoard",
            component: () => import("../views/admin/annotation/BoardView.vue"),
          },
          {
            path: "export",
            name: "AnnotationExport",
            component: () => import("../views/admin/annotation/ExportView.vue"),
          },
          {
            path: "logs",
            name: "AnnotationLogs",
            component: () => import("../views/admin/annotation/OperationLogsView.vue"),
          },
        ],
      },
    ],
  },
  {
    path: "/detail/:nodeId",
    name: "Detail",
    component: () => import("../views/professional/graph/Detail.vue"),
    meta: { requiresAuth: true, requiresProfessional: true },
  },
  {
    path: "/detail-by-file/:fileUuid",
    name: "DetailByFile",
    component: () => import("../views/professional/graph/Detail.vue"),
    meta: { requiresAuth: true, requiresProfessional: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const authStore = useAuthStore();
  const role = authStore.user?.role;

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return "/login";
  }

  // 超级管理员登录后直达管理端点
  if (to.path === "/" && (role === "admin" || role === "super_admin")) {
    return "/admin";
  }

  if (to.meta.guest && authStore.isLoggedIn) {
    return "/";
  }

  if (
    to.meta.requiresProfessional &&
    !["professional", "admin", "super_admin"].includes(role)
  ) {
    return "/";
  }

  if (to.meta.requiresAdmin && !["admin", "super_admin"].includes(role)) {
    return "/";
  }

  if (to.meta.requiresAnnotator && role !== "annotator") {
    // 标注员专属操作台：管理员走管理端，普通/专业用户回首页
    return role === "admin" || role === "super_admin" ? "/admin" : "/";
  }

  if (role === "annotator" && !to.path.startsWith("/annotate") && to.path !== "/login") {
    return "/annotate";
  }
});

export default router;
