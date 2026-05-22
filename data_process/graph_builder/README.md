# graph_builder — 离线图谱建表

从 `lit_metadata` 与 `med_case` 抽取节点特征，计算相似度边，并写入图谱展示表 `nodes` / `edges`。

## 模块说明

- [data_process/graph_builder/models.py](data_process/graph_builder/models.py)：`Node`、`Edge`、`BuildGraphOptions` 数据类。
- [data_process/graph_builder/processor.py](data_process/graph_builder/processor.py)：文本清洗、分词、Jaccard 相似度、边生成、`top_k_value` 计算。
- [data_process/graph_builder/database.py](data_process/graph_builder/database.py)：数据库连接、Schema 创建、源表读取、分批写入。
- [data_process/graph_builder/engine.py](data_process/graph_builder/engine.py)：建图流程编排。
- [data_process/graph_builder/cli.py](data_process/graph_builder/cli.py)：命令行入口与 `.env` 读取。
- [data_process/graph_builder/__main__.py](data_process/graph_builder/__main__.py)：`python -m` 入口。
- [data_process/graph_builder/builder.py](data_process/graph_builder/builder.py)：兼容导出层，保留旧 import 路径。

## 流程概览

1. `cli.py` 读取 `.env`（优先 `DB_*`，其次 `POSTGRES_*`）。
2. `engine.py` 连接数据库并应用 Schema。
3. `database.py` 拉取 `lit_metadata` 与 `med_case`，构建节点。
4. `processor.py` 计算相似度边与 `top_k_value`。
5. `database.py` 按策略写入 `nodes` / `edges`。

## 节点构建逻辑

### paper 节点（`lit_metadata`）

- 标题：`title` → `matched_title` → `cleaned_title` → `original_name` → `file_uuid` 依次兜底。
- `node_id`：`paper` 前缀 + 归一化 key 的 SHA1。
- 文本拼接：`title`、`matched_title`、`cleaned_title`、`original_name`、`abstract`、`keywords`。
- 分词：
  - 英文/数字词：`[a-zA-Z0-9_]+`，长度 >= 2。
  - 中文：逐字切分成双字 bigram。
- **过滤**：`tokens` 为空则丢弃该节点。
- `metric_value`：从 `pub_year` 中提取年份。

### record 节点（`med_case`）

- 标题：来源于关联的 `lit_metadata` 字段，逻辑与 paper 同。
- `node_id`：`record` 前缀 + 归一化 key 的 SHA1。
- 文本拼接：`western_diagnosis`、`tcm_diagnosis`、`treatment_principle`、`prescription`、`present_symptoms`、`medical_history`、`lab_tests`、`ultrasound`、`followup`、`commentary`。
- 分词逻辑同上。
- **过滤**：`tokens` 为空则丢弃该节点。
- `metric_value`：从 `age` 中提取年龄。

## 边构建逻辑

### paper-paper / record-record

- 计算 Jaccard 相似度：$\frac{|A \cap B|}{|A \cup B|}$。
- 对每个节点取 Top K 相似节点（按分数降序）。
- 低于 `min_score` 的边直接丢弃。
- 边去重：无向对 `(src, dst)` 规范化后只保留更高分的一条。
- `edge_id`：`edge_type|src|dst` 归一化后取 SHA1。
- `similarity_score` 四舍五入到 4 位，`raw_score` 保留原值。

### ref

- 通过 `file_uuid` 关联 `paper` 与 `record`。
- `similarity_score` 与 `raw_score` 固定为 `1.0`。

### top_k_value

- 对每个节点累计相连边的 `similarity_score`。
- `top_k_value = 1.0 + log1p(weighted_degree)`。

### 聚类/近邻关系说明

- 这里没有显式的聚类算法，而是用 Jaccard 相似度生成 Top K 边。
- 结果是一个“相似度近邻图”：相似节点被连成局部邻域，可视为一种基于相似度的软聚类结构。

## 写入策略

- 使用 SQLAlchemy `create_all` 创建 `nodes` / `edges` 表，无需 SQL 文件。
- `truncate`：先清空 `edges`、`nodes`，再批量写入。
- `upsert`：`id` 冲突时更新字段并刷新 `updated_at`。
- 分批写入大小：500。

## 运行

从项目根目录运行：

```bash
python -m data_process.graph_builder
```

默认读取项目根目录 `.env`，并按 `DB_*` 优先、`POSTGRES_*` 兜底的顺序读取数据库配置。

## 参数

- `GRAPH_BUILDER_STRATEGY`：写入策略，支持 `truncate` / `upsert`
- `GRAPH_BUILDER_PAPER_TOP_K` / `GRAPH_BUILDER_RECORD_TOP_K`
- `GRAPH_BUILDER_PAPER_MIN_SCORE` / `GRAPH_BUILDER_RECORD_MIN_SCORE`

## 验证

```bash
python -m unittest discover -s data_process/graph_builder/tests
```
