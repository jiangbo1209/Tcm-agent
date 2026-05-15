# TCM-Graph UI

本目录提供“中医文献与病案知识图谱”的前后端与建图脚本，前端负责可视化与搜索入口，后端提供图谱查询、详情、搜索与 MinIO 文件访问。

## 0. 目录结构

```
UI/
├─ backend/   # FastAPI 后端（PostgreSQL + MinIO）
├─ frontend/  # 搜索页 + 图谱页（G6）
├─ configs/   # 节点/边建表、索引与数据 schema
└─ README.md
```

关键流程：

- ETL 脚本把 lit_metadata/med_case 建图为 nodes/edges
- 搜索 API 支持 PostgreSQL GIN/tsvector，索引未就绪时回退 LIKE
- 文献原文通过 MinIO 预签名 URL 预览/下载

## 1. 数据与表结构

数据依赖以下表（均在 PostgreSQL）：

- core_file：文件元信息与 MinIO 存储路径
- lit_metadata：文献元数据
- med_case：病案元数据
- nodes / edges：图谱展示表（由脚本生成）

其中文献与病案通过 file_uuid 关联，脚本会生成 ref 边（强连接）。

## 2. backend 说明

主要能力：

- BFS 图谱扩展 / 搜索 / 节点详情
- MinIO 预签名链接（文献预览/下载）
- 索引状态检查（全文检索就绪与否）

主要入口与路由：

- main.py：FastAPI 入口，挂载前端页面
- /api/graph/expand：图谱扩展
- /api/graph/node-detail：节点详情
- /api/graph/search：关键词搜索
- /api/graph/search/index-status：索引状态
- /api/graph/file-url/{node_id}：文献预签名链接
- /health：健康检查

## 3. frontend 说明

- search.html：主搜索页（输入关键词/ID）
- index.html：图谱页（G6 可视化）
- env.js：配置 API_BASE_URL

后端托管页面路径：

- /：搜索页
- /graph-view：图谱页

## 4. 配置说明（.env）

后端会优先读取 DB_*，若缺失则使用 POSTGRES_*：

- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
- POSTGRES_HOST / POSTGRES_PORT / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB

MinIO 相关配置：

- MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY / MINIO_BUCKET_NAME

## 5. 本地启动（后端）

```bash
cd UI/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端检查：

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/api/graph/search/index-status

## 6. 本地启动（前端静态）

```bash
cd UI/frontend
python -m http.server 5500
```

访问：

- 搜索页：http://127.0.0.1:5500/search.html
- 图谱页：http://127.0.0.1:5500/index.html

## 7. Docker 启动

在项目根目录执行：

```bash
docker compose up -d --build
```

访问：

- Backend API：http://127.0.0.1:8000/health
- 搜索页：http://127.0.0.1:8000/
- 图谱页：http://127.0.0.1:8000/graph-view

## 8. 索引与建图

### 8.1 创建全文索引（GIN/tsvector）

```bash
psql -h 127.0.0.1 -U postgres -d papers_records -f UI/configs/sql/indexes/001_fulltext_search_indexes.sql
```

或使用容器：

```bash
docker compose exec -T postgres psql -U postgres -d papers_records < UI/configs/sql/indexes/001_fulltext_search_indexes.sql
```

### 8.2 建图脚本（nodes/edges）

```bash
python UI/backend/scripts/build_graph_from_tables.py --password <POSTGRES_PASSWORD>
```

默认使用 UI/configs/graph_nodes_edges.sql 建表。

### 8.3 文件预览/下载 API

- 预览：`GET /api/graph/file-url/{node_id}?mode=view`
- 下载：`GET /api/graph/file-url/{node_id}?mode=download`

## 9. 测试建议

1) 健康检查

```bash
curl http://127.0.0.1:8000/health
```

2) 索引状态

```bash
curl http://127.0.0.1:8000/api/graph/search/index-status
```

3) 搜索与扩展

```bash
curl "http://127.0.0.1:8000/api/graph/search?q=肝肾亏虚&page=1&size=10"
```

4) 节点详情

```bash
curl "http://127.0.0.1:8000/api/graph/node-detail?node_id=<NODE_ID>"
```

## 10. 搜索策略配置

在 `.env` 或运行环境中设置：

- `SEARCH_BACKEND_MODE=auto`：优先 FULLTEXT，缺失时自动回退 LIKE（推荐）
- `SEARCH_BACKEND_MODE=fulltext`：强制优先 FULLTEXT（SQL 异常时仍回退 LIKE）
- `SEARCH_BACKEND_MODE=like`：始终使用 LIKE（仅兼容场景）

## 11. 工程化建议

- 建议补充 lint + test + CI/CD 流程
- ETL 参数化与日志化（top_k、min_score、耗时等）
- 观测与告警（健康检查、耗时、错误率）
