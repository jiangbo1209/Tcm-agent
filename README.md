# 中医大模型智能体与知识图谱平台（TCM-Agent Graph Platform）

**TCM-Agent** 融合 **数据处理**、**知识图谱呈现** 与 **Agent 智能对话** 三大能力，面向中医领域的高价值知识抽取与智能问答。

**核心业务痛点**：将海量非结构化的中医文献与临床病案自动化提炼为结构化医疗实体，通过知识图谱进行可视化串联，并最终由 Agent 对话系统为医生/科研人员提供智能问答与辅助诊疗。

**技术栈**：Python、FastAPI、SQLAlchemy、Vue 3、Vite、AntV G6、PostgreSQL、对象存储(S3/COS)、LLM（大模型）。

## 快速启动

### 环境准备

项目需要 **Python 3.10+**。当前推荐使用 `Tcm-agent` conda 环境。

```bash
# 创建环境（包含所有依赖）
conda env create -f environment.yml
conda activate Tcm-agent

# 安装 Playwright 浏览器（如需使用爬虫功能）
playwright install chromium

# 前端依赖
cd UI/frontend && npm install
```

### 初始化数据库

```bash
python scripts/init_db.py
```

### 启动后端

```bash
cd UI/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8011
```

### 启动前端

```bash
cd UI/frontend
npm run dev
```

访问 http://localhost:5500，注册账号后即可使用。

### 测试账号

先初始化数据库，再通过 CSV 批量创建用户：

```bash
# 1. 初始化数据库表
python scripts/init_db.py

# 2. 批量导入用户（参考 scripts/users.csv.example 准备 CSV）
python scripts/import_users.py scripts/users.csv
```

## 核心业务数据流

### 阶段一：数据处理层（Data Processing）

1. 用户上传文档至对象存储
2. 触发后台解析流程
3. 调用大模型抽取中医实体
4. 结构化结果写入 PostgreSQL 核心表
5. 通过 ETL 脚本建模生成图谱底表（Nodes/Edges）

```mermaid
graph LR

    classDef userAction fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef db fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#f57f17;
    classDef process fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef storage fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;

    subgraph Upload["📤 文件上传"]
        Start((开始)) --> UploadAction[上传 PDF]:::userAction
        UploadAction --> GenUUID[生成 UUID]:::process
        GenUUID --> SaveStorage[(保存到存储桶)]:::storage
        GenUUID --> InsertCoreFile[(CORE_FILE)]:::db
    end

    SaveStorage -.-> Scheduler{调度}:::process
    InsertCoreFile -.-> Scheduler

    Scheduler --> CrawlAction[爬虫/解析]:::process
    CrawlAction --> InsertLitMeta[(LIT_METADATA)]:::db


    Scheduler -- "pdf" --> LLMProcess[大模型提取]:::process
    LLMProcess --> InsertCase[(MED_CASE)]:::db

    InsertLitMeta --> End((完成)):::process
    InsertCase --> End
```

### 阶段二：KG 图谱应用层（Knowledge Graph）

FastAPI 后端从 PostgreSQL 读取 Nodes/Edges，提供 BFS 扩展与详情查询接口；前端使用 AntV G6 实现交互式力导向图渲染，支持分层扩展、高亮聚焦、节点搜索。

```mermaid
graph LR

    subgraph Data["🗄️ 数据层 (PostgreSQL)"]
        NODES[(nodes<br/>图谱节点)]
        EDGES[(edges<br/>相似边)]
        LIT[(lit_metadata<br/>文献元数据)]
        CASE[(case_metadata<br/>病案数据)]
    end

    subgraph Backend["⚙️ 后端 (FastAPI)"]
        GRAPH_REPO[GraphRepository<br/>图谱数据访问]
        GRAPH_SVC[GraphService<br/>BFS 扩展 / 详情聚合]
        SEARCH_REPO[SearchRepository<br/>全文搜索 / Facet 统计]
    end

    subgraph Frontend["🖥️ 前端 (Vue 3 + AntV G6)"]
        GRAPH_PAGE[Graph.vue<br/>图谱主页]
        GRAPH_VIEW[GraphView.vue<br/>G6 力导向图渲染]
        NODE_DETAIL[NodeDetail.vue<br/>节点详情面板]
        SEARCH_RESULTS[SearchResults.vue<br/>搜索结果 + 筛选]
    end

    NODES --> GRAPH_REPO
    EDGES --> GRAPH_REPO
    LIT --> GRAPH_REPO
    CASE --> GRAPH_REPO
    LIT --> SEARCH_REPO
    CASE --> SEARCH_REPO

    GRAPH_REPO --> GRAPH_SVC
    GRAPH_SVC -->|GET /api/graph/expand| GRAPH_PAGE
    GRAPH_SVC -->|GET /api/graph/node-detail| NODE_DETAIL
    GRAPH_SVC -->|GET /api/graph/search| GRAPH_PAGE
    SEARCH_REPO -->|POST /api/search| SEARCH_RESULTS

    GRAPH_PAGE --> GRAPH_VIEW
    GRAPH_VIEW -->|点击节点展开| GRAPH_PAGE
```

