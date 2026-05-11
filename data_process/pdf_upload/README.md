# pdf_upload — PDF 文件上传与数据库建立

## 功能

用户上传 PDF 论文 → 后端生成 UUID → 存储到 MinIO → 记录到 PostgreSQL `core_file` 表。

## 启动服务

```bash
# 激活环境
conda activate tcm-agent

# 从项目根目录启动
cd D:\SleepPause\Program\python\Tcm-agent
uvicorn data_process.pdf_upload.main:app --port 8001 --reload
```

Swagger 文档：http://localhost:8001/docs

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/files/upload` | 单文件上传，同名返回 409 |
| POST | `/api/files/batch-upload` | 批量上传，同名自动 skip |
| GET | `/api/files/` | 文件列表（分页） |
| GET | `/api/files/{uuid}` | 文件详情 |
| GET | `/api/files/{uuid}/download-url` | 生成 MinIO 下载链接 |
| DELETE | `/api/files/{uuid}` | 删除文件（MinIO + DB 同步） |

## 使用示例

```bash
# 单文件上传
curl -X POST -F "file=@论文.pdf" http://localhost:8001/api/files/upload

# 批量上传（同名文件自动跳过）
curl -X POST \
  -F "files=@论文A.pdf" \
  -F "files=@论文B.pdf" \
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
| storage_path | VARCHAR(1024) | MinIO 存储路径 |
| file_type | VARCHAR(32) | 文件类型 |
| upload_time | TIMESTAMPTZ | 上传时间 |
| status_metadata | BOOLEAN | 文献元数据处理状态 |
| status_case | BOOLEAN | 病案处理状态 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| POSTGRES_HOST | 172.16.150.45 | PostgreSQL 地址 |
| POSTGRES_PORT | 5432 | PostgreSQL 端口 |
| POSTGRES_USER | postgres | 数据库用户 |
| POSTGRES_PASSWORD | - | 数据库密码 |
| POSTGRES_DB | papers_records | 数据库名 |
| MINIO_ENDPOINT | 172.16.150.45:9000 | MinIO 地址 |
| MINIO_ROOT_USER | admin | MinIO 用户 |
| MINIO_ROOT_PASSWORD | - | MinIO 密码 |
| MINIO_BUCKET_NAME | tcm-documents | 存储桶名 |
| UPLOAD_MAX_SIZE_MB | 100 | 最大文件大小 |

## 测试

```bash
conda activate tcm-agent
pytest data_process/pdf_upload/tests/ -v
```
