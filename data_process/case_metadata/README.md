# case_metadata — 病案元数据提取

## 功能

从已上传的 PDF 论文中，调用 Gemini 大模型提取中医病案结构化数据，写入 `case_metadata` 表，并更新 `core_file.status_case` 标记。

处理流程：查询待处理记录 → 从 MinIO 下载 PDF → Gemini API 提取 → JSON 解析校验 → 入库 → 更新状态

## 运行

```bash
# 激活环境
conda activate tcm-agent

# 从项目根目录运行
cd D:\SleepPause\Program\python\Tcm-agent
python -m data_process.case_metadata.run_extraction

# 只处理 20 条待处理病案
python -m data_process.case_metadata.run_extraction --limit 20
```

## 前置条件

1. PostgreSQL 和 MinIO 服务运行中
2. `core_file` 表中有 `document_type=1` 且 `status_case=false` 的记录（即已上传但未提取病案的 PDF）
3. `.env` 中已配置 Gemini API 密钥

## 工作机制

```
run_extraction.py 启动
  → 查询 core_file WHERE document_type=1 AND status_case=false
  → 对每条记录：
    1. 从 MinIO 下载 PDF
    2. base64 编码 PDF，连同 prompt 一起发送给 Gemini
    3. 解析 Gemini 返回的 JSON（20 个中文键名字段）
    4. 校验字段完整性，缺失字段补 null
    5. 中文键名映射为英文列名（如"中医证候诊断" → tcm_diagnosis）
    6. 插入 case_metadata 表
    7. 更新 core_file.status_case = true
  → 输出统计：成功/失败数
```

**断点续传**：已 `status_case=true` 的记录自动跳过，可随时中断后重新运行。

**去重保护**：已存在于 `case_metadata` 的 `file_uuid` 会跳过，不会重复调用 Gemini 或重复插入；若 `core_file.status_case=false` 但 `case_metadata` 已有记录，脚本只会同步 `status_case=true`。

**重试**：单条记录最多重试 3 次，间隔 10 秒。

## 中文键名 → 英文列名映射

LLM 输出中文键名（语义更准确），入库时映射为英文：

| LLM 输出键名 | 数据库列名 | 含义 |
|-------------|-----------|------|
| 年齡 | age | 年龄 |
| BMI | bmi | BMI |
| 月经情况 | menstruation | 月经情况 |
| 不孕情况 | infertility | 不孕情况 |
| 生活习惯 | lifestyle | 生活习惯 |
| 刻下症 | present_symptoms | 刻下症 |
| 既往病史 | medical_history | 既往病史 |
| 生化检查 | lab_tests | 生化检查 |
| 超声检查 | ultrasound | 超声检查 |
| 复诊情况 | followup | 复诊情况 |
| 西医病名诊断 | western_diagnosis | 西医诊断 |
| 中医证候诊断 | tcm_diagnosis | 中医诊断 |
| 治法 | treatment_principle | 治法 |
| 方剂 | prescription | 方剂 |
| 针刺选穴 | acupoints | 针刺选穴 |
| 辅助生殖技术 | assisted_reproduction | 辅助生殖 |
| 西药 | western_medicine | 西药 |
| 疔效评价 | efficacy | 疗效评价 |
| 不良反应 | adverse_reactions | 不良反应 |
| 按语/评价说明 | commentary | 按语/说明 |

## 数据库表

`case_metadata`（PostgreSQL `papers_records` 库）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| file_uuid | VARCHAR(36) FK | 关联 core_file |
| age | TEXT | 年齡 |
| bmi | TEXT | BMI |
| ... (其余 18 个 TEXT 字段) | TEXT | 病案各维度 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `prompt.md` | 发送给 Gemini 的提取指令（中文键名，20 字段） |
| `schema.json` | JSON Schema，用于校验 LLM 输出 + 生成 Gemini responseSchema |
| `models.py` | MedCase SQLAlchemy 模型 |
| `llm_client.py` | Gemini SSE 流式调用、payload 构建、JSON 解析 |
| `schemas.py` | 中文→英文映射、Pydantic 校验模型 |
| `service.py` | 核心业务逻辑（下载→提取→入库→更新状态） |
| `run_extraction.py` | 手动触发入口脚本 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| RELAY_BASE_URL | https://x666.me/v1beta/... | Gemini 中转站端点 |
| RELAY_API_KEY | - | API 密钥 |
| GEMINI_MODEL | gemini-3-flash-preview | 使用的模型 |

## 验证

```bash
# 运行提取后检查数据库
# PostgreSQL:
SELECT * FROM case_metadata;
SELECT file_uuid, status_case FROM core_file WHERE status_case = true;
```

## 去重机制

本模块可以安全重复运行，不会因为重复处理同一个病案 PDF 而产生多条病案结构化记录。

去重依据是 `file_uuid`：

- `case_metadata.file_uuid` 会创建唯一索引 `ux_case_metadata_file_uuid`，同一个 PDF 只保留一条病案结构化记录。
- 待处理查询只选择 `document_type=1`、`lower(file_type)='pdf'`、`status_case=false`，且 `case_metadata` 不存在同 `file_uuid` 记录的文件。
- 处理单条记录前会再次检查 `case_metadata` 是否已存在，防止任务中断后重新运行时重复调用 Gemini。
- 如果 `case_metadata` 已经存在记录，但 `core_file.status_case=false`，脚本只同步 `status_case=true`，不会重新调用 Gemini。
- 如果极端并发导致重复插入，唯一索引会阻止重复数据；程序回滚后同步 `status_case=true`，并将该条计为 skipped。
- Gemini、MinIO 或解析失败时不会写入 `case_metadata`，也不会把 `status_case` 改为 `true`，后续重新运行会继续重试。

状态规则：

```text
case_metadata 已存在 -> 不调用 Gemini -> 同步 core_file.status_case=true -> skipped
case_metadata 不存在且 status_case=false -> 下载 PDF -> Gemini 抽取 -> 写入 case_metadata -> status_case=true
抽取失败/超时 -> 不写 case_metadata -> status_case 保持 false，后续可重试
```
