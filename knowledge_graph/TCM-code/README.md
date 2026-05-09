# TCM-code

中医文献与病案知识图谱项目，采用前后端分离 + ETL 建图脚本结构。

## 0. 代码结构总览

```
TCM-code/
├─ backend/   # FastAPI 后端，图谱查询、详情、搜索、MinIO 文件访问
├─ frontend/  # 搜索页 + 图谱页，G6 可视化与交互
├─ configs/   # 数据库建表、索引脚本、schema 与环境模板
├─ .env       # 本地运行环境变量（数据库 / MinIO / API）
└─ docker-compose.yaml  # 本地容器编排（MySQL + Backend + Frontend）
```

关键流程：

- ETL 脚本生成 nodes/edges -> 图谱服务查询与渲染
- 搜索 API 支持 FULLTEXT/LIKE 回退，并提供索引就绪状态
- 文献文件通过 MinIO 预签名 URL 预览/下载

## 1. 根目录说明

### 1.1 根目录文件

- `README.md`
  - 项目说明、启动方式、工程化建议。
- `.env`
  - 本地环境变量（建议仅本机使用，不提交敏感信息）。
- `docker-compose.yaml`
  - 本地容器编排（MySQL + Backend API + Frontend 静态站点）。
- `papers_records_2026-04-23_215402.sql`
  - 数据导出样例（用于数据库初始化或问题复现）。

### 1.2 根目录子目录

- `backend`
  - 后端 API、业务逻辑、数据库访问、ETL 脚本。
- `frontend`
  - 图可视化页面（G6）和前端状态管理。
- `configs`
  - 配置与 schema（数据库建表 SQL、数据 JSON schema）。
  - 包含索引预留目录：`configs/sql/indexes`。

## 2. backend 目录说明

### 2.1 backend 顶层文件

- `backend/main.py`
  - FastAPI 应用入口。
  - 组装路由、注入服务实例、配置 CORS。
  - 提供 API、健康检查与前端页面入口（search/index）。
  - 静态资源通过 `/static` 路径挂载。
- `backend/requirements.txt`
  - 后端 Python 依赖清单。

### 2.2 backend/app 分层目录

- `backend/app/api`
  - 路由层。
  - 当前主要接口文件：`routes_graph.py`。
  - 职责：参数校验、错误码处理、调用 service。

- `backend/app/services`
  - 业务逻辑层。
  - 当前主要文件：`graph_service.py`。
  - 职责：
    - 图谱 BFS 扩展（支持 depth）
    - 节点详情组装
    - limit/depth 业务约束处理

- `backend/app/repositories`
  - 数据访问层。
  - 当前主要文件：`graph_repository.py`。
  - 职责：
    - 访问 `nodes`、`edges` 图表
    - 查询 `paper` 与 `all_papers_records` 明细
    - 数据库连接与 SQL 执行

- `backend/app/models`
  - 领域模型常量。
  - 当前主要文件：`entities.py`。
  - 职责：定义 paper/record 字段集合等领域常量。

- `backend/app/schemas`
  - 接口出入参定义（Pydantic）。
  - 当前主要文件：`graph.py`。
  - 职责：统一响应结构，保证前后端契约稳定。

- `backend/app/config.py`
  - 配置读取与数据库连接参数解析。

- `backend/app/search`
  - 搜索策略配置层（预留扩展接口）。
  - `settings.py`：定义 `auto/fulltext/like` 搜索后端模式。

- `backend/app/core`
  - 核心工具层。
  - `minio_utils.py`：MinIO 客户端封装、Bucket 检查、预签名 URL 生成。

### 2.3 backend/scripts

- `backend/scripts/build_graph_from_tables.py`
  - ETL 建图脚本。
  - 职责：
    - 从 `paper` 和 `all_papers_records` 读取源数据
    - 文本分词与 Jaccard 相似度计算
    - 生成 `nodes`、`edges` 及 top_k 权重
    - 写回图服务层表

- `backend/scripts/run_file_key_sync.py`
  - 文献文件回填脚本。
  - 职责：执行 `002` 迁移脚本、扫描 MinIO 对象并回填 `paper.file_key`。

## 3. frontend 目录说明

### 3.1 frontend 顶层文件

- `frontend/index.html`
  - 图谱展示页入口。
  - 默认挂载路径：`/graph-view` 或 `/index.html`。
  - 引入 G6、`env.js` 配置和前端模块脚本。

- `frontend/search.html`
  - 主搜索入口页。
  - 默认挂载路径：`/`。

- `frontend/src/search.css`
  - 搜索入口页样式。

- `frontend/src/search.js`
  - 搜索入口页交互逻辑（回车/点击跳转到图谱页）。

- `frontend/env.js`
  - 前端运行时配置文件。
  - 目前用于配置后端 API 地址：`API_BASE_URL`。

### 3.2 frontend/src 目录

- `frontend/src/main.js`
  - 前端主流程编排。
  - 职责：
    - 处理用户输入
    - 调用 `${API_BASE_URL}/api/graph/expand` 与 `${API_BASE_URL}/api/graph/node-detail`
    - 连接 store 与组件，更新页面状态

- `frontend/src/styles.css`
  - 页面样式、布局与响应式规则。

- `frontend/src/components`
  - UI/图组件层。
  - `graphView.js`：G6 图实例初始化、节点边映射、渲染与交互。
  - `detailPanel.js`：右侧详情面板渲染。

