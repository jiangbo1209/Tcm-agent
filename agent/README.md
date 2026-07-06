# 医疗 Agent 第一阶段

本目录按 `DOR_Agent_设计文档V2.docx` 中的命名组织，先完成第一阶段 Agent 内部能力。

## 当前链路

1. `analyzers/query_analyzer.py`：问题理解与检索改写。
2. `tools/retrieval/tool.py`：知识库检索工具入口。
3. `tools/retrieval/ragflow_client.py`：RAGFlow 检索客户端，封装 `POST /api/v1/retrieval`。
4. `tools/retrieval/evidence_processor.py`：证据去重、整理、标准化。
5. `services/answer_generator.py`：基于 evidence 和提示词调用 LLM 生成回答。
6. `tools/validation/tool.py`：医学指南校验入口，启用后会检索 RAGFlow 指南库。
7. `orchestrator/agent.py`：串联完整 Agent 主流程。
8. `orchestrator/response_builder.py`：组装最终响应。

## RAGFlow 检索配置

Agent 检索工具固定调用 RAGFlow，需要配置：

```env
RAGFLOW_BASE_URL=http://172.16.150.45:8012
RAGFLOW_API_KEY=你的API_KEY
RAGFLOW_LITERATURE_DATASET_ID=文献知识库ID
RAGFLOW_CASE_DATASET_ID=病案知识库ID
RAGFLOW_GUIDELINE_DATASET_ID=指南知识库ID
```

可选参数：

```env
RAGFLOW_REQUEST_TIMEOUT=30
RAGFLOW_SIMILARITY_THRESHOLD=0.2
RAGFLOW_VECTOR_SIMILARITY_WEIGHT=0.3
RAGFLOW_TOP_K=1024
RAGFLOW_KEYWORD=true
RAGFLOW_HIGHLIGHT=false
RAGFLOW_USE_KG=false
RAGFLOW_TOC_ENHANCE=false
```

## LLM 配置

后续默认按千问/Qwen 的 OpenAI-compatible 接口使用，配置全部来自环境变量：

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=你的千问API_KEY
LLM_MODEL=qwen-plus
LLM_TIMEOUT_SECONDS=120
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
```

如果你的中转站仍使用 `RELAY_API_KEY`，代码也兼容；但推荐 Agent 侧统一使用 `LLM_API_KEY`。

问题理解模块也支持 LLM 结构化输出，但默认仍走规则识别，避免开发和测试时频繁调用模型。需要开启时配置：

```env
AGENT_ENABLE_LLM_QUERY_ANALYSIS=true
```

## 医学安全校验

默认不启用指南校验。需要启用时配置：

```env
AGENT_ENABLE_GUIDELINE_VALIDATION=true
```

启用后流程为：

```text
生成回答
-> GuidelineRetriever 使用 RAGFLOW_GUIDELINE_DATASET_ID 检索指南/共识/规范片段
-> GuidelineChecker 使用 guideline_validation.md 和 LLM 校验回答风险
-> ValidationResult 返回 passed / risk_level / issues / suggested_revision
```

指南库主要用于安全边界校验，不作为普通问答的默认回答资料库。

## 表设计

第一阶段复用现有表：

- `users`：用户身份表。
- `conversations`：用户会话表。
- `messages`：完整聊天记录表。
- `search_history`：搜索行为记录表。

新增但暂不接业务逻辑：

- `conversation_memories`：会话记忆表，先建表。
- `agent_tool_runs`：工具调用观测表，用于排查检索参数、返回数量、耗时和错误。

## 运行检查

```powershell
python -m pytest agent\tests -q
```

简单跑一轮 Agent：

```powershell
python -c "from agent.dependencies import build_agent; from agent.schemas.chat import ChatRequest; r=build_agent().run(ChatRequest(question='多囊卵巢综合征有哪些文献证据？', top_k=3)); print(r.answer)"
```

运行前需要确认 RAGFlow 服务可访问，且三个 dataset id 与 `.env` 一致。

## 暂不做

- 长期记忆和 Memory 摘要逻辑。
- UI 聊天接口接入。

这些等第一阶段内部链路确认后再接。
