# TCM Agent 后端

`UI/backend` 是平台唯一的 HTTP 服务。它使用 FastAPI，提供认证、Agent 对话、搜索、图谱、文件、用户管理、元数据管理和数据标注 API。全部业务数据存储在 PostgreSQL，PDF 存储在 S3-compatible 对象存储中。

## 目录结构

```text
UI/backend/
├── main.py                     # FastAPI 入口、路由注册、应用级服务实例
├── app/
│   ├── auth/                   # 登录、注册、JWT 与密码哈希
│   ├── core/                   # PostgreSQL 引擎、格式化、schema 兼容处理
│   ├── dependencies/           # 权限和上传服务依赖
│   ├── models/                 # 业务表与图谱表 ORM
│   ├── repositories/           # 管理、详情、图谱和搜索数据访问
│   ├── routers/                # HTTP API
│   ├── schemas/                # Pydantic 请求/响应模型
│   ├── services/               # Agent、图谱、管理和标注业务逻辑
│   └── storage/                # S3-compatible 客户端、文件 token 和上传服务
├── scripts/
│   ├── init_db.py              # 初始化全部 PostgreSQL 表
│   ├── import_users.py         # 通过 CSV 创建或更新用户
│   └── users.csv.example
└── tests/                      # pytest 测试
```

Python 依赖统一声明在项目根目录的 `environment.yml`；本目录没有独立的 `requirements.txt`。当前后端不使用 SQLite，也不会创建 `tcm.db`。

## 配置与启动

从项目根目录执行：

```bash
conda env create -f environment.yml
conda activate Tcm-agent
# UserCreate 使用 Pydantic EmailStr；当前 environment.yml 未显式包含该可选包
python -m pip install email-validator
cp .env.example .env

docker compose up -d postgresql
python UI/backend/scripts/init_db.py

cd UI/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8011
```

启动后可访问：

- OpenAPI：<http://127.0.0.1:8011/docs>
- 健康检查：<http://127.0.0.1:8011/health>

`main.py` 导入时会执行部分兼容性列迁移，但完整建表仍应显式运行 `scripts/init_db.py`。

## API 与权限

| 模块 | 方法与路径 | 权限 |
| --- | --- | --- |
| 认证 | `POST /api/auth/register`、`POST /api/auth/login` | 公开 |
| 对话 | `GET/POST /api/chat/conversations` | 登录 |
| 对话 | `GET/POST /api/chat/conversations/{id}/messages` | 登录且只能访问自己的对话 |
| 对话 | `DELETE /api/chat/conversations/{id}` | 登录且只能删除自己的对话 |
| 搜索 | `POST /api/search` | professional / admin |
| 搜索 | `GET /api/search/index-status` | 公开（当前代码行为） |
| 搜索历史 | `GET /api/search/history` | 登录 |
| 聚合历史 | `GET /api/history` | 登录 |
| 图谱 | `GET /api/graph/expand`、`/node-detail`、`/search` | professional / admin |
| 文件 | 上传、列表、详情、下载 URL | 登录 |
| 文件 | `GET /api/files/stream?token=...` | 有效文件签名 token |
| 文件 | 单个/批量删除 | admin |
| 元数据管理 | `/api/admin...` | admin |
| 用户管理 | `/api/users...` | admin |
| 标注工作台 | `/api/annotation...` | annotator + `ANNOTATION_ENABLED=true` |
| 标注管理 | `/api/annotation/admin...` | admin + `ANNOTATION_ENABLED=true` |

文件查看/下载入口是：

```text
GET /api/files/{file_uuid}/download-url?mode=view|download
```

旧接口 `/api/graph/file-url/{node_id}` 已不存在。

## 数据库

同步路由使用 `psycopg2` 引擎；文件路由使用懒加载的 `asyncpg` 引擎。二者连接同一个 `POSTGRES_*` 数据库。

主要表组：

- 账号与对话：`users`、`conversations`、`messages`、`conversation_memories`、`agent_tool_runs`、`search_history`。
- 文件与元数据：`core_file`、`lit_metadata`、`case_metadata`、`guideline_metadata`。
- 图谱：`nodes`、`edges`。
- 标注：`annotation_pools`、`annotation_pool_items`、`annotation_tasks`、`annotation_task_items`、`annotation_submissions`、`annotation_logs`。

## 创建用户

公开注册只创建 `normal` 用户：

```bash
curl -X POST http://127.0.0.1:8011/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@tcm.com","password":"123456"}'
```

其他角色通过 CSV 导入脚本创建或更新：

```bash
cp UI/backend/scripts/users.csv.example /tmp/tcm-users.csv
python UI/backend/scripts/import_users.py /tmp/tcm-users.csv
```

CSV 无表头，格式为：

```text
username,email,password,role
```

可用角色为 `normal`、`professional`、`annotator`、`admin`。

## 主要环境变量

| 变量 | 代码默认值 | 说明 |
| --- | --- | --- |
| `POSTGRES_HOST` | `127.0.0.1` | PostgreSQL 地址 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 端口 |
| `POSTGRES_USER` | `postgres` | 用户名 |
| `POSTGRES_PASSWORD` | 空 | 密码 |
| `POSTGRES_DB` | `postgres` | 数据库名；根目录示例覆盖为 `papers_records` |
| `APP_ENV` | `development` | 设为 `production` 时启用密钥检查 |
| `JWT_SECRET_KEY` | 开发默认密钥 | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | `1440` | token 有效期（分钟） |
| `FILE_TOKEN_SECRET` | 空 | 文件流签名密钥；生产环境必填 |
| `S3_ENDPOINT` | 腾讯云北京 COS 地址 | S3-compatible 地址 |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | 空 | 对象存储凭证 |
| `S3_BUCKET_NAME` | `tcm-documents` | 存储桶 |
| `S3_REGION` | `ap-beijing` | 区域 |
| `UPLOAD_MAX_FILE_SIZE_MB` | `100` | 单文件限制 |
| `UPLOAD_ALLOWED_EXTENSIONS` | `.pdf` | 允许扩展名，逗号分隔 |
| `UPLOAD_BATCH_CONCURRENCY` | `5` | 批量上传并发数 |
| `SEARCH_BACKEND_MODE` | `auto` | `auto` / `fulltext` / `like` |
| `ANNOTATION_ENABLED` | `false` | 标注功能总闸 |

完整配置以项目根目录 `.env.example` 和代码中的 Settings 类为准。生产模式下若 JWT 仍使用开发默认值，或 `FILE_TOKEN_SECRET` 为空，应用会拒绝启动。

## 测试

后端测试位于 `UI/backend/tests/`。在依赖和测试数据库配置完整的环境中，可从项目根目录运行：

```bash
python -m pytest UI/backend/tests -q
```