**图谱交互流程**：
1. 用户点击节点或输入搜索词，前端调用 `/api/graph/expand?seed_id=xxx&depth=N`
2. 后端 BFS 遍历 `edges` 表，收集可达节点
3. 前端 G6 增量渲染，支持滑块控制保留扩展层数
4. 点击节点显示详情面板，支持 PDF 预览下载

### 阶段三：Agent 对话系统（Agent Dialogue System）

基于 LLM 的智能问答系统，通过多工具协同实现中医领域的语义理解与知识检索。

```mermaid
graph TD

    classDef user fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef agent fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c;
    classDef tool fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef db fill:#fff9c4,stroke:#fbc02d,color:#f57f17;

    User[("👤 用户提问")]:::user --> Router[routing.py<br/>路由分析]:::agent

    Router -->|文献/病案检索| SearchTool[search_tool<br/>智能搜索]:::tool
    Router -->|图谱查询| GraphTool[graph_tool<br/>图谱扩展]:::tool
    Router -->|通用问答| LLM[LLM 直接回答]:::agent
    Router -->|多步推理| Orchestrator[orchestrator/<br/>多步编排]:::agent

    SearchTool --> Repo[GraphRepository<br/>PostgreSQL 搜索]:::db
    GraphTool --> Repo

    Orchestrator --> Analyzer[analyzers/<br/>意图分解]:::agent
    Analyzer --> SubQuery[子查询分发]:::agent
    SubQuery --> SearchTool
    SubQuery --> GraphTool

    SearchTool --> Result[结果聚合]:::agent
    GraphTool --> Result
    Orchestrator --> Result
    LLM --> Result
    Result --> Answer[("💬 最终回答")]:::user
```

**对话流程说明**：
1. 用户输入自然语言问题
2. `routing.py` 分析问题意图，路由到对应工具
3. **search_tool**：对 PostgreSQL 执行全文/模糊搜索，返回匹配的文献和病案
4. **graph_tool**：查询知识图谱节点，获取关联路径
5. **orchestrator**：复杂问题拆分为多步子查询，逐步推理
6. 所有工具结果汇集到 LLM，生成最终回答

**对话管理**：
- `conversations` 表维护多轮对话上下文
- `conversation_memories` 存储 LLM 记忆摘要
- `messages` 记录每条消息的 role 和 content
- Agent 工具调用轨迹写入 `agent_tool_runs` 表

---

## 项目目录与架构映射

```
.
├── UI                              # 用户界面
│   ├── backend                     # 后端 FastAPI 应用
│   │   ├── main.py                 # 入口（路由注册、S3/G6 初始化）
│   │   └── app/
│   │       ├── config.py           # 环境变量配置
│   │       ├── core/database.py    # PostgreSQL 同步/异步引擎
│   │       ├── auth/               # 认证模块（JWT + bcrypt）
│   │       ├── models/             # SQLAlchemy ORM 模型
│   │       ├── schemas/            # Pydantic 请求/响应模型
│   │       ├── routers/            # API 路由
│   │       ├── services/           # 业务逻辑层
│   │       ├── repositories/       # 数据访问层
│   │       └── storage/            # S3 对象存储客户端
│   └── frontend                    # 前端 Vue 3 应用
│       ├── src/
│       │   ├── api/                # 后端 API 调用
│       │   ├── components/         # 通用组件（GraphView、ChatInput 等）
│       │   ├── views/              # 页面组件（Graph、Search 等）
│       │   ├── stores/             # Pinia 状态管理
│       │   └── router/             # 路由配置
│       └── ...                     # Vite 构建配置
├── agent                           # Agent 对话系统
│   ├── routing.py                  # 问题路由与意图识别
│   ├── orchestrator/               # 多步推理编排
│   ├── analyzers/                  # 查询意图分解
│   ├── services/                   # LLM 客户端、答案生成
│   ├── prompts/                    # LLM Prompt 模板
│   ├── tools/                      # Agent 工具（search、graph、validate）
│   └── memory/                     # 对话记忆管理
├── data_process                    # 离线数据处理脚本
│   ├── lit_metadata/               # 文献元数据爬取
│   ├── case_metadata/              # 病案大模型提取
│   ├── graph_builder/              # Nodes/Edges 离线建图
│   ├── ai_summary/                 # AI 摘要生成
│   ├── ragflow_sync/               # RAGFlow 文档同步
│   ├── guideline_metadata/         # 指南元数据
│   ├── pdf_upload/                 # TUI 上传工具
│   └── db_init.py                  # 数据库表初始化
├── scripts                         # 管理脚本
│   ├── init_db.py                  # 初始化所有数据库表
│   ├── import_users.py             # 从 CSV 批量导入用户
│   └── users.csv.example           # 用户导入模板
├── docker-compose.yaml
├── docker/
└── docs/
```

