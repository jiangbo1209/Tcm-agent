# 医疗 Agent

## 1. 模块定位

`agent` 是医疗对话的核心工作流模块，负责问题理解、意图路由、上下文工程、RAGFlow 检索、引用整理、LLM 流式回答和可选的指南校验。

Agent 不再单独启动调试用 FastAPI 服务。当前生产调用链是：

```text
前端
  -> UI 后端 /api/chat/conversations/{conversation_id}/messages
  -> Agent.run_stream()
  -> RAGFlow / LLM / 可选指南校验
  -> UI 后端 SSE
  -> 前端
```

前端只调用 UI 后端，Agent 作为 UI 后端进程内的业务模块运行。

## 2. 目录结构

```text
agent/
├── analyzers/
│   └── query_analyzer.py       # 问题初步理解，生成 QueryPlan
├── memory/
│   ├── models.py               # Memory 常量
│   ├── repository.py           # 只读会话消息和摘要，不持有 ORM
│   ├── context_builder.py      # ORM 行转换为 MemoryContext
│   ├── context_engine.py       # 上下文选择、排序和 ContextPack
│   ├── prompt_context.py       # ContextPack 入口和格式化
│   ├── resolver.py             # 追问、引用编号和上下文指代解析
│   ├── schemas.py              # Memory、用户偏好、上下文结构
│   ├── service.py              # Memory 统一入口
├── orchestrator/
│   ├── agent.py                # Agent 主工作流和 SSE 事件
│   └── response_builder.py     # 组装最终 ChatResponse
├── prompts/                   # 问题理解、回答和校验 Prompt
├── schemas/                   # QueryPlan、Evidence、Response、StreamEvent
├── services/
│   ├── answer_generator.py     # Prompt 路由、LLM 回答、引用生成
│   ├── llm_client.py           # OpenAI-compatible Chat Completions 客户端
├── tools/
│   ├── retrieval/              # RAGFlow 调用、证据整理和去重
│   └── validation/             # 可选指南检索和回答校验
├── routing.py                  # 任务路由和回答结构契约
├── routing_terms.py            # 统一维护路由、追问、上下文和证据关键词
├── config.py                   # .env 和环境变量配置
├── dependencies.py             # Agent 依赖组装入口
└── tests/                      # Agent 单元测试
```

## 3. 完整工作流

`MedicalAgent.run_stream()` 的标准流程如下：

```text
1. 规范化用户问题
2. QueryAnalyzer 生成 QueryPlan
3. routing.py 应用任务路由
4. KnowledgeRetrievalTool 执行 RAGFlow 检索
5. EvidenceProcessor 整理、去重并分配引用编号
6. AnswerGenerator 构造 ContextPack 和路由 Prompt
7. LLM 流式生成回答
8. 可选执行指南库检索和回答校验
9. ResponseBuilder 组装最终响应
```

面向 UI 的回答只保留流式链路：`MedicalAgent.run_stream()` 和 `AnswerGenerator.stream_generate()`。非流式回答入口已删除。

来源追问有单独分支：

```text
用户提到“文献1 / 来源2 / 引用[3]”
  -> 从 MemoryContext 定位指定引用
  -> retrieval_required = false
  -> 只把指定来源交给回答模型和前端
```

如果用户明确要求“全部引用来源”“所有文献都展开”，则保留上一轮全部引用；普通的新问题仍然正常执行 RAGFlow 检索。

## 4. 问题理解和意图路由

### 4.1 QueryAnalyzer

`QueryAnalyzer` 支持两种初步识别模式：

- 规则模式：默认启用，通过医学关键词命中情况生成基础 `QueryPlan`。
- LLM 模式：设置 `AGENT_ENABLE_LLM_QUERY_ANALYSIS=true` 后，先让 LLM 输出结构化 JSON；解析失败时自动回退到规则模式。

当前默认关闭 LLM 初步识别，因此默认链路是：

```text
关键词规则初判 -> routing.py 二次路由 -> 检索和回答
```

开启 LLM 初步识别后是：

