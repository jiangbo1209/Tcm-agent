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
        path: "detail/:nodeId",
        name: "Detail",
        component: () => import("../views/Detail.vue"),
        meta: { requiresProfessional: true },
      },
    ],
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

  if (to.meta.guest && authStore.isLoggedIn) {
    return next("/");
  }

  if (to.meta.requiresProfessional && authStore.user?.role !== "professional") {
    return next("/");
  }

  next();
});

export default router;