### 数据处理入口

数据库表结构初始化（业务表 + 图谱表）：

```bash
python scripts/init_db.py
```

离线生成图谱底表 `nodes` / `edges`：

```bash
python -m data_process.graph_builder.main
```

### 终端上传工具 (TUI)

TUI 是一个独立的命令行客户端，运行在本地电脑，通过 HTTPS+JWT 连接到部署在云服务器的 UI/backend：

```bash
# 1. 配置 API 地址
export TCM_API_BASE_URL=https://api.example.com:8011

# 2. 启动 TUI（首次会要求登录）
python data_process/pdf_upload/pdf_manager_tui.py
```

## 数据库建模

所有表均位于同一 PostgreSQL 数据库，按功能域分为三组。

**初始化方式**：
- 所有表通过 `python scripts/init_db.py` 统一创建（幂等，可重复执行）
- 图谱数据需额外通过 `python -m data_process.graph_builder.main` 离线构建填充

### 1. 用户与对话

```mermaid
erDiagram

    users {
        int id PK "自增主键"
        string username "用户名，唯一"
        string email "邮箱，唯一"
        string password_hash "bcrypt 哈希"
        string role "normal | professional"
        datetime created_at
    }

    conversations {
        int id PK "自增主键"
        int user_id FK "关联 users"
        string title "对话标题"
        datetime created_at
        datetime updated_at
    }

    messages {
        int id PK "自增主键"
        int conversation_id FK "关联 conversations"
        string role "user | assistant"
        text content "消息内容"
        json metadata "扩展元数据"
        datetime created_at
    }

    conversation_memories {
        int id PK "自增主键"
        int conversation_id FK "关联 conversations"
        text summary "LLM 记忆摘要"
        datetime created_at
    }

    agent_tool_runs {
        int id PK "自增主键"
        int conversation_id FK "关联 conversations"
        string tool_name "工具名称"
        json input "输入参数"
        json output "输出结果"
        datetime created_at
    }

    search_history {
        int id PK "自增主键"
        int user_id FK "关联 users"
        string query "搜索关键词"
        string search_type "literature | case | both"
        int result_count "结果数量"
        datetime created_at
    }

    users ||--o{ conversations : "拥有"
    conversations ||--o{ messages : "包含"
    conversations ||--o{ conversation_memories : "记忆"
    conversations ||--o{ agent_tool_runs : "工具调用"
    users ||--o{ search_history : "搜索"
```

### 2. 文献与病案

```mermaid
erDiagram

    CORE_FILE {
        string file_uuid PK "UUID 主键"
        string original_name "原始文件名"
        string storage_path "S3 存储路径"
        string file_type "文件类型（如 pdf）"
        datetime upload_time "上传时间"
        bool status_metadata "文献元数据是否已提取"
        bool status_case "病案数据是否已提取"
        bool status_guidelinemeta "指南元数据是否已提取"
        bool status_ragflow "是否已同步 RAGFlow"
        int document_type "0=文献 1=病案 2=指南"
        int uploader_id "上传用户 ID（逻辑外键）"
    }

    LIT_METADATA {
        int id PK "自增主键"
        string file_uuid FK "外键，关联 CORE_FILE，唯一"
        string original_name "原始文件名"
        string storage_path "S3 路径"
        string cleaned_title "清洗后标题"
        string title "论文标题"
        json authors "作者列表"
        text abstract "摘要"
        json keywords "关键词列表"
        string paper_type "文献类型（期刊论文/学位论文）"
        string source_site "来源网站"
        text source_url "来源 URL"
        string journal "期刊名称"
        string pub_year "发表年份"
        string matched_title "匹配标题"
        bool is_exact_match "是否精确匹配"
        string crawl_status "爬取状态（success/partial/failed）"
        text error_message "错误信息"
        text ai_summary "AI 摘要"
        string ai_summary_status "摘要生成状态"
        datetime created_at
        datetime updated_at
    }

    MED_CASE {
        int id PK "自增主键"
        string file_uuid FK "外键，关联 CORE_FILE"
        text age "年龄"
        text bmi "BMI"
        text menstruation "月经情况"
        text infertility "不孕情况"
        text lifestyle "生活习惯"
        text present_symptoms "刻下症"
        text medical_history "既往病史"
        text lab_tests "生化检查"
        text ultrasound "超声检查"
        text followup "复诊情况"
        text western_diagnosis "西医诊断"
        text tcm_diagnosis "中医证候诊断"
        text treatment_principle "治法"
        text prescription "方剂"
        text acupoints "针刺选穴"
        text assisted_reproduction "辅助生殖技术"
        text western_medicine "西药"
        text efficacy "疗效评价"
        text adverse_reactions "不良反应"
        text commentary "按语/评价说明"
        datetime created_at
        datetime updated_at
    }

    GUIDELINE_METADATA {
        int id PK "自增主键"
        string file_uuid FK "外键，关联 CORE_FILE"
        string title "指南标题"
        json authors "作者列表"
        text abstract "摘要"
        json keywords "关键词"
        string paper_type "文献类型"
        string source_site "来源"
        string journal "期刊"
        string pub_year "年份"
        datetime created_at
        datetime updated_at
    }

    CORE_FILE ||--o| LIT_METADATA : "一篇文献"
    CORE_FILE ||--o| MED_CASE : "一个病案"
    CORE_FILE ||--o| GUIDELINE_METADATA : "一个指南"
```

