# graph_builder — 离线图谱建表

从 `lit_metadata` 与 `case_metadata` 抽取节点特征，计算相似度边，并写入图谱展示表 `nodes` / `edges`。

## 模块说明

- [data_process/graph_builder/models.py](data_process/graph_builder/models.py)：`GraphNode`、`GraphEdge`、`BuildGraphOptions` 数据类（节点/边是 builder 内部工作数据，区别于 ORM 的 `Node`/`Edge`）。
- [data_process/graph_builder/processor.py](data_process/graph_builder/processor.py)：文本清洗、分词、Jaccard 相似度、边生成、`top_k_value` 计算。包含 CPU 与 GPU（cuPy）两种实现，由 `--device` 选择。
- [data_process/graph_builder/database.py](data_process/graph_builder/database.py)：数据库连接、Schema 创建、源表读取、分批写入。
- [data_process/graph_builder/engine.py](data_process/graph_builder/engine.py)：建图流程编排。
- [data_process/graph_builder/main.py](data_process/graph_builder/main.py)：命令行入口（argparse）与 `.env` 读取。
- [data_process/graph_builder/builder.py](data_process/graph_builder/builder.py)：兼容导出层，保留旧 import 路径。

## 流程概览

1. `main.py` 读取 `.env`（优先 `DB_*`，其次 `POSTGRES_*`）与命令行参数。
2. `engine.py` 连接数据库并应用 Schema。
3. `database.py` 拉取 `lit_metadata` 与 `case_metadata`，构建节点。
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
- **范围**：所有出现在 `lit_metadata` 表中的文件都建 paper 节点（不再按 `core_file.document_type` 过滤）。这样同一份病例文件被抽取出的文献元数据也能和病案节点用 `ref` 边连通。

### record 节点（`case_metadata`）

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

- 通过 `file_uuid` 关联同一份文件的 `paper` 与 `record` 节点。
- `similarity_score` 与 `raw_score` 固定为 `1.0`。
- 之前若同一 `file_uuid` 既在 `lit_metadata` 又在 `case_metadata`，只有 `core_file.document_type = 0` 的文件被选作 paper 节点，导致 ref 边算不出来。现已修复：所有 `lit_metadata` 行都建 paper 节点。

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
# GPU（若环境装了 cuPy 且有 CUDA 设备）—— 推荐用于大数据量
python -m data_process.graph_builder.main --device cuda

# CPU 参考实现（默认）
python -m data_process.graph_builder.main --device cpu

# 自动选择：可用时用 GPU，否则回退到 CPU
python -m data_process.graph_builder.main             # 等价 --device auto

# 临时覆盖写入策略
python -m data_process.graph_builder.main --device cuda --strategy upsert
```

默认读取项目根目录 `.env`，并按 `DB_*` 优先、`POSTGRES_*` 兜底的顺序读取数据库配置。

## 命令行参数

| 参数 | 取值 | 默认 | 说明 |
|------|------|------|------|
| `--device` | `auto` / `cpu` / `cuda` | `auto` | 相似度边计算的执行后端。`auto` 会在检测到可用的 cuPy + CUDA 设备时使用 GPU，否则回退到 CPU。 |
| `--strategy` | `truncate` / `upsert` | 取自 `GRAPH_BUILDER_STRATEGY`（默认 `truncate`） | 写入策略，可直接用 CLI 覆盖而不改 `.env`。 |

## 环境变量

- `GRAPH_BUILDER_STRATEGY`：写入策略，支持 `truncate` / `upsert`
- `GRAPH_BUILDER_PAPER_TOP_K` / `GRAPH_BUILDER_RECORD_TOP_K`
- `GRAPH_BUILDER_PAPER_MIN_SCORE` / `GRAPH_BUILDER_RECORD_MIN_SCORE`

## GPU 加速

`processor.py` 的 `build_pair_edges` 在 `--device cuda` 下走 cuPy 路径：

1. 把每个节点的 token 集合编码为 0/1 稀疏矩阵 `X`（n × V）。
2. 用 cuSPARSE SpMM 计算 `X @ Xᵀ` 得到交集矩阵（n × n），再把每行分块以控制 GPU 显存（默认块大小 512）。
3. 按公式 `J = inter / (|a| + |b| - inter)` 计算每对非零项的 Jaccard。
4. 在 CPU 上对每行的候选邻居排序并取 Top K，避免重复边并接入到统一的 `GraphEdge` 数据结构里。

注意：

- 旧实现是 N 进程内浮现的两两 Python 循环，时间复杂度 O(n²)，节点过万时单线程跑数小时都跑不完。
- GPU 版本因矩阵相乘交给 cuSPARSE 处理，在 RTX 3080（10GB）上跑 n≈15500 个文献节点约 1 分钟内完成（含建库+写库），CPU 版本在同样规模下估算需要 2 小时以上。
- 阈值 `min_score` 与 `top_k` 与 CPU 实现保持一致；分数由于 float32 累加，末位可能差 1 个 ULP（万分位差 1），属可接受误差。

## 安装 GPU 依赖

仅 CPU 运行无需额外安装。如果希望启用 `--device cuda`：

```bash
# 与 CUDA Toolkit 版本对应的 cuPy wheel，例如 CUDA 11.x
pip install cupy-cuda11x
```

第一次使用时 cuPy 会在 `~/.cupy/kernel_cache` 编译部分 kernel，首次启动可能多花几秒。