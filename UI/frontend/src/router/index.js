import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    meta: { guest: true },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("../views/Register.vue"),
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
        component: () => import("../views/Chat.vue"),
      },
      {
        path: "search",
        name: "Search",
        component: () => import("../views/Search.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "search/results",
        name: "SearchResults",
        component: () => import("../views/SearchResults.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "graph",
        name: "Graph",
        component: () => import("../views/Graph.vue"),
        meta: { requiresProfessional: true },
      },
      {
        path: "admin",
        name: "Admin",
        component: () => import("../views/AdminDataEdit.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "users",
        name: "Users",
        component: () => import("../views/UserManagement.vue"),
        meta: { requiresAdmin: true },
      },
      {
        path: "annotate",
        name: "AnnotateWorkbench",
        component: () => import("../views/AnnotationWorkbench.vue"),
        meta: { requiresAnnotator: true },
      },
      {
        path: "annotate/history",
        name: "AnnotationHistory",
        component: () => import("../views/AnnotationHistoryView.vue"),
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
    component: () => import("../views/Detail.vue"),
    meta: { requiresAuth: true, requiresProfessional: true },
  },
  {
    path: "/detail-by-file/:fileUuid",
    name: "DetailByFile",
    component: () => import("../views/Detail.vue"),
    meta: { requiresAuth: true, requiresProfessional: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return next("/login");
  }

  if (to.path === "/" && authStore.user?.role === "admin") {
    return next("/admin");
  }

  if (to.meta.guest && authStore.isLoggedIn) {
    return next("/");
  }

  if (
    to.meta.requiresProfessional &&
    !["professional", "admin"].includes(authStore.user?.role)
  ) {
    return next("/");
  }

  if (to.meta.requiresAdmin && authStore.user?.role !== "admin") {
    return next("/");
  }

  if (to.meta.requiresAnnotator && authStore.user?.role !== "annotator") {
    return next("/");
  }

  if (
    authStore.user?.role === "annotator" &&
    !to.path.startsWith("/annotate") &&
    to.path !== "/login"
  ) {
    return next("/annotate");
  }

  next();
});

export default router;
