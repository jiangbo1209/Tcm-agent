# case_metadata — 病案元数据提取

## 功能

从已上传且标记为病案的 PDF 中，调用通义千问多模态模型提取中医病案结构化数据，写入 `case_metadata` 表，并更新 `core_file.status_case` 标记。

处理流程：查询待处理记录 → 从 MinIO 下载 PDF → PDF 页面渲染为图片 → Qwen-VL 提取 → JSON 解析校验 → 入库 → 更新状态

## 运行

```bash
# 激活环境
conda activate tcm-agent

# 从项目根目录运行
cd D:\SleepPause\Program\python\Tcm-agent
python -m data_process.case_metadata.run_extraction
```

## 前置条件

1. PostgreSQL 和 MinIO 服务运行中
2. `core_file` 表中有 `document_type=1` 且 `status_case=false` 的记录（即已上传但未提取病案的 PDF）
3. `.env` 中已配置通义千问/百炼 API 密钥
4. 已安装 `PyMuPDF`，用于将 PDF 页面渲染为图片

## 工作机制

```
run_extraction.py 启动
  → 查询 core_file WHERE document_type=1 AND status_case=false AND file_type='pdf'
  → 对每条记录：
    1. 从 MinIO 下载 PDF
    2. 将 PDF 前若干页渲染为 JPEG 图片，并转为 base64 data URL
    3. 通过 DashScope OpenAI 兼容接口发送 prompt + 页面图片给 Qwen-VL
    4. 解析 Qwen-VL 返回的 JSON（20 个中文键名字段）
    5. 校验字段完整性，缺失字段补 null
    6. 中文键名映射为英文列名（如"中医证候诊断" → tcm_diagnosis）
    7. 插入 case_metadata 表
    8. 更新 core_file.status_case = true
  → 输出统计：成功/失败数
```

**断点续传**：已 `status_case=true` 的病案记录自动跳过，可随时中断后重新运行；文献和指南不会进入本模块处理。

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
| `prompt.md` | 发送给 Qwen-VL 的提取指令（中文键名，20 字段） |
| `schema.json` | JSON Schema，用于校验 LLM 输出 |
| `models.py` | MedCase SQLAlchemy 模型 |
| `llm_client.py` | Qwen-VL OpenAI 兼容流式调用、PDF 渲染、payload 构建、JSON 解析 |
| `schemas.py` | 中文→英文映射、Pydantic 校验模型 |
| `service.py` | 核心业务逻辑（下载→提取→入库→更新状态） |
| `run_extraction.py` | 手动触发入口脚本 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | DashScope OpenAI 兼容端点 |
| `LLM_API_KEY` | - | API 密钥 |
| `LLM_MODEL` | `qwen-vl-plus` | 使用的多模态模型 |
| `QWEN_PDF_MAX_PAGES` | `8` | 每个 PDF 最多发送前几页 |
| `QWEN_PDF_RENDER_SCALE` | `1.5` | PDF 页面渲染倍率 |

兼容旧变量：如果没有配置 `LLM_BASE_URL` 或 `LLM_API_KEY`，代码仍会读取 `RELAY_BASE_URL`、`RELAY_API_KEY`。模型名请使用 `LLM_MODEL` 或 `QWEN_MODEL`。

## 验证

```bash
# 运行提取后检查数据库
# PostgreSQL:
SELECT * FROM case_metadata;
SELECT file_uuid, status_case FROM core_file WHERE status_case = true;
```
