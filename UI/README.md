# TCM-Graph UI

本目录提供"中医文献与病案知识图谱"的前后端，采用 Vue 3 + FastAPI 架构。

## 目录结构

```
UI/
├── backend/        # FastAPI 后端
│   ├── main.py     # 应用入口
│   ├── app/
│   │   ├── auth/           # JWT 认证模块
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── routers/        # API 路由
│   │   ├── services/       # 业务逻辑层
│   │   ├── repositories/   # 数据访问层
│   │   ├── core/           # 数据库引擎、异常等基础设施
│   │   ├── storage/        # S3 兼容对象存储 (腾讯云 COS / AWS S3)
│   │   └── search/         # 搜索策略配置
│   ├── requirements.txt
│   └── create_professional_user.py
└── frontend/       # Vue 3 前端
    ├── src/
    │   ├── views/          # 页面组件
    │   ├── components/     # 通用组件
    │   ├── stores/         # Pinia 状态管理
    │   ├── api/            # API 封装
    │   ├── router/         # 路由配置
    │   └── styles/         # 全局样式
    ├── package.json
    └── vite.config.js
```

## 技术栈

- **前端**: Vue 3 + Vite + Vue Router + Pinia + Axios
- **后端**: FastAPI + SQLAlchemy ORM + JWT 认证
- **数据库**: SQLite（用户/对话/搜索历史）+ PostgreSQL（文献/病案/图谱数据）

## 快速启动

详见 [UI/backend/README.md](backend/README.md) 和 [UI/frontend/README.md](frontend/README.md)。

## API 概览

| 模块 | 路由前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/auth` | 注册、登录 |
| 对话 | `/api/chat` | 对话管理、消息发送（SSE） |
| 搜索 | `/api/search` | 智能搜索、搜索历史 |
| 历史 | `/api/history` | 对话+搜索历史聚合 |
| 图谱 | `/api/graph` | BFS 扩展、节点详情、文件访问 |
| 文件 | `/api/files` | PDF 上传/列表/删除 (需登录) |

## 数据库说明

- **SQLite** (`tcm.db`): 存储用户、对话、消息、搜索历史，后端启动时自动创建
- **PostgreSQL**: 存储文献、病案、图谱节点/边，需通过 `data_process.db_init` 初始化

## 角色权限

| 功能 | normal | professional |
|------|--------|--------------|
| 对话助手 | ✓ | ✓ |
| 智能搜索 | ✗ | ✓ |