```text
LLM 结构化初判 -> routing.py 规则校正 -> 检索和回答
```

### 4.2 当前任务路由

路由由 `routing.py` 根据问题关键词、初始意图和历史上下文确定，当前包括：

| 任务类型 | 主要用途 | 默认回答模式 |
| --- | --- | --- |
| `source_detail` | 指定或批量展开上一轮来源 | 来源详情 |
| `report_interpretation` | 检查报告、化验和指标解释 | 报告解读 |
| `assisted_reproduction_stages` | 降调、促排、移植、黄体支持等分阶段问题 | 阶段指导 |
| `safety_risk` | 风险、禁忌、不良反应和就医信号 | 安全风险 |
| `option_comparison` | 方案比较、适用条件和优缺点 | 方案对比 |
| `case_analysis` | 个体病例和结构化病例分析 | 病例分析 |
| `case_review` | 病案经验和治疗思路复盘 | 病案复盘 |
| `literature_evidence` | 文献、研究、综述和证据问题 | 证据总结 |
| `patient_education` | 通俗解释、生活指导和注意事项 | 患者宣教 |
| `follow_up` | 一般连续追问 | 追问回答 |
| `general_qa` | 无法归入专门路由的问题 | 通用回答 |

### 4.3 Prompt 路由

`AnswerGenerator` 根据 `answer_mode` 和 `evidence_status` 选择 Prompt：

- `source_detail` -> `prompts/source_detail.md`
- 有本轮证据 -> `prompts/grounded_answer.md`
- 没有足够证据 -> `prompts/general_answer.md`
- 指南校验 -> `prompts/guideline_validation.md`

路由契约由 `route_contract()` 生成，用于向 Prompt 传递回答重点、角色要求、风险等级和格式约束。回答格式不是所有问题共用一个固定模板，而是由当前任务路由决定。

## 5. 上下文工程

`ContextEngine` 生成发送给问题理解和回答 Prompt 的 `ContextPack`。当前顺序固定为：

1. 当前用户问题 `current_question`
2. 当前上下文计划 `context_plan`
3. 当前任务角色与用户偏好 `user_context`
4. 当前病例结构化信息 `current_case`
5. 本轮 RAGFlow 检索证据 `retrieval_evidence`
6. 引用来源定位信息 `citation_context`
7. 与当前问题相关的历史记忆 `relevant_history`
8. 回答风格和输出约束 `answer_constraints`
9. 医学安全边界 `medical_safety`

上下文选择规则：

- 普通新问题：只保留与问题相关的少量历史内容。
- 连续追问：读取滚动摘要和最近消息，默认 Memory 服务保留最近 8 条原文消息。
- 病例问题：从历史用户消息和当前问题中提取年龄、AMH、FSH、LH、诊断、证型等结构化事实。
- 来源追问：根据编号筛选上一轮对应引用，避免把其他来源送进模型。
- 全部来源追问：保留上一轮全部引用，但仍限制来源数量和片段长度。

历史记忆的数据库读取由 UI 后端完成：

```text
UI AgentMemoryAdapter
  -> ConversationMemoryRepository
  -> MemoryContextBuilder
  -> MemoryService
  -> MemoryContext
  -> ContextEngine
  -> ContextPack
```

Agent Memory 不拥有 UI 后端 ORM，只依赖 Repository 接口和稳定的领域结构，因此后续可以替换数据库实现或增加摘要存储。

### 滚动会话摘要

会话记忆同时使用 `messages` 和 `conversation_memories`：

```text
conversation_memories.session_summary
  + 最近 8 条 messages 原文
  -> MemoryContext
  -> ContextPack
```

每轮助手消息保存后，Memory 服务会检查是否有消息落在最近 8 条窗口之外。被挤出的旧消息会与已有摘要合并，更新同一条 active `session_summary`；`covered_message_id` 记录摘要已覆盖到的最后一条消息，避免重复压缩或遗漏历史。

