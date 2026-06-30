# lit_metadata — 基础文档元数据提取

## 功能

`lit_metadata` 用于给所有已上传 PDF 提取基础文档元数据，并写入 `lit_metadata` 表。

这里的 `lit_metadata` 虽然名字里有 `lit`，但当前项目中它承担的是“基础文档元数据表”的作用，不只处理文献。

处理范围来自 `core_file`：

```sql
status_metadata = false
AND document_type IN (0, 1, 2)
AND lower(file_type) = 'pdf'
```

三类数据都会进入 `lit_metadata`：

| document_type | 类型 | 是否进入 lit_metadata | 后续用途 |
|------|------|------|------|
| 0 | 文献 | 是 | 文献知识库、图谱文献节点 |
| 1 | 病案 | 是 | 给病案补充标题、来源等基础信息 |
| 2 | 指南 | 是 | 后续同步到 `guideline_metadata` |

成功写入后，会更新：

```sql
core_file.status_metadata = true
```

## 它做什么

本模块不读取 PDF 正文，只根据文件名清洗出标题，然后到外部学术站点检索基础信息：

1. 清洗 `core_file.original_name`
2. 默认依次检索 `e读`、`NSTL`
3. 只接受标题严格匹配的结果
4. 写入 `lit_metadata`
5. 更新 `core_file.status_metadata=true`
6. 失败记录写入 `failed_records`，并可导出 CSV

CNKI 默认关闭，后续确实需要时再手动开启。

提取字段包括：

- 标题
- 作者
- 摘要
- 关键词
- 文献类型
- 来源站点
- 来源链接
- 期刊
- 年份
- 匹配标题
- 爬取状态

## 启动前准备

先确认已经上传 PDF：

```bash
python data_process/pdf_upload/pdf_manager_tui.py
```

上传后 `core_file` 里应有记录，并且 `document_type` 已正确标记：

```text
0 文献
1 病案
2 指南
```

## 配置 .env

进入模块目录：

```bash
cd data_process/lit_metadata
cp .env.example .env
```

数据库连接有两种配置方式。

方式一：直接配置 `DATABASE_URL`：

```env
DATABASE_URL=postgresql+asyncpg://postgres:你的URL编码后的密码@172.16.150.45:5432/papers_records
```

如果密码中有 `@`，要写成 `%40`。例如：

```text
Tcm@2026_pg -> Tcm%402026_pg
```

方式二：使用项目根目录 `.env` 中的 PostgreSQL 配置，程序会自动拼接 PostgreSQL 连接：

```env
POSTGRES_HOST=172.16.150.45
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=你的密码
POSTGRES_DB=papers_records
```

本模块不再使用 SQLite 兜底。如果数据库配置缺失或指向 SQLite，会直接报错。

推荐测试配置：

```env
OUTPUT_DIR=./outputs
CORE_FILE_PENDING_LIMIT=10
CRAWLER_CONCURRENCY=1
REQUEST_DELAY_MIN=2.0
REQUEST_DELAY_MAX=5.0
ENABLE_NSTL=true
ENABLE_CNKI=false
EXPORT_FAILED_CSV=true
LOG_LEVEL=INFO
```

参数说明：

| 参数 | 说明 |
|------|------|
| `CORE_FILE_PENDING_LIMIT` | 本次最多处理多少条，`0` 表示不限制 |
| `ENABLE_CNKI` | 是否启用知网检索，默认关闭 |
| `ENABLE_NSTL` | 是否启用 NSTL 检索 |
| `CRAWLER_CONCURRENCY` | 并发数，建议先用 `1` |
| `EXPORT_FAILED_CSV` | 是否导出失败记录 CSV |

## 安装依赖

在项目环境中执行：

```bash
conda activate Tcm-agent
pip install -r data_process/lit_metadata/requirements.txt
```

CNKI 默认不启用，所以正常测试不需要安装浏览器。只有手动开启 CNKI 时，首次才可能需要浏览器支持。Windows 推荐使用系统 Edge：

