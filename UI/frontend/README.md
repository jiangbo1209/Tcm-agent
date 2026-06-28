# TCM Agent 前端

Vue 3 单页应用，提供对话助手、智能搜索和历史记录功能。

## 目录结构

```
frontend/
├── index.html              # 入口 HTML
├── package.json            # 依赖配置
├── vite.config.js          # Vite 配置（开发代理、端口）
└── src/
    ├── main.js             # Vue 应用入口
    ├── App.vue             # 根组件
    ├── router/
    │   └── index.js        # 路由配置（登录守卫、角色守卫）
    ├── stores/             # Pinia 状态管理
    │   ├── auth.js         # 认证状态（token、user、角色）
    │   ├── chat.js         # 对话状态（对话列表、消息）
    │   └── search.js       # 搜索状态（结果、历史）
    ├── api/                # Axios API 封装
    │   ├── request.js      # Axios 实例（JWT 拦截器）
    │   ├── auth.js         # 登录/注册
    │   ├── chat.js         # 对话 CRUD + SSE 流式消息
    │   ├── search.js       # 智能搜索
    │   └── history.js      # 历史记录
    ├── views/              # 页面组件
    │   ├── Login.vue       # 登录页
    │   ├── Register.vue    # 注册页
    │   ├── Chat.vue        # 对话主页（SSE 流式输出）
    │   ├── Search.vue      # 智能搜索入口
    │   └── SearchResults.vue # 搜索结果页
    ├── components/         # 通用组件
    │   ├── Layout.vue      # 主布局（侧边栏 + 内容区）
    │   ├── Sidebar.vue     # 左侧导航栏
    │   ├── ChatMessage.vue # 消息气泡
    │   └── ChatInput.vue   # 输入框
    └── styles/
        └── global.css      # 全局样式（teal 配色方案）
```

## 启动

```bash
cd UI/frontend

# 安装依赖
npm install

# 开发模式（默认端口 5500）
npm run dev

# 生产构建
npm run build
```

访问 http://localhost:5500

## 页面说明

### 登录/注册

- `/login` — 登录页，已有账号登录
- `/register` — 注册页，创建新账号（默认 normal 角色）

### 对话助手（`/`）

- 左侧栏：新建对话、对话历史列表
- 主区域：聊天消息流，支持 SSE 流式输出
- 输入框：Enter 发送消息

### 智能搜索（`/search`）

- 仅专业用户可见
- 支持勾选：搜索文献 / 搜索病案 / 全部
- 搜索结果页：卡片式展示，支持分页
- 搜索历史：首页展示历史查询词

### 历史记录

- 左侧栏展示对话历史和搜索历史
- 点击对话历史可恢复对话

## 角色权限

| 功能 | normal | professional |
|------|--------|--------------|
| 登录/注册 | ✓ | ✓ |
| 对话助手 | ✓ | ✓ |
| 智能搜索 | ✗（菜单隐藏） | ✓ |
| 搜索历史 | ✗ | ✓ |

## 开发代理

`vite.config.js` 配置了 API 代理，开发时自动将 `/api` 请求转发到后端：

```js
server: {
  port: 5500,
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8011",
      changeOrigin: true,
    },
  },
},
```

## 构建部署

```bash
npm run build
```

构建产物输出到 `dist/` 目录，可部署到 Nginx 等静态服务器。

Nginx 配置示例：

```nginx
server {
    listen 80;
    root /path/to/UI/frontend/dist;
    index index.html;

    location /api {
        proxy_pass http://127.0.0.1:8011;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 技术要点

- **JWT 认证**：登录后 token 存储在 localStorage，Axios 拦截器自动携带
- **SSE 流式输出**：对话消息通过 `fetch` + `ReadableStream` 实现逐字输出
- **路由守卫**：未登录自动跳转登录页，普通用户无法访问搜索页
- **配色方案**：主色调 teal (#00796b)，深色侧边栏 (#1a1a2e)