- `frontend/src/store`
  - 状态管理层。
  - `graphStore.js`：
    - 节点/边内存存储
    - 合并增量图数据
    - in-flight 请求状态管理

## 4. configs 目录说明

- `configs/graph_nodes_edges.sql`
  - 图服务层建表脚本（`nodes`、`edges`）。
- `configs/case_record.schema.json`
  - 病案数据结构约束 schema。
- `configs/.env.example`
  - 环境变量模板。
- `configs/sql/indexes/001_fulltext_search_indexes.sql`
  - 文献与病案搜索 FULLTEXT 索引脚本（面向 10w+ 规模预留）。
- `configs/sql/indexes/README.md`
  - 索引发布流程与命名规范。
- `configs/sql/002_literature_file_key.sql`
  - 增加 `paper.file_key` 字段。

## 5. 本地启动（前后端分离）

### 5.1 使用 venv

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 5.2 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 5.3 启动后端 API

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端健康检查：`http://127.0.0.1:8000/health`

索引就绪检查（新增）：`http://127.0.0.1:8000/api/graph/search/index-status`

后端托管的前端入口：

- 主搜索页：`http://127.0.0.1:8000/`
- 图谱页：`http://127.0.0.1:8000/graph-view` 或 `http://127.0.0.1:8000/index.html`

### 5.4 启动前端静态站点

先确认 `frontend/env.js` 中的 `API_BASE_URL` 指向后端地址（默认 `http://127.0.0.1:8000`）。

```bash
cd frontend
python -m http.server 5500
```

访问前端页面：

- 搜索页：`http://127.0.0.1:5500/search.html`
- 图谱页：`http://127.0.0.1:5500/index.html`

## 6. Docker 启动（分离部署）

```bash
docker compose up -d
```

- Frontend(搜索页): `http://127.0.0.1:8080/`
- Frontend(图谱页): `http://127.0.0.1:8080/graph-view`
- Backend API: `http://127.0.0.1:8000/health`

## 7. ETL 建图脚本使用

```bash
cd backend
python scripts/build_graph_from_tables.py --password 你的MySQL密码
```

默认 schema 路径：`../configs/graph_nodes_edges.sql`

## 8. 文献文件

### 8.1 基础概念

- `paper.file_key`：MinIO 对象名（如 `docs/xxx.pdf`），用于预览/下载

### 8.2 迁移与回填

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p papers_records < configs/sql/002_literature_file_key.sql
```

回填脚本：

```bash
cd backend
python scripts/run_file_key_sync.py
```

### 8.3 文件预览/下载 API

- 预览：`GET /api/graph/file-url/{node_id}?mode=view`
- 下载：`GET /api/graph/file-url/{node_id}?mode=download`

## 9. 大规模搜索索引预留（10w+ 文献）

### 8.1 执行索引脚本

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p papers_records < configs/sql/indexes/001_fulltext_search_indexes.sql
```

### 8.2 检查索引就绪状态

调用：`GET /api/graph/search/index-status`

返回关键字段：

- `configured_backend`：当前配置的搜索策略
- `effective_backend`：当前实际生效策略
- `fulltext_ready`：FULLTEXT 是否就绪
- `tables[].missing_columns`：缺失索引列

### 8.3 搜索策略配置

在 `.env` 或运行环境中设置：

- `SEARCH_BACKEND_MODE=auto`：优先 FULLTEXT，缺失时自动回退 LIKE（推荐）
- `SEARCH_BACKEND_MODE=fulltext`：强制优先 FULLTEXT（SQL 异常时仍回退 LIKE）
- `SEARCH_BACKEND_MODE=like`：始终使用 LIKE（仅兼容场景）

## 10. 后续工程化建议

### 7.1 配置与环境

- 引入分环境配置：`dev/test/prod`（例如 `pydantic-settings`）。
- 统一 `.env` 管理策略，区分提交模板与本地私密配置。
- 在启动前增加配置校验，避免运行期才发现缺参。

### 7.2 代码质量与规范

- 增加 `ruff + black + isort + mypy`。
- 增加 pre-commit，提交前自动格式化与静态检查。
- 为 service/repository 层补充类型标注与 docstring。

### 7.3 测试体系

- 增加后端单元测试（service 纯逻辑）。
- 增加 repository 集成测试（测试库 + 固定数据）。
- 增加 API 契约测试，校验响应 schema 稳定性。
- 前端增加基础 E2E（节点展开、详情加载、清空图谱）。

### 7.4 数据与 ETL

- 将 ETL 参数化并沉淀为配置文件（top_k、min_score）。
- 增加 ETL 运行日志和指标输出（写入节点数、边数、耗时）。
- 对大数据量场景增加批处理优化和断点续跑能力。

### 7.5 可观测性与运维

- 接入结构化日志（JSON）并统一 request_id。
- 增加健康检查接口和 readiness/liveness 探针。
- 为关键接口增加耗时与错误率监控。

### 7.6 部署与交付

- 补齐 `backend/Dockerfile` 与前端静态构建方案。
- 将 `docker-compose.yaml` 区分开发版与部署版。
- 建立 CI/CD：lint -> test -> build -> deploy。

### 7.7 架构演进

- 逐步引入数据库迁移工具（Alembic 或等价方案）。
- 为 API 增加版本化（如 `/api/v1/...`）。
- 当图规模增大时评估图数据库或检索加速方案。