```bash
playwright install msedge
```

## 运行

推荐从 `lit_metadata` 目录运行：

```bash
cd data_process/lit_metadata
python main.py
```

小批量测试时，先把 `.env` 里的 `CORE_FILE_PENDING_LIMIT` 设置为 `5` 或 `10`。

全量运行时：

```env
CORE_FILE_PENDING_LIMIT=0
```

然后重新执行：

```bash
python main.py
```

## CNKI 首次运行说明

如果启用了 CNKI：

```env
ENABLE_CNKI=true
CNKI_HEADLESS_BOOTSTRAP=false
CNKI_BROWSER_CHANNEL=msedge
```

首次运行可能会弹出浏览器窗口。请等待页面正常加载，如果出现验证，需要手动完成。完成后程序会保存 cookie，后续短时间内会自动复用。

如果你只想先快速跑通流程，可以临时关闭 CNKI：

```env
ENABLE_CNKI=false
```

## 查看处理结果

回到数据库查看：

```sql
select
  cf.document_type,
  count(*) as total,
  count(lm.file_uuid) as lit_done,
  count(*) filter (where cf.status_metadata = false) as pending
from core_file cf
left join lit_metadata lm on lm.file_uuid = cf.file_uuid
group by cf.document_type
order by cf.document_type;
```

查看最近写入的元数据：

```sql
select file_uuid, original_name, title, source_site, journal, pub_year, crawl_status
from lit_metadata
order by updated_at desc
limit 20;
```

查看失败记录：

```sql
select file_name, cleaned_title, failure_reason, error_message, created_at
from failed_records
order by created_at desc
limit 20;
```

如果开启了 `EXPORT_FAILED_CSV=true`，失败 CSV 会输出到：

```text
data_process/lit_metadata/outputs/failed_records.csv
```

## 常用流程

50 篇测试推荐顺序：

```bash
# 1. 上传三类 PDF
python data_process/pdf_upload/pdf_manager_tui.py

# 2. 提取全部 PDF 的基础文档元数据
cd data_process/lit_metadata
python main.py

# 3. 回到项目根目录继续处理病案和指南
cd ../..
python -m data_process.case_metadata.run_extraction
python -m data_process.guideline_metadata.main
```

## 注意事项

- `lit_metadata` 必须先于 `guideline_metadata` 运行，因为指南元数据同步依赖 `lit_metadata`。
- 病案也建议先跑 `lit_metadata`，这样后续图谱和 RAGFlow 同步能拿到标题、来源等信息。
- 本模块只做基础文档元数据，不做病案结构化抽取。
- 本模块不把数据同步到 RAGFlow，RAGFlow 同步由 `data_process/ragflow_sync` 负责。

## 去重机制

本模块可以安全重复运行，不会因为重复处理同一个 PDF 而产生多条基础元数据记录。

去重依据是 `file_uuid`：

- `lit_metadata.file_uuid` 有唯一约束，同一个 PDF 只保留一条基础元数据记录。
- 写入 `lit_metadata` 时使用 upsert 逻辑；同一个 `file_uuid` 再次写入会更新原记录，不会重复插入。
- 扫描待处理文件时，会排除已经存在于 `lit_metadata` 的 `file_uuid`，避免再次爬取和解析。
- 如果 `lit_metadata` 已经存在记录，但 `core_file.status_metadata=false`，程序会先同步为 `true`，然后跳过该文件。
- `failed_records.file_uuid` 也有唯一约束；同一个 PDF 失败多次时，会更新原失败记录，不会重复插入，也不会因为唯一键冲突中断任务。

状态规则：

```text
lit_metadata 已存在 -> 不重新爬取 -> 同步 core_file.status_metadata=true -> skipped
lit_metadata 不存在且 status_metadata=false -> 正常爬取 -> 写入 lit_metadata -> status_metadata=true
爬取失败 -> upsert failed_records -> status_metadata 保持 false，后续可重试
```