摘要生成使用 LLM 的非流式内部调用，不影响面向用户的流式回答。摘要服务异常时会退回到确定性文本压缩，助手消息和当前会话不会因此保存失败。`referenced_sources_summary` 会保留归档历史中的关键来源，并与近期来源合并用于上下文提示；它们不能作为本轮医学检索证据。

## 6. RAGFlow 检索和引用来源

`RagflowClient` 调用 RAGFlow：

```text
POST {RAGFLOW_BASE_URL}/api/v1/retrieval
```

根据 `QueryPlan.search_type` 选择知识库：

- `literature`：文献知识库
- `case`：病案知识库
- `guideline`：指南知识库
- `both`：文献和病案知识库

`EvidenceProcessor` 会完成：

- 统一 RAGFlow 返回字段
- 从 chunk、metadata、嵌套文件对象中提取 `file_uuid`
- 按文件、文档或 chunk 去重
- 分配本轮引用编号

`RagflowClient` 在检索结果没有完整文件元数据时，会按文档查询 RAGFlow 文档元数据进行补全。引用来源会返回标题、摘要片段、文件 UUID、作者、期刊、年份等信息。

当前文件查看链路是：

```text
前端点击引用来源
  -> UI 后端根据 file_uuid 查询业务数据库
  -> 获取文件记录和对象存储 key
  -> 从 MinIO 或 S3-compatible 存储生成预签名链接
  -> 前端打开源文件
```

因此 `file_uuid` 是引用来源能够定位原文件的关键字段，RAGFlow 元数据和业务数据库记录必须保持一致。

## 7. 证据状态和医学边界

检索结果主要分为：

- `grounded`：证据与问题存在直接医学锚点，可作为本轮回答依据。
- `weak_evidence`：检索到了内容，但不足以直接支撑当前问题，回答不能把它当作直接证据。
- `no_direct_evidence`：没有可用的直接检索证据，允许 LLM 提供一般医学知识，但必须明确说明没有本地知识库直接支撑。
- `source_only`：来源追问，不重新检索知识库，基于上一轮引用上下文回答。

系统提示词和回答 Prompt 共同约束：不能编造文献、指南、数据、疗效、剂量或引用；涉及具体诊疗、孕期、用药和风险问题时，必须保留医学安全边界。

## 8. SSE 事件

Agent 核心流事件顺序为：

```text
started
query_plan
retrieval_done
answer_delta (多个)
answer_done
validation_done (启用校验时)
done
```

异常时发送：

```text
error
```

UI 后端会把 Agent 的 `answer_delta` 转成前端使用的 SSE 内容流，并在流结束后保存助手消息、QueryPlan、引用、校验结果和工具轨迹。

## 9. 核心数据结构

### ChatRequest

```json
{
  "question": "多囊卵巢综合征有哪些文献证据？",
  "user_id": 1,
  "conversation_id": 123,
  "top_k": 3,
  "memory_context": {},
  "user_context": {}
}
```

### QueryPlan

主要字段包括：

- `intent`：初步意图
- `task_type`：最终任务类型
- `answer_mode`：回答 Prompt 路由
- `search_type`：文献、病案、指南或混合检索
- `retrieval_strategy`：单查询、多查询、来源定向等策略
- `rewritten_query`：发送给 RAGFlow 的查询
- `sub_queries`：多阶段问题拆分后的查询
- `risk_level`：风险等级
- `retrieval_required`：是否需要重新检索

### ReferenceSource

主要字段包括：

- `index`：回答中的引用编号
- `title`：来源标题
- `file_uuid`：业务数据库和对象存储定位依据
- `snippet`：来源片段
- `source_type`：文献、病案或指南
- `authors`、`journal`、`year`：来源元数据

## 10. 配置

所有配置从项目根目录 `.env` 或系统环境变量读取。系统环境变量优先于 `.env`。

