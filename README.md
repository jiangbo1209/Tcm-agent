# 中医大模型智能体与知识图谱平台（TCM-Agent Graph Platform）

**TCM-Agent** 融合 **数据处理**、**知识图谱呈现** 与 **Agent 智能对话** 三大能力，面向中医领域的高价值知识抽取与智能问答。

**核心业务痛点**：将海量非结构化的中医文献与临床病案自动化提炼为结构化医疗实体，通过知识图谱进行可视化串联，并最终由 Agent 对话系统为医生/科研人员提供智能问答与辅助诊疗。

**技术栈**：Python、FastAPI、AntV G6、PostgreSQL、MinIO、Docker、LLM（大模型）。

## 核心业务数据流（Data Workflow）

**阶段一：数据处理层（Data Processing）**
1. 用户上传文档至 MinIO
2. 触发后台解析流程
3. 调用大模型抽取中医实体
4. 结构化结果写入 PostgreSQL 核心表
5. 通过 ETL 脚本建模生成图谱底表（Nodes/Edges）

```mermaid
graph TD

    %% 定义样式

    classDef userAction fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef db fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#f57f17;
    classDef process fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef minio fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;

    %% --- 阶段 1: 文件上传 ---

    Start((开始)) --> UploadAction[用户上传 PDF 文件]:::userAction
    UploadAction --> GenUUID[后端生成 UUID]:::process
    GenUUID --> SaveMinio[保存文件到 MinIO]:::minio
    SaveMinio --> InsertCoreFile[(插入 CORE_FILE 表<br/>status_metadata=false<br/>status_case=false)]:::db

    %% --- 调度/轮询层 ---

    InsertCoreFile -.-> Scheduler{手动调度}:::process

    %% --- 阶段 2: 文献元数据提取 ---

    Scheduler -- "轮询 status_metadata=false" --> QueryMeta[查询待处理文献]:::process
    QueryMeta --> CrawlAction[调用爬虫/解析器]:::process
    CrawlAction --> InsertLitMeta[(插入 LIT_METADATA 表)]:::db
    InsertLitMeta --> UpdateMetaStatus[更新 		CORE_FILE<br/>status_metadata=true]:::db

    %% --- 阶段 4: 病案解析 ---

    Scheduler -- "轮询 status_case=false" --> QueryCase[查询待处理病案]:::process
    QueryCase --> DownloadPDF[从 MinIO 下载 PDF]:::minio
    DownloadPDF --> LLMProcess[调用大模型 API 提取]:::process
    LLMProcess --> ParseJSON[解析 JSON 数据]:::process
    ParseJSON --> InsertCase[(插入 MED_CASE 表)]:::db
    InsertCase --> UpdateCaseStatus[更新 CORE_FILE<br/>status_case=true]:::db

    %% --- 结束 ---
    UpdateMetaStatus --> End((处理完成)):::process
    UpdateCaseStatus --> End
```


**阶段二：KG 图谱应用层（Knowledge Graph）**
1. FastAPI 后端提供图数据检索与 BFS 扩展接口
2. 前端 AntV G6 实现交互式高亮渲染与节点探索

**阶段三：Agent 对话系统（Agent Dialogue System）**
1. 基于大模型与RAG进行语义增强
2. 提供自然语言对话界面
3. 支持病案溯源、智能问答与关联分析

---

## 项目目录与架构映射（Directory Structure）

```
.
├── UI                              # 用户界面
│   ├── backend                     # 后端
│   │   ├── app
│   │   └── scripts
│   └── frontend                    # 前端
│       └── src
├── agent                           # agent
├── configs
│   ├── nginx
│   └── sql
├── data_process                    # 数据处理
│   ├── case_metadata               # 病案元数据提取
│   ├── lit_metadata                # 文献元数据提取
│   └── pdf_upload                  # 文件上传建立数据库
└── docker                          # docker配置文件

```

### Git 协作与分支规范

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

## 数据库建模

```mermaid
erDiagram

    %% 1. 文件核心表：MinIO 映射
    CORE_FILE {
        string file_uuid PK "主键，自动生成"
        string original_name "原始文件名"
        string storage_path "MinIO 中的存储路径"
        string file_type "文件类型"
        datetime upload_time "上传时间"
        bool status_matadata "文献元数据处理状态"
        bool status_case "病案处理状态"
    }

    %% 2. 文献元数据表：爬虫数据

    LIT_METADATA {
        int id PK "自增主键"
        string file_uuid FK "外键，关联 CORE_FILE"
        string title "论文标题"
        string cleaned_title "清洗后论文标题"
        string author "作者列表"
        string institution "机构"
        string publish_date "发表时间"
        string source "来源期刊"
        string abstract "摘要"
        string keywords "关键词"
        string type "文献类型"
        string matadata_url "来源url"
        string doi "DOI号"

    }

  

    %% 3. 病例记录表：大模型提取的核心数据

    MED_CASE {
        int id PK "自增主键"
        string file_uuid FK "外键，关联 CORE_FILE"
        string patient_id "患者ID（脱敏）"
        string diagnosis "中医诊断/西医诊断"
        string syndrome "证型（如：气阴两虚）"
        string treatment_principle "治法"
        text prescription "处方内容"
        string efficacy "疗效"

    }

    
    
    %% 关系定义
    CORE_FILE ||--|{ LIT_METADATA : "包含"
    CORE_FILE ||--|{ MED_CASE : "提取自"

```