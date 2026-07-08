# 医疗 Agent 第一版

本目录实现第一版可控工作流 Agent，用于问题理解、RAGFlow 检索、基于证据回答、参考来源返回、可选指南核对和 SSE 流式输出。

## 模型接口

Agent 后续只考虑千问大模型，通过 OpenAI-compatible Chat Completions 接口调用。

必填配置：

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode
LLM_API_KEY=你的千问API_KEY
LLM_MODEL=qwen-plus
```

如果中转地址已经包含 `/v1/chat/completions`，也可以直接填写完整地址。

## 当前链路

1. `analyzers/query_analyzer.py`：识别问题类型并生成 `QueryPlan`。
2. `tools/retrieval/ragflow_client.py`：调用 RAGFlow `POST /api/v1/retrieval`。
3. `tools/retrieval/evidence_processor.py`：整理 evidence，去重，分配引用编号。
4. `services/answer_generator.py`：把问题、检索证据和引用编号交给千问生成回答。
5. `tools/validation/tool.py`：可选调用指南库做回答依据核对。
6. `orchestrator/response_builder.py`：组装最终 `ChatResponse`。

## 接口

普通完整响应接口：

```text
POST /api/agent/chat
```

SSE 流式响应接口：

```text
POST /api/agent/chat/stream
```

两者请求体一致：

```json
{
  "question": "多囊卵巢综合征有哪些文献证据？",
  "top_k": 3
}
```

## SSE 事件

`/api/agent/chat/stream` 返回 `text/event-stream`，事件格式如下：

```text
event: answer_delta
data: {"content":"..."}
```

当前事件顺序：

- `started`：开始处理问题。
- `query_plan`：问题理解完成。
- `retrieval_done`：RAGFlow 检索完成，返回 `references`。
- `answer_delta`：千问流式输出的回答片段。
- `answer_done`：回答正文输出完成。
- `validation_done`：依据核对完成。
- `done`：完整 `ChatResponse`。
- `error`：流式过程中出现错误。

## 主要返回字段

- `answer`：给用户展示的回答正文，包含 `[1]`、`[2]` 等引用编号。
- `references`：给前端展示的参考来源列表，包含 `file_uuid`、标题、片段、作者、期刊、年份等，不返回相似度分数。
- `evidence`：原始检索证据，主要用于调试和管理员排查。
- `validation`：回答依据状态，包含：
  - `grounded`：是否基于知识库检索结果。
  - `message`：依据说明。没有命中知识库时会说明回答基于普通医学知识。
  - `issues`：可选指南核对发现的需要谨慎表述的问题。

## RAGFlow 配置

```env
RAGFLOW_BASE_URL=http://172.16.150.45:8012
RAGFLOW_API_KEY=你的RAGFlow_API_KEY
RAGFLOW_LITERATURE_DATASET_ID=文献知识库ID
RAGFLOW_CASE_DATASET_ID=病案知识库ID
RAGFLOW_GUIDELINE_DATASET_ID=指南知识库ID
```

开启指南核对：

```env
AGENT_ENABLE_GUIDELINE_VALIDATION=true
```

## 调试运行

安装依赖：

```powershell
pip install -r agent\requirements.txt
```

启动独立 Agent 服务：

```powershell
python -m uvicorn agent.main:app --host 0.0.0.0 --port 8020 --reload
```

测试：

```powershell
python -m pytest agent\tests -q
```