### LLM

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode
LLM_API_KEY=你的API_KEY
LLM_MODEL=qwen-plus
LLM_AUTH_HEADER=Authorization
LLM_TIMEOUT_SECONDS=120
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
```

如果 `LLM_BASE_URL` 已经包含 `/v1/chat/completions`，客户端会直接使用该地址；否则会自动拼接 `/v1/chat/completions`。

### 问题理解和指南校验

```env
# 是否启用 LLM 初步意图识别，默认 false
AGENT_ENABLE_LLM_QUERY_ANALYSIS=false

# 是否启用指南库检索，默认 false
AGENT_ENABLE_GUIDELINE_RETRIEVAL=false

# 是否启用回答后的指南校验，默认 false
AGENT_ENABLE_GUIDELINE_VALIDATION=false
```

### RAGFlow

```env
RAGFLOW_BASE_URL=http://127.0.0.1:9380
RAGFLOW_API_KEY=你的RAGFlow_API_KEY
RAGFLOW_LITERATURE_DATASET_ID=文献知识库ID
RAGFLOW_CASE_DATASET_ID=病案知识库ID
RAGFLOW_GUIDELINE_DATASET_ID=指南知识库ID
RAGFLOW_REQUEST_TIMEOUT=30
RAGFLOW_TOP_K=1024
RAGFLOW_SIMILARITY_THRESHOLD=0.2
RAGFLOW_VECTOR_SIMILARITY_WEIGHT=0.3
RAGFLOW_KEYWORD=true
RAGFLOW_HIGHLIGHT=false
RAGFLOW_USE_KG=false
RAGFLOW_TOC_ENHANCE=false
```

### 其他

```env
AGENT_DEFAULT_TOP_K=6
AGENT_MEMORY_RECENT_MESSAGE_LIMIT=8
AGENT_MEMORY_SUMMARY_MAX_CHARS=4000
```

不要把真实 API Key、数据库密码或对象存储密钥提交到 Git。

## 11. 运行和测试

安装 Agent 依赖：

```powershell
pip install -r agent\requirements.txt
```

运行 Agent 测试：

```powershell
python -m pytest agent\tests -q
```

当前 Agent 没有独立的服务端口。启动 UI 后端后，由 UI 后端代理前端请求并调用 Agent。修改 Agent 的 Python 代码或 `.env` 后，如果没有启用自动重载，需要重启 UI 后端。

## 12. 后续迭代建议

### 可以优先优化的地方

1. 所有规则关键词已统一放在 `routing_terms.py`；新增或调整关键词时，只在该文件维护，再补充对应路由测试。
2. 开启 `AGENT_ENABLE_LLM_QUERY_ANALYSIS` 后，增加 QueryPlan 结构化输出的监控和失败样本记录，持续修正规则兜底。
3. 将 `ContextEngine` 的历史选择、病例事实抽取、引用选择拆成可独立测试的策略，后续支持更精细的上下文排序。
4. 为 RAGFlow 检索增加召回、重排、证据相关性和最终引用准确率指标。
5. `RagflowClient` 的文档元数据补全目前可能产生逐文档请求，文献量增大后应增加批量查询或缓存。
6. 为 Prompt 路由增加版本号和离线回归集，避免修改模板后影响已有问题类型。
7. 继续优化滚动摘要触发条件，例如按 token 预算或病例信息变化触发，并保留最近消息与结构化病例事实。

## 13. 新增能力时的推荐修改位置

新增一种问题类型时，建议按以下顺序修改：

1. 在 `schemas/query.py` 确认需要的 `QueryPlan` 字段。
2. 在 `routing_terms.py` 增加或调整关键词，并在 `query_analyzer.py` 调整规则或 LLM 输出约束。
3. 在 `routing.py` 增加任务路由、检索策略和回答结构契约。
4. 在 `prompts/` 新增或调整对应 Prompt。
5. 在 `answer_generator.py` 增加 Prompt 选择条件或证据处理逻辑。
6. 在 `ContextEngine` 中明确需要哪些历史、病例、引用和用户偏好。
7. 增加真实问题的路由、检索、引用和流式输出测试。

这样可以保持“意图识别、路由、上下文、Prompt、检索、回答”之间的边界，方便后续逐步迭代。
