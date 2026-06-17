# RAGFlow 同步脚本

用于将项目中的文献 PDF 和病案结构化内容同步到 RAGFlow 知识库。该脚本按服务器运行场景设计，默认只在部署了 RAGFlow、PostgreSQL、MinIO 的服务器上执行。

## 功能概览

- 从 `core_file` + `lit_metadata` 读取文献记录。
- 根据 `storage_path` 从 MinIO 下载文献 PDF。
- 从 `med_case` 读取病案记录，并生成可上传文本。
- 通过 RAGFlow HTTP API 上传文档、写入元数据、触发解析。
- 通过 `ragflow_sync_status` 表记录同步状态，保证幂等。
- 支持只重跑失败记录，适合生产补数。

读取 PostgreSQL core_file / lit_metadata / med_case

    |

    |-- 文献：从 MinIO 下载 PDF

    |       -> 上传 PDF 到 RAGFlow

    |       -> 用 document_id 写入 meta_fields

    |       -> 触发 parse

    |

    |-- 病案：从 med_case 生成 Markdown/TXT

    -> 上传到

    RAGFlow

    -> 写入 meta_fields

    -> 触发 parse

## 代码结构

```text
data_process/ragflow_sync/
├── __init__.py              # 包标识
├── __main__.py              # 支持 python -m data_process.ragflow_sync
├── main.py                  # 命令行入口，解析参数并输出同步摘要
├── config.py                # 读取 .env 中的数据库、MinIO、RAGFlow 配置
├── models.py                # 同步流程使用的数据类，如 LiteratureSource、CaseSource、SyncResult
├── orm.py                   # RAGFlow 同步状态表 ORM 模型 RagflowSyncStatus
├── database.py              # SQLAlchemy ORM 数据库访问层，读取文献/病案并维护同步状态
├── minio_store.py           # MinIO PDF 下载封装
├── ragflow_client.py        # RAGFlow HTTP API 客户端，负责上传、写 metadata、触发 parse
├── document_builder.py      # 病案文本生成、文件名生成、metadata 构建、content_hash 计算
├── service.py               # 同步主流程编排，处理幂等、阶段日志、失败记录
├── requirements.txt         # 同步脚本依赖
├── README.md                # 使用说明
└── tests/                   # 单元测试
    ├── test_document_builder.py
    ├── test_service.py
    ├── test_main.py
    └── test_database_orm.py
```

核心调用链：

```text
main.py
  -> RagflowSyncService
  -> RagflowSyncRepository / MinioObjectStore / RagflowClient
  -> RAGFlow API
```

## 安装依赖

```bash
pip install -r data_process/ragflow_sync/requirements.txt
```

## 命令说明

最常用的参数：

- `--source`：同步范围，可选 `all`、`literature`、`case`
- `--limit`：限制本次同步条数，适合分批测试
- `--dry-run`：只预览待同步数据，不实际上传
- `--only-failed`：只重跑上次状态为 `failed` 的记录
- `--no-parse`：上传并写入元数据，但不触发解析
- `--force`：忽略已有成功状态，强制重新上传

## 生产运行

下面三类最关键命令。

### 1. Dry-run 预览

用于正式同步前检查本次会处理哪些数据，不会调用 RAGFlow。

```bash
python -m data_process.ragflow_sync --source all --limit 5 --dry-run
```

### 2. 小批量同步

建议先从病案或文献各同步少量记录，确认上传、元数据写入和解析都正常。

```bash
python -m data_process.ragflow_sync --source case --limit 5
python -m data_process.ragflow_sync --source literature --limit 5
```

### 3. 全量同步

小批量验证通过后，再执行全量同步。全量运行时不传 `--limit`，脚本会按当前筛选条件处理全部记录。

```bash
python -m data_process.ragflow_sync --source literature
python -m data_process.ragflow_sync --source case
python -m data_process.ragflow_sync --source all
```

### 4. 失败重跑

当部分文档因解析失败、网络波动或接口异常未完成时，只重跑失败项。

```bash
python -m data_process.ragflow_sync --source literature --only-failed
python -m data_process.ragflow_sync --source case --only-failed
```

## 日志与结果

每条记录会输出：

- 数据类型：`literature` / `case`
- `file_uuid`
- 当前结果：`uploaded` / `parsed` / `skipped` / `failed`
- 当前阶段：`precheck` / `dry_run` / `metadata` / `parse` / `upload`
- `document_id`
- 错误信息或补充信息

示例：

```text
literature 95b36265-04dc-4595-bdf6-c46b856a60e1: parsed stage=parse document_id=f9e5086069ec11f1b42713f4d88a1b71
literature dbcf7033-8843-4642-a1d1-77a47be2f009: failed stage=parse document_id=f9489c0a69ec11f1b42713f4d88a1b71 message=parse failed: RAGFlow API error: IndexError('list index out of range')
```

脚本结束后会输出汇总摘要：

```text
Summary: uploaded=0 parsed=3 skipped=5 failed=2 total=10
```

## 故障定位

常见失败阶段含义如下：

- `stage=upload`：上传文档到 RAGFlow 失败
- `stage=metadata`：写入元数据失败
- `stage=parse`：触发解析或解析过程失败
- `stage=precheck`：同步前检查命中跳过条件
- `stage=dry_run`：当前是预览模式，没有实际上传

如果某条记录反复在 `parse` 阶段失败，通常说明文档本身在 RAGFlow 解析时存在兼容问题，可在 RAGFlow 页面进一步查看该 `document_id`。
