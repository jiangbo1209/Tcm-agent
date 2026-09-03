import axios from "axios";

const request = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

request.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || "";
      // 登录/注册接口的 401 属于业务失败（密码错误、账号不存在等），
      // 应就地展示错误文案，不触发登出+跳转（避免登录页重定向循环）
      const isAuthRequest =
        url.includes("/api/auth/login") ||
        url.includes("/auth/login") ||
        url.includes("/api/auth/register") ||
        url.includes("/auth/register");
      if (!isAuthRequest) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default request;
