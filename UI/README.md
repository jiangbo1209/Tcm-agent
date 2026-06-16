# TCM-Graph UI

本目录提供“中医文献与病案知识图谱”的前后端。前端负责可视化与搜索入口，后端提供图谱查询、详情、搜索与 MinIO 文件访问。

## 目录结构

```
UI/
├─ backend/   # FastAPI 后端（PostgreSQL + MinIO）
├─ frontend/  # 搜索页 + 图谱页（G6）
├─ configs/   # 节点/边建表、索引与数据 schema
└─ README.md
```

迁移说明：离线建图脚本已迁移到 [data_process/graph_builder](data_process/graph_builder)，UI 仅保留建表 SQL 与索引脚本。

## 数据依赖

后端依赖以下表（PostgreSQL）：

- `core_file`：文件元信息与 MinIO 存储路径
- `lit_metadata`：文献元数据
- `med_case`：病案元数据
- `nodes` / `edges`：图谱展示表（由 `data_process.graph_builder` 生成）

文献与病案通过 `file_uuid` 关联，建图模块会生成 `ref` 边（强连接）。

## 在线 BFS 图谱生成逻辑（核心）

图谱扩展接口：`GET /api/graph/expand?seed_id=...&limit=...&depth=...`

1. 参数规范：
	- `limit` 被限制在 `[10, 20]`，默认 `10`。
	- `depth` 被限制在 `[1, 3]`，默认 `1`。
2. BFS 扩展流程（[UI/backend/app/services/graph_service.py](UI/backend/app/services/graph_service.py)）：
	- 从 `seed_id` 开始入队，维护 `visited_nodes` 与 `queue`。
	- 每出队一个节点，调用 `fetch_edges_by_seed` 拉取该节点的边（按 `similarity_score` 降序取 Top K）。
	- 将边的 `source_id/target_id` 加入 `visited_nodes`，未入队的节点进入下一层队列。
	- 当层级达到 `depth` 停止扩展。
3. 节点补全：
	- BFS 结束后一次性查询 `nodes` 表获取节点详情，按完成度排序（`core_file` 里状态完整的文献更靠前）。
4. 输出：返回 `nodes` + `edges`，前端以 G6 渲染。

## 后端能力与路由

- `main.py`：FastAPI 入口，仅 API，无页面渲染
- `/api/graph/expand`：BFS 图谱扩展
- `/api/graph/node-detail`：节点详情
- `/api/graph/search`：关键词搜索
- `/api/graph/search/index-status`：索引状态
- `/api/graph/file-url/{node_id}`：文献预签名链接
- `/health`：健康检查

搜索策略：PostgreSQL GIN/tsvector 就绪时走 FULLTEXT，不可用时回退 LIKE。

## 前端说明

- `search.html`：主搜索页（输入关键词/ID）
- `index.html`：图谱页（G6 可视化）
- `env.js`：配置 `API_BASE_URL`

前后端分离部署时，前端走静态服务器，后端只提供 API。前端通过 `env.js` 指定 `API_BASE_URL`，后端通过 `CORS_ALLOW_ORIGINS` 放行前端来源。

## 配置（.env）

后端优先读取 `DB_*`，缺失时使用 `POSTGRES_*`：

- `DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME`
- `POSTGRES_HOST / POSTGRES_PORT / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB`

MinIO 配置：

- `MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY / MINIO_BUCKET_NAME`

CORS：

- `CORS_ALLOW_ORIGINS`（逗号分隔）

## 本地启动（后端）

```bash
cd UI/backend
conda activate Tcm-agent
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/api/graph/search/index-status

## 本地启动（前端静态）

```bash
cd UI/frontend
python3 -m http.server 5500
```

- 搜索页：http://127.0.0.1:5500/search.html
- 图谱页：http://127.0.0.1:5500/index.html

## 索引与离线建图

### 初始化数据库表结构

```bash
python -m data_process.db_init
```

### 创建全文索引（GIN/tsvector）

```bash
psql -h 127.0.0.1 -U postgres -d papers_records -f UI/configs/sql/indexes/001_fulltext_search_indexes.sql
```

或使用容器：

```bash
docker compose exec -T postgresql psql -U postgres -d papers_records < UI/configs/sql/indexes/001_fulltext_search_indexes.sql
```

### 离线建图（nodes/edges）

建图脚本已迁移到 [data_process/graph_builder](data_process/graph_builder)：

```bash
python3 -m data_process.graph_builder
```

`nodes` / `edges` 表由 SQLAlchemy `create_all` 创建，无需 SQL 文件。

## 文件说明

### backend

- [UI/backend/main.py](UI/backend/main.py)：FastAPI 入口与 CORS
- [UI/backend/app/config.py](UI/backend/app/config.py)：DB/MinIO/Search 配置读取
- [UI/backend/app/api/routes_graph.py](UI/backend/app/api/routes_graph.py)：图谱 API 路由
- [UI/backend/app/services/graph_service.py](UI/backend/app/services/graph_service.py)：BFS 扩展、详情聚合、搜索分页
- [UI/backend/app/repositories/graph_repository.py](UI/backend/app/repositories/graph_repository.py)：SQL 查询封装
- [UI/backend/app/core/minio_utils.py](UI/backend/app/core/minio_utils.py)：MinIO 预签名链接
- [UI/backend/app/search/settings.py](UI/backend/app/search/settings.py)：搜索策略枚举
- [UI/backend/app/models/entities.py](UI/backend/app/models/entities.py)：表实体与字段常量
- [UI/backend/app/schemas/graph.py](UI/backend/app/schemas/graph.py)：API Schema

### frontend

- [UI/frontend/search.html](UI/frontend/search.html)：搜索入口页面
- [UI/frontend/index.html](UI/frontend/index.html)：图谱页面
- [UI/frontend/env.js](UI/frontend/env.js)：`API_BASE_URL` 配置
- [UI/frontend/src/search.js](UI/frontend/src/search.js)：搜索页逻辑
- [UI/frontend/src/main.js](UI/frontend/src/main.js)：图谱页逻辑
- [UI/frontend/src/components/graphView.js](UI/frontend/src/components/graphView.js)：G6 渲染与交互
- [UI/frontend/src/components/detailPanel.js](UI/frontend/src/components/detailPanel.js)：详情面板
- [UI/frontend/src/store/graphStore.js](UI/frontend/src/store/graphStore.js)：前端状态存储
- [UI/frontend/src/search.css](UI/frontend/src/search.css)：搜索页样式
- [UI/frontend/src/styles.css](UI/frontend/src/styles.css)：图谱页样式
