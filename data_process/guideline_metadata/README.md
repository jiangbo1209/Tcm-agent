# guideline_metadata — 指南元数据同步

## 功能

将已经写入 `lit_metadata` 的指南基础元数据同步到 `guideline_metadata` 表。

本模块不重新爬取、不重新解析 PDF，只处理以下记录：

```sql
core_file.document_type = 2
AND core_file.status_metadata = true
AND core_file.status_guidelinemeta = false
AND lower(core_file.file_type) = 'pdf'
```

同步成功后更新：

```sql
core_file.status_guidelinemeta = true
```

## 运行

```bash
# 同步全部待处理指南
python -m data_process.guideline_metadata.main

# 小批量同步
python -m data_process.guideline_metadata.main --limit 10
```

## 数据流

```text
core_file(document_type=2)
  -> lit_metadata 基础文档元数据
  -> guideline_metadata 指南元数据
  -> core_file.status_guidelinemeta=true
```

## 说明

`lit_metadata` 是所有 PDF 的基础文档元数据表。

`guideline_metadata` 是指南专用表，后续用于 Agent 的医学指南依据、回答校验和安全性判断，不参与图谱构建。
