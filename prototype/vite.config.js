import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 独立原型：无后端代理，全部数据来自本地 mock
export default defineConfig({
  plugins: [vue()],
  server: { port: 5600, strictPort: true },
});
