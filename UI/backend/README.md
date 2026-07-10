# TCM Agent 后端

FastAPI 后端，提供用户认证、对话管理、智能搜索和知识图谱 API。

## 目录结构

```
backend/
├── main.py                     # FastAPI 入口，注册路由、初始化数据库
├── requirements.txt            # Python 依赖
├── create_professional_user.py # 创建专业用户脚本
├── tcm.db                      # SQLite 数据库（运行时自动生成）
└── app/
    ├── config.py               # 环境变量配置（PostgreSQL、S3/COS、搜索策略）
    ├── database.py             # SQLite 引擎 & Session 管理
    ├── database_pg.py          # PostgreSQL 引擎 & Session 管理
    ├── auth/
    │   ├── service.py          # 密码哈希（bcrypt）、JWT 生成/验证
    │   ├── dependencies.py     # FastAPI 依赖注入（get_current_user、require_professional）
    │   └── router.py           # POST /api/auth/register、POST /api/auth/login
    ├── models/
    │   ├── base.py             # SQLite SQLAlchemy Base
    │   ├── user.py             # users 表
    │   ├── conversation.py     # conversations 表
    │   ├── message.py          # messages 表
    │   ├── search_history.py   # search_history 表
    │   └── graph.py            # PostgreSQL ORM（Node、Edge、LitMetadata、MedCase、CoreFile）
    ├── schemas/
    │   ├── user.py             # 用户 Pydantic 模型
    │   ├── conversation.py     # 对话 Pydantic 模型
    │   ├── message.py          # 消息 Pydantic 模型
    │   ├── search.py           # 搜索请求/响应 Pydantic 模型
    │   └── graph.py            # 图谱 Pydantic 模型（保留）
    ├── routers/
    │   ├── auth.py             # 认证路由
    │   ├── chat.py             # 对话路由（含 SSE 流式输出占位）
    │   ├── search.py           # 智能搜索路由（需专业用户权限）
    │   ├── history.py          # 历史记录路由
    │   └── graph.py            # 图谱 API 路由（保留）
    ├── services/
    │   └── graph_service.py    # 图谱业务逻辑（BFS 扩展、详情聚合）
    ├── repositories/
    │   └── graph_repository.py # 图谱数据访问（SQLAlchemy ORM）
    ├── core/
    │   └── minio_utils.py      # 对象存储预签名链接 (S3 兼容)
    └── search/
        └── settings.py         # 搜索后端策略枚举
```

## 启动

```bash
cd UI/backend

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认端口 8011）
uvicorn main:app --reload --host 0.0.0.0 --port 8011
```

启动后自动创建 SQLite 数据库文件 `tcm.db`。

## API 文档

启动后访问 http://127.0.0.1:8011/docs 查看 Swagger 交互式文档。

### 认证接口

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/auth/register` | 注册新用户 | 公开 |
| POST | `/api/auth/login` | 登录，返回 JWT token | 公开 |

### 对话接口

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/chat/conversations` | 获取对话列表 | 登录用户 |
| POST | `/api/chat/conversations` | 创建新对话 | 登录用户 |
| GET | `/api/chat/conversations/{id}/messages` | 获取对话消息 | 登录用户 |
| POST | `/api/chat/conversations/{id}/messages` | 发送消息（SSE 流式响应） | 登录用户 |
| DELETE | `/api/chat/conversations/{id}` | 删除对话 | 登录用户 |

### 搜索接口

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/search` | 智能搜索（文献/病案/全部） | 专业用户 |
| GET | `/api/search/history` | 搜索历史 | 登录用户 |

### 历史接口

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/history` | 对话+搜索历史聚合 | 登录用户 |

### 图谱接口（保留）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/graph/expand` | BFS 图谱扩展 |
| GET | `/api/graph/node-detail` | 节点详情 |
| GET | `/api/graph/search` | 关键词搜索 |
| GET | `/api/graph/file-url/{node_id}` | 文献预签名链接 |
| GET | `/health` | 健康检查 |

## 数据库

### SQLite（用户/对话/搜索）

自动创建，无需手动操作。

**users 表**：用户信息、角色（normal/professional）

**conversations 表**：对话记录，关联 user_id

**messages 表**：消息记录，关联 conversation_id，role 为 user 或 assistant

**search_history 表**：搜索历史，记录查询词、搜索类型、结果数

### PostgreSQL（文献/病案/图谱）

需通过 `data_process.db_init` 初始化，配置在 `.env` 中：

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=papers_records
```

## 创建测试用户

```bash
# 创建普通用户（通过 API）
curl -X POST http://127.0.0.1:8011/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "email": "test@tcm.com", "password": "123456"}'

# 创建专业用户（脚本）
python create_professional_user.py
# 默认: admin / admin123
# 自定义: PRO_USERNAME=myuser PRO_PASSWORD=mypass python create_professional_user.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_SECRET_KEY` | tcm-agent-secret-key... | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | 1440 | Token 过期时间（分钟） |
| `POSTGRES_HOST` | 127.0.0.1 | PostgreSQL 地址 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `POSTGRES_USER` | postgres | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | (空) | PostgreSQL 密码 |
| `POSTGRES_DB` | postgres | PostgreSQL 数据库名 |
| `S3_ENDPOINT` | https://cos.ap-beijing.myqcloud.com | 对象存储地址 |
| `S3_ACCESS_KEY` | (空) | SecretId |
| `S3_SECRET_KEY` | (空) | SecretKey |
| `S3_BUCKET` | tcm-documents-1387425381 | COS 存储桶名 |
| `S3_REGION` | ap-beijing | COS 地域 |
