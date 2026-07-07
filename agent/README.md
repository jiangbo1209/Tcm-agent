# 医疗 Agent 第一版

本目录实现第一版可控工作流 Agent，用于问题理解、RAGFlow 检索、基于证据回答、参考来源返回和可选指南核对。

## 当前链路

1. `analyzers/query_analyzer.py`：识别问题类型并生成 `QueryPlan`。
2. `tools/retrieval/ragflow_client.py`：调用 RAGFlow `POST /api/v1/retrieval`。
3. `tools/retrieval/evidence_processor.py`：整理 evidence，去重，分配引用编号。
4. `services/answer_generator.py`：把问题、检索证据和引用编号交给 LLM 生成回答。
5. `tools/validation/tool.py`：可选调用指南库做回答依据核对。
6. `orchestrator/response_builder.py`：组装最终 `ChatResponse`。

## 主要返回字段

- `answer`：给用户展示的回答正文，包含 `[1]`、`[2]` 等引用编号。
- `references`：给前端展示的参考来源列表，包含 `file_uuid`、标题、片段、作者、期刊、年份等，不返回相似度分数。
- `evidence`：原始检索证据，主要用于调试和管理员排查。
- `validation`：回答依据状态，包含：
  - `grounded`：是否基于知识库检索结果。
  - `message`：依据说明。没有命中知识库时会说明回答基于普通医学知识。
  - `issues`：可选指南核对发现的需要谨慎表述的问题。

## 必填配置

```env
RAGFLOW_BASE_URL=http://172.16.150.45:8012
RAGFLOW_API_KEY=你的RAGFlow_API_KEY
RAGFLOW_LITERATURE_DATASET_ID=文献知识库ID
RAGFLOW_CASE_DATASET_ID=病案知识库ID
RAGFLOW_GUIDELINE_DATASET_ID=指南知识库ID

LLM_PROVIDER=openai
LLM_BASE_URL=你的模型接口地址
LLM_API_KEY=你的API_KEY
LLM_MODEL=你的模型名
```

开启指南核对：

```env
AGENT_ENABLE_GUIDELINE_VALIDATION=true
```

## 调试运行

```powershell
python -m uvicorn agent.main:app --host 0.0.0.0 --port 8020 --reload
```

测试：

```powershell
python -m pytest agent\tests -q
```
