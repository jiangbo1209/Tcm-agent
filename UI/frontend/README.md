# TCM Agent 前端

Vue 3 单页应用，使用 Vite、Vue Router、Pinia、Axios 和 AntV G6。前端只访问 UI 后端，不直接连接 PostgreSQL、对象存储、RAGFlow 或 LLM。

## 目录结构

```text
UI/frontend/
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── src/
    ├── api/                    # Axios API 与聊天 fetch/SSE 客户端
    ├── components/             # 布局、侧栏、聊天、图谱、详情组件
    ├── router/index.js         # 路由和角色守卫
    ├── stores/                 # auth、chat、search Pinia store
    ├── styles/global.css
    └── views/
        ├── auth/               # 登录、注册
        ├── chat/               # Agent 对话
        ├── professional/       # 搜索、图谱、详情
        ├── annotator/          # 标注工作台与历史
        └── admin/              # 成员管理与标注管理
```

## 启动与构建

```bash
cd UI/frontend
npm install
npm run dev
```

开发服务器默认监听 <http://localhost:5500>。

```bash
npm run build
npm run preview
```

`vite.config.js` 将 `/api` 代理到 `VITE_API_TARGET`；未设置时使用 `http://127.0.0.1:8011`：

```bash
VITE_API_TARGET=http://127.0.0.1:8011 npm run dev
```

## 当前路由

| 路径 | 页面 | 权限 |
| --- | --- | --- |
| `/login` | 登录 | 访客 |
| `/register` | 注册 | 访客 |
| `/` | Agent 对话 | 登录；admin/annotator 会转到各自工作区 |
| `/search` | 搜索条件 | professional/admin |
| `/search/results` | 搜索结果 | professional/admin |
| `/graph` | 知识图谱 | professional/admin |
| `/detail/:nodeId` | 图谱节点详情 | professional/admin |
| `/detail-by-file/:fileUuid` | 文件关联详情 | professional/admin |
| `/users` | 成员管理 | admin |
| `/annotate` | 标注工作台 | annotator |
| `/annotate/history` | 标注历史 | annotator |
| `/admin/annotation/pools` | 标注池管理 | admin |
| `/admin/annotation/review` | 审核队列 | admin |
| `/admin/annotation/board` | 标注看板 | admin |
| `/admin/annotation/export` | 标注导出 | admin |
| `/admin/annotation/logs` | 操作日志 | admin |
| `/admin` | 元数据管理路由 | admin |

角色信息来自登录 JWT 的 `sub` 和 `role`，与 token 一起保存在 `localStorage`。Axios 请求拦截器为普通 API 自动添加 Bearer token；聊天流使用 `fetch` 读取后端 SSE。

## 角色可见功能

| 功能 | normal | professional | annotator | admin |
| --- | --- | --- | --- | --- |
| 对话 | ✓ | ✓ | ✗ | ✗ |
| 专业搜索、图谱 | ✗ | ✓ | ✗ | 菜单不展示，但路由守卫和后端允许 |
| 标注工作台 | ✗ | ✗ | ✓ | ✗ |
| 成员、标注管理 | ✗ | ✗ | ✗ | ✓ |

后端文件 API 已有实现，但当前侧栏没有独立文件管理页面；PDF 链接主要从聊天引用和详情组件进入。

## 开发代理与生产部署

开发服务器把 `/api` 请求代理到 UI 后端。生产部署需要让 SPA 路由回退到 `index.html`，并反向代理 `/api`：

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

聊天接口使用流式响应；生产代理还应关闭该接口的响应缓冲，并配置足够的读取超时。

当前 `package.json` 只有 `dev`、`build`、`preview`，没有 lint 或前端测试脚本。
