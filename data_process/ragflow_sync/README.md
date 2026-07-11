# RAGFlow 同步脚本

用于把项目中的文献、病案和指南同步到 RAGFlow。当前按三类知识库分别同步：

- 文献 PDF -> 文献知识库
- 病案结构化 Markdown -> 病案知识库
- 指南 PDF -> 指南校验知识库

`--source all` 只同步文献和病案，不包含指南。指南需要显式执行 `--source guideline`，避免误传到主问答知识库。

## 数据来源

| source | 数据来源 | 上传内容 | RAGFlow 知识库 |
|------|------|------|------|
| `literature` | `core_file` + `lit_metadata`，且 `document_type=0` | PDF 原文 | 文献知识库 |
| `case` | `case_metadata`，且 `document_type=1` | Markdown 文本 | 病案知识库 |
| `guideline` | `core_file` + `guideline_metadata`，且 `document_type=2` | PDF 原文 | 指南校验知识库 |

同步状态写入 `ragflow_sync_status`，用于幂等跳过和失败重跑。

## 环境变量

```env
RAGFLOW_BASE_URL=http://172.16.150.45:8012
RAGFLOW_API_KEY=你的API_KEY

RAGFLOW_LITERATURE_DATASET_ID=文献知识库ID
RAGFLOW_CASE_DATASET_ID=病案知识库ID
RAGFLOW_GUIDELINE_DATASET_ID=指南校验知识库ID

RAGFLOW_PARSE_AFTER_UPLOAD=true
RAGFLOW_DOMAIN=DOR infertility
```

脚本会根据 `--source` 自动选择对应知识库：

| 命令参数 | 使用的 dataset id |
|------|------|
| `--source literature` | `RAGFLOW_LITERATURE_DATASET_ID` |
| `--source case` | `RAGFLOW_CASE_DATASET_ID` |
| `--source guideline` | `RAGFLOW_GUIDELINE_DATASET_ID` |
| `--source all` | 文献 + 病案，不包含指南 |

## 安装依赖

```bash
pip install -r data_process/ragflow_sync/requirements.txt
```

## Dry-run 预览

只查看待同步数据，不上传到 RAGFlow。

```bash
python -m data_process.ragflow_sync --source literature --limit 5 --dry-run
python -m data_process.ragflow_sync --source case --limit 5 --dry-run
python -m data_process.ragflow_sync --source guideline --limit 5 --dry-run
```

## 小批量同步

建议生产前先小批量验证。

```bash
python -m data_process.ragflow_sync --source literature --limit 5
python -m data_process.ragflow_sync --source case --limit 5
python -m data_process.ragflow_sync --source guideline --limit 5
```

## 全量同步

小批量验证通过后再执行全量。全量运行时不传 `--limit`。

```bash
python -m data_process.ragflow_sync --source literature
python -m data_process.ragflow_sync --source case
python -m data_process.ragflow_sync --source guideline
```

也可以同步主问答知识库相关数据：

```bash
python -m data_process.ragflow_sync --source all
```

注意：`all` 只包含 `literature` 和 `case`。

## 失败重跑

只重跑上次同步状态为 `failed` 的记录。

```bash
python -m data_process.ragflow_sync --source literature --only-failed
python -m data_process.ragflow_sync --source case --only-failed
python -m data_process.ragflow_sync --source guideline --only-failed
```

## 输出摘要

每条记录会输出：

```text
{source} {file_uuid}: {action} stage={stage} document_id={document_id} message={message}
```

脚本结束会输出汇总：

```text
Summary: uploaded=12 parsed=10 skipped=50 failed=2 total=74
```

常见阶段：

| stage | 含义 |
|------|------|
| `dry_run` | 预览模式，没有上传 |
| `precheck` | 同步前检查，通常是跳过 |
| `upload` | 上传到 RAGFlow |
| `metadata` | 写入 RAGFlow 元数据 |
| `parse` | 触发 RAGFlow 解析 |

## 代码结构

```text
data_process/ragflow_sync/
├── __main__.py          # 支持 python -m data_process.ragflow_sync
├── main.py              # 命令行入口
├── config.py            # 读取数据库、对象存储 (COS)、RAGFlow 配置
├── database.py          # SQLAlchemy 数据库访问
├── document_builder.py  # 构建文件名、Markdown 和 metadata
├── s3_store.py          # 腾讯云 COS 下载封装 (S3 兼容)
├── ragflow_client.py    # RAGFlow HTTP API 客户端
├── service.py           # 同步主流程
├── orm.py               # ragflow_sync_status ORM
└── tests/               # 单元测试
```
