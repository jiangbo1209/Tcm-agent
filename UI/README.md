# TCM Agent Web UI

`UI/` 包含 Vue 3 前端和 FastAPI 后端，提供 Agent 对话、专业搜索、知识图谱、PDF 文件、成员管理和数据标注能力。

## 目录结构

```text
UI/
├── backend/
│   ├── main.py
│   ├── app/
│   │   ├── auth/
│   │   ├── core/
│   │   ├── dependencies/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── storage/
│   ├── scripts/
│   └── tests/
└── frontend/
    ├── src/
    │   ├── api/
    │   ├── components/
    │   ├── router/
    │   ├── stores/
    │   ├── styles/
    │   └── views/
    ├── package.json
    └── vite.config.js
```

Python 依赖位于项目根目录 `environment.yml`；后端目录没有独立 `requirements.txt`。全部业务表、元数据表和图谱表都使用 PostgreSQL，不使用 SQLite。

## 快速启动

先按项目根 README 创建环境、配置 `.env` 并初始化 PostgreSQL，再分别启动：

```bash
cd UI/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8011
```

```bash
cd UI/frontend
npm install
npm run dev
```

前端开发服务器监听 <http://localhost:5500>，并把 `/api` 代理到 `http://127.0.0.1:8011`。

详细说明见 [后端 README](backend/README.md) 和 [前端 README](frontend/README.md)。

## API 概览

| 前缀 | 功能 | 主要权限 |
| --- | --- | --- |
| `/api/auth` | 注册、登录 | 公开 |
| `/api/chat` | 对话与 Agent SSE | 登录 |
| `/api/search` | 专业搜索与搜索历史 | 搜索需 professional/admin；历史需登录 |
| `/api/history` | 对话和搜索聚合历史 | 登录 |
| `/api/graph` | BFS 扩展、节点详情、节点搜索 | professional/admin |
| `/api/files` | PDF 上传、读取和删除 | 上传/读取需登录；删除需 admin |
| `/api/admin` | 元数据管理 | admin |
| `/api/users` | 成员管理 | admin |
| `/api/annotation` | 标注工作台 | annotator + 标注总闸 |
| `/api/annotation/admin` | 标注管理 | admin + 标注总闸 |

PDF 查看/下载由 `/api/files/{file_uuid}/download-url` 提供。

## 角色权限

| 功能 | normal | professional | annotator | admin |
| --- | --- | --- | --- | --- |
| Agent 对话 | ✓ | ✓ | 后端允许，前端不展示 | 后端允许，前端不展示 |
| 专业搜索、知识图谱 | ✗ | ✓ | ✗ | 后端与路由允许 |
| 标注工作台 | ✗ | ✗ | ✓ | ✗ |
| 用户、元数据、标注管理 | ✗ | ✗ | ✗ | ✓ |

标注功能默认关闭，需要设置 `ANNOTATION_ENABLED=true`。
