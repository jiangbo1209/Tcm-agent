# pdf_upload — PDF 文件上传与数据库建立

## 功能

用户上传 PDF 文件 → 选择数据类型 → 后端生成 UUID → 存储到对象存储 → 记录到 PostgreSQL `core_file` 表。

`document_type` 用于区分数据类型：

| 值 | 类型 | 后续处理 |
|------|------|------|
| 0 | 文献 | 进入 `lit_metadata`，参与文献检索和图谱构建 |
| 1 | 病案 | 进入 `case_metadata`，参与病案检索和图谱构建 |
| 2 | 指南 | 进入 `guideline_metadata`，只用于 Agent 回答校验 |

## 启动服务

```bash
# 激活环境
conda activate tcm-agent

# 从项目根目录启动
cd D:\SleepPause\Program\python\Tcm-agent
uvicorn data_process.pdf_upload.main:app --port 8001 --reload
```

Swagger 文档：http://localhost:8001/docs

## 文件管理工具（推荐使用）

### TUI 管理工具（完整增删查功能）

```bash
python data_process/pdf_upload/pdf_manager_tui.py
```

菜单功能：
- **📤 上传文件** - 弹出文件选择器，支持单选或多选 PDF 文件；上传前选择文献、病案或指南
- **📋 查看文件列表** - 查看所有已上传的文件、数据类型和处理状态
- **🗑️  删除文件** - 通过编号选择文件删除（确认后执行）

**Linux 无图形界面说明**

在无 GUI 的 Linux 服务器上运行时，上传文件会切换为命令行输入模式：
- 直接输入单个或多个 PDF 文件路径（逗号分隔）。
- 也可以输入一个目录路径，工具会自动读取该目录下的 `*.pdf`。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/files/upload` | 单文件上传，可通过 `document_type` 指定类型 |
| POST | `/api/files/batch-upload` | 批量上传，可通过 `document_type` 指定类型，同类型同名自动 skip |
| GET | `/api/files/` | 文件列表（分页） |
| GET | `/api/files/{uuid}` | 文件详情 |
| GET | `/api/files/{uuid}/download-url` | 生成 COS 下载链接 (预签名 URL) |
| POST | `/api/files/batch-delete` | 批量删除文件（请求体含 file_uuids 列表） |
| DELETE | `/api/files/{uuid}` | 删除文件（COS + DB 同步） |

## 使用示例

```bash
# 单文件上传文献
curl -X POST \
  -F "document_type=0" \
  -F "file=@论文.pdf" \
  http://localhost:8001/api/files/upload

# 单文件上传指南
curl -X POST \
  -F "document_type=2" \
  -F "file=@指南.pdf" \
  http://localhost:8001/api/files/upload

# 批量上传病案（同类型同名文件自动跳过）
curl -X POST \
  -F "document_type=1" \
  -F "files=@病案A.pdf" \
  -F "files=@病案B.pdf" \
  http://localhost:8001/api/files/batch-upload

# 查看文件列表
curl http://localhost:8001/api/files/?page=1&size=10

# 生成下载链接（1小时有效）
curl http://localhost:8001/api/files/{uuid}/download-url

# 删除文件
curl -X DELETE http://localhost:8001/api/files/{uuid}
```

## 数据库表

`core_file`（PostgreSQL `papers_records` 库）：

| 字段 | 类型 | 说明 |
|------|------|------|
| file_uuid | VARCHAR(36) PK | 自动生成 UUID |
| original_name | VARCHAR(512) | 原始文件名 |
| storage_path | VARCHAR(1024) | 对象存储 COS 存储路径 |
| file_type | VARCHAR(32) | 文件类型 |
| upload_time | TIMESTAMPTZ | 上传时间 |
| status_metadata | BOOLEAN | 文献元数据处理状态 |
| status_case | BOOLEAN | 病案处理状态 |
| document_type | INTEGER | 数据类型：0 文献、1 病案、2 指南 |
| status_guidelinemeta | BOOLEAN | 指南元数据处理状态 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| POSTGRES_HOST | 172.16.150.45 | PostgreSQL 地址 |
| POSTGRES_PORT | 5432 | PostgreSQL 端口 |
| POSTGRES_USER | postgres | 数据库用户 |
| POSTGRES_PASSWORD | - | 数据库密码 |
| POSTGRES_DB | papers_records | 数据库名 |
| S3_ENDPOINT | https://cos.ap-beijing.myqcloud.com | 对象存储地址 |
| S3_ACCESS_KEY | - | 对象存储 SecretId |
| S3_SECRET_KEY | - | 对象存储 SecretKey |
| S3_BUCKET | tcm-documents-1387425381 | COS 存储桶名 |
| S3_REGION | ap-beijing | COS 地域 |
| UPLOAD_MAX_SIZE_MB | 100 | 最大文件大小 |

## 测试

```bash
conda activate tcm-agent
pytest data_process/pdf_upload/tests/ -v
```