### 3. 知识图谱

```mermaid
erDiagram

    NODES {
        string id PK "节点 ID"
        string node_type "paper | record"
        string title "节点标题"
        int metric_value "数值（年份/年龄）"
        float top_k_value "Top-K 相似度值"
        datetime created_at
        datetime updated_at
    }

    EDGES {
        string id PK "SHA1 边 ID"
        string source_id FK "源节点 ID"
        string target_id FK "目标节点 ID"
        string edge_type "相似边类型"
        float similarity_score "相似度分数"
        float raw_score "原始分数"
        datetime created_at
        datetime updated_at
    }

    NODES ||--o{ EDGES : "源节点"
    NODES ||--o{ EDGES : "目标节点"
```

---

## 后端 API 总览

| 模块 | 路径 | 说明 | 权限 |
|------|------|------|------|
| 认证 | `POST /api/auth/register` | 注册 | 公开 |
| 认证 | `POST /api/auth/login` | 登录 | 公开 |
| 对话 | `GET/POST /api/chat/conversations` | 对话 CRUD | 登录 |
| 对话 | `GET/POST /api/chat/conversations/{id}/messages` | 消息读写 | 登录 |
| 搜索 | `POST /api/search` | 智能搜索（全文+筛选+Facet） | 专业用户 |
| 搜索 | `GET /api/search/history` | 搜索历史 | 登录 |
| 图谱 | `GET /api/graph/expand` | BFS 扩展 | 登录 |
| 图谱 | `GET /api/graph/node-detail` | 节点详情 | 登录 |
| 图谱 | `GET /api/graph/search` | 图谱节点搜索 | 登录 |
| 图谱 | `GET /api/graph/file-url/{node_id}` | PDF 访问链接 | 登录 |
| 文件 | `POST /api/files/upload` | 单文件上传 | 登录 |
| 文件 | `POST /api/files/batch-upload` | 批量上传 | 登录 |
| 文件 | `DELETE /api/files/{file_uuid}` | 文件删除 | 登录 |
| 管理 | `GET/PUT /api/admin/{table}/{id}` | 元数据编辑 | 管理员 |
| 管理 | `DELETE /api/admin/lit/{id}` | 删除文献（级联删除病案+文件） | 管理员 |
| 管理 | `DELETE /api/admin/case/{id}` | 删除病案（不影响文献） | 管理员 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_SECRET_KEY` | tcm-agent-secret-key... | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | 1440 | Token 过期时间（分钟） |
| `POSTGRES_HOST` | 127.0.0.1 | PostgreSQL 地址 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `POSTGRES_USER` | postgres | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | (空) | PostgreSQL 密码 |
| `POSTGRES_DB` | postgres | PostgreSQL 数据库名 |
| `S3_ENDPOINT` | https://cos.ap-beijing.myqcloud.com | 对象存储地址 |
| `S3_ACCESS_KEY` | (空) | SecretId |
| `S3_SECRET_KEY` | (空) | SecretKey |
| `S3_BUCKET_NAME` | tcm-documents-xxx | COS 存储桶名 |
| `S3_REGION` | ap-beijing | COS 地域 |
| `SEARCH_BACKEND_MODE` | auto | 搜索后端（auto/fulltext/like） |
