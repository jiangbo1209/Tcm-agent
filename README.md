# 🧠 中医大模型智能体与知识图谱平台（TCM-Agent Graph Platform）

**TCM-Agent Graph Platform** 是一个基于 Monorepo（单体仓库）架构的先进 GraphRAG 平台，融合 **数据处理**、**知识图谱呈现** 与 **Agent 智能对话** 三大能力，面向中医领域的高价值知识抽取与智能问答。

**核心业务痛点**：将海量非结构化的中医文献与临床病案自动化提炼为结构化医疗实体，通过知识图谱进行可视化串联，并最终由 Agent 对话系统为医生/科研人员提供智能问答与辅助诊疗。

**技术栈**：Python、FastAPI、AntV G6、MySQL、MinIO、Docker、LLM（大模型）。

---

## 🔄 核心业务数据流（Data Workflow）

**阶段一：数据处理层（Data Processing）**
1. 用户上传文档至 MinIO
2. 触发后台解析流程
3. 调用大模型抽取中医实体
4. 结构化结果写入 MySQL 核心表
5. 通过 ETL 脚本建模生成图谱底表（Nodes/Edges）

**阶段二：KG 图谱应用层（Knowledge Graph）**
1. FastAPI 后端提供图数据检索与 BFS 扩展接口
2. 前端 AntV G6 实现交互式高亮渲染与节点探索

**阶段三：Agent 对话系统（Agent Dialogue System）**
1. 基于大模型与知识图谱（GraphRAG）进行语义增强
2. 提供自然语言对话界面
3. 支持病案溯源、智能问答与关联分析

---

## 🧭 项目目录与架构映射（Directory Structure）

```
.
├── agent/                     # Agent 对话系统与核心大模型交互模块
├── data_modeling/             # 数据处理层（清洗、建模、ETL 建图脚本）
├── knowledge_graph/TCM-code/  # 图谱应用层（backend + frontend）
│   ├── backend/
│   └── frontend/
├── configs/                   # 环境配置
├── data/                      # 持久化数据挂载卷（Git 忽略）
├── docker-compose.yaml        # 联调基础设施
├── .env.example               # 环境变量模板
└── README.md

## 🛠️ 开发者协同指南（Developer Guide）

### ✅ 联调策略：分离调试 + 全链路联调

**分离调试（本地断点）**

仅启动基础设施，然后在各子模块目录中使用本地 IDE 断点调试：

```bash
docker compose up -d mysql minio
```

在本地模块中读取 `.env`，以 127.0.0.1 连接数据库，即可进行独立开发调试。

**全链路联调（服务组合）**

通过 Compose 启动指定模块进行精准联调：

```bash
docker compose up -d kg-backend kg-frontend
```

### 🌿 Git 协作与分支规范

**主干分支模型**：`main` / `master` 作为稳定主干，功能开发通过特性分支合并。

**分支命名规则**：
- `feat/agent-xxx`
- `feat/data-xxx`
- `feat/kg-xxx`
- `fix/agent-xxx`
- `fix/kg-xxx`

**Conventional Commits 提交规范**：

```
<type>(<scope>): <subject>
```

示例：
- `feat(agent): add dialogue router`
- `fix(kg): handle bfs pagination`
- `chore(infra): update docker compose`

常用 type：`feat`、`fix`、`chore`、`docs`、`refactor`、`test`。
