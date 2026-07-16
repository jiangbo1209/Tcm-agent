<template>
  <div class="message" :class="message.role">
    <div class="message-avatar">
      <div v-if="message.role === 'user'" class="avatar user-avatar">U</div>
      <div v-else class="avatar ai-avatar">AI</div>
    </div>
    <div class="message-body">
      <div v-if="isAssistant && showProcess" class="agent-process" :class="{ collapsed: processCollapsed }">
        <button class="process-header" type="button" @click="processCollapsed = !processCollapsed">
          <span class="process-title">检索过程</span>
          <span class="process-summary">{{ processSummary }}</span>
          <span class="process-caret" :class="{ open: !processCollapsed }">⌄</span>
        </button>
        <ol v-show="!processCollapsed" class="process-list">
          <li
            v-for="(step, index) in displayProcessSteps"
            :key="`${step.event}-${index}`"
            class="process-step"
            :class="step.status"
          >
            <span class="step-state" aria-hidden="true"></span>
            <span class="step-content">
              <span class="step-label">{{ step.label }}</span>
              <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
            </span>
          </li>
        </ol>
      </div>

      <div v-if="showAnswer" class="message-content">
        <template v-for="(part, index) in contentParts" :key="index">
          <button
            v-if="part.type === 'citation'"
            class="citation-marker"
            type="button"
            @click="focusReference(part.index)"
          >[{{ part.index }}]</button>
          <span v-else>{{ part.text }}</span>
        </template>
      </div>

      <div v-if="showReferences" class="reference-panel">
        <div class="reference-title">引用来源</div>
        <div class="reference-list">
          <button
            v-for="ref in references"
            :key="`${ref.index}-${ref.file_uuid || ref.document_id || ref.title}`"
            :ref="(el) => setReferenceRef(ref.index, el)"
            class="reference-item"
            :class="{ active: activeRef === ref.index, unresolved: !ref.file_uuid }"
            type="button"
            :disabled="loadingRef === ref.index"
            @click="openReference(ref)"
          >
            <span class="reference-index">[{{ ref.index }}]</span>
            <span class="reference-main">
              <span class="reference-name">{{ ref.title || "未命名来源" }}</span>
              <span class="reference-meta">{{ referenceMeta(ref) }}</span>
              <span v-if="ref.snippet" class="reference-snippet">{{ ref.snippet }}</span>
              <span v-if="referenceError(ref.index)" class="source-error">{{ referenceError(ref.index) }}</span>
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { getFileUrlByUuid } from "../api/graph";

const props = defineProps({
  message: { type: Object, required: true },
});

const loadingRef = ref(null);
const activeRef = ref(null);
const referenceEls = ref({});
const referenceErrors = ref({});
const processCollapsed = ref(false);

const isAssistant = computed(() => props.message.role === "assistant");
const isStreaming = computed(() => Boolean(props.message.streaming));
const references = computed(() => props.message.references || []);
const referenceIndexes = computed(() => new Set(references.value.map((item) => Number(item.index))));
const showAnswer = computed(() => !isAssistant.value || Boolean(props.message.content));
const showReferences = computed(() => isAssistant.value && !isStreaming.value && references.value.length);
const showProcess = computed(() => isAssistant.value && (isStreaming.value || processSteps.value.length));

const processSummary = computed(() => {
  if (isStreaming.value) {
    const running = displayProcessSteps.value.find((step) => step.status === "running");
    return running ? running.label : "正在处理";
  }
  if (!processSteps.value.length) {
    return "";
  }
  const failed = processSteps.value.find((step) => step.event === "error");
  return failed ? "处理失败" : "已完成";
});

const contentParts = computed(() => {
  const text = normalizeAnswerText(props.message.content || "");
  if (props.message.role !== "assistant" || !references.value.length) {
    return [{ type: "text", text }];
  }

  const parts = [];
  const pattern = /\[(\d+)\]|<(\d+)>|【(\d+)】|（(\d+)）/g;
  let cursor = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    const index = Number(match[1] || match[2] || match[3] || match[4]);
    if (!referenceIndexes.value.has(index)) {
      continue;
    }
    if (match.index > cursor) {
      parts.push({ type: "text", text: text.slice(cursor, match.index) });
    }
    parts.push({ type: "citation", index });
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    parts.push({ type: "text", text: text.slice(cursor) });
  }

  return parts.length ? parts : [{ type: "text", text }];
});

function normalizeAnswerText(text) {
  return String(text || "")
    .split("\n")
    .filter((line) => !line.includes("回答完毕") && !line.includes("retrieval_evidence") && !line.includes("evidence_status"))
    .join("\n")
    .replace(/\*\*\*|\*\*/g, "")
    .replace(/^\s*#{1,6}\s*/gm, "")
    .replace(/^\s*[-*_]{3,}\s*$/gm, "")
    .replace(/`([^`\n]+)`/g, "$1");
}

const processSteps = computed(() => {
  if (props.message.agent_steps?.length) {
    return props.message.agent_steps.map((step) => ({ ...step, status: step.event === "error" ? "error" : "done" }));
  }

  const steps = [];
  if (props.message.query_plan) {
    steps.push({
      event: "query_plan",
      label: "完成问题理解",
      detail: [
        taskTypeLabel(props.message.query_plan.task_type),
        answerModeLabel(props.message.query_plan.answer_mode),
        retrievalStrategyLabel(props.message.query_plan.retrieval_strategy),
        props.message.query_plan.rewritten_query,
      ].filter(Boolean).join(" · "),
    });
  }
  if (props.message.retrieval_total !== null && props.message.retrieval_total !== undefined) {
    const evidenceStatus = props.message.evidence_status || props.message.query_plan?.evidence_status;
    steps.push({
      event: "retrieval_done",
      label: evidenceStatusLabel(evidenceStatus),
      detail: retrievalDetail(evidenceStatus, props.message.retrieval_total, references.value.length),
    });
  }
  if (props.message.validation_result) {
    steps.push({
      event: "validation_done",
      label: "完成医学边界校验",
      detail: props.message.validation_result.message || "",
    });
  }
  return steps;
});

const displayProcessSteps = computed(() => {
  const steps = processSteps.value.map((step) => ({ ...step, status: step.status || "done" }));
  if (!isStreaming.value || steps.some((step) => step.event === "error" || step.event === "done")) {
    return steps;
  }

  const lastEvent = steps[steps.length - 1]?.event || "";
  const running = nextRunningStep(lastEvent);
  if (running && !steps.some((step) => step.event === running.event)) {
    steps.push(running);
  }
  return steps;
});

function nextRunningStep(lastEvent) {
  const runningMap = {
    "": { event: "started_pending", label: "正在建立响应", detail: "" },
    started: { event: "query_plan_pending", label: "正在理解问题", detail: "" },
    query_plan: { event: "retrieval_pending", label: "正在检索知识库", detail: "" },
    retrieval_done: { event: "answer_pending", label: "正在生成回答", detail: "" },
    answer_done: { event: "done_pending", label: "正在组装响应", detail: "" },
    validation_done: { event: "done_pending", label: "正在组装响应", detail: "" },
  };
  const step = runningMap[lastEvent];
  return step ? { ...step, status: "running" } : null;
}

function evidenceStatusLabel(status) {
  if (status === "source_only") return "完成引用来源定位";
  if (status === "no_direct_evidence" || status === "weak_evidence") return "未找到直接依据，启用通用回答";
  return "完成知识库检索";
}

function retrievalDetail(status, total, referenceCount) {
  if (status === "source_only") return "针对上一轮引用进行分析，未重新检索知识库";
  if (status === "no_direct_evidence") return "当前没有可直接支撑问题的本地知识库依据";
  if (status === "weak_evidence") return `检索到 ${total} 条相关主题资料，但不足以支撑当前结论`;
  return `命中 ${total} 条，采用 ${referenceCount} 条来源`;
}

function referenceMeta(ref) {
  const parts = [
    sourceTypeLabel(ref.source_type),
    ref.authors,
    ref.journal,
    ref.year,
    ref.file_uuid ? `UUID: ${ref.file_uuid}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function sourceTypeLabel(type) {
  const labels = {
    paper: "文献",
    literature: "文献",
    case: "病案",
    record: "病案",
    guideline: "指南",
  };
  return labels[type] || type || "资料";
}

function taskTypeLabel(type) {
  const labels = {
    source_detail: "来源详情",
    report_interpretation: "报告解读",
    assisted_reproduction_stages: "辅助生殖分阶段指导",
    safety_risk: "安全风险评估",
    option_comparison: "方案对比",
    case_analysis: "病例分析",
    case_review: "病案复盘",
    literature_evidence: "文献证据",
    patient_education: "患者宣教",
    follow_up: "连续追问",
    general_qa: "综合问答",
  };
  return labels[type] || type || "问题理解";
}

function answerModeLabel(mode) {
  const labels = {
    source_detail: "来源详情回答",
    report_interpretation: "报告解读格式",
    phase_guidance: "分阶段回答",
    safety_risk: "风险提示格式",
    option_comparison: "对比分析格式",
    case_analysis: "病例分析格式",
    case_review: "病案复盘格式",
    evidence_summary: "证据总结格式",
    patient_education: "通俗宣教格式",
    follow_up: "追问补充格式",
    general: "综合回答格式",
  };
  return labels[mode] || mode || "回答路由";
}

function retrievalStrategyLabel(strategy) {
  const labels = {
    single_query: "单问题检索",
    literature_first: "文献优先",
    case_first: "病案优先",
    literature_case_mix: "文献+病案",
    guideline_first: "指南优先",
    source_targeted: "来源定向",
    report_evidence: "报告证据",
    multi_query: "分阶段检索",
    hybrid: "综合检索",
  };
  return labels[strategy] || strategy || "检索策略";
}

async function openReference(ref) {
  activeRef.value = ref.index;
  clearReferenceError(ref.index);
  if (!ref.file_uuid) {
    setReferenceError(ref.index, "该引用暂未返回 file_uuid，无法用 UUID 查询原始文件。需要重新同步 RAGFlow 元数据后再试。");
    return;
  }

  loadingRef.value = ref.index;
  const targetWindow = window.open("about:blank", "_blank");
  if (targetWindow) {
    targetWindow.opener = null;
  }
  try {
    const { data } = await getFileUrlByUuid(ref.file_uuid, ref.source_type || "paper", "view");
    if (!data?.url) {
      throw new Error("后端未返回文件链接");
    }
    if (targetWindow) {
      targetWindow.location.href = data.url;
    } else {
      window.open(data.url, "_blank", "noopener,noreferrer");
    }
  } catch (error) {
    targetWindow?.close?.();
    const detail = error?.response?.data?.detail || error?.response?.data?.error || error?.message || "来源文件打开失败";
    setReferenceError(ref.index, detail);
  } finally {
    loadingRef.value = null;
  }
}

function setReferenceError(index, message) {
  referenceErrors.value = { ...referenceErrors.value, [index]: message };
}

function clearReferenceError(index) {
  const next = { ...referenceErrors.value };
  delete next[index];
  referenceErrors.value = next;
}

function referenceError(index) {
  return referenceErrors.value[index] || "";
}

function setReferenceRef(index, el) {
  if (el) {
    referenceEls.value[index] = el;
  }
}

function focusReference(index) {
  activeRef.value = index;
  const el = referenceEls.value[index];
  if (el?.scrollIntoView) {
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.user-avatar {
  background: linear-gradient(135deg, #5c6bc0, #3949ab);
}

.ai-avatar {
  background: linear-gradient(135deg, var(--teal), #4db6ac);
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message.user .message-body {
  text-align: right;
}

.message-content {
  display: inline-block;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.user .message-content {
  background: var(--teal);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: var(--panel);
  color: var(--ink-900);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.citation-marker {
  display: inline;
  border: none;
  background: transparent;
  color: var(--teal);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 0 1px;
  margin: 0 1px;
  vertical-align: super;
  cursor: pointer;
}

.citation-marker:hover {
  text-decoration: underline;
}

.agent-process,
.reference-panel {
  margin-top: 8px;
  max-width: 720px;
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: var(--radius);
  padding: 10px 12px;
}

.agent-process {
  margin-top: 0;
  margin-bottom: 8px;
  padding: 0;
  overflow: hidden;
}

.process-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}

.process-header:hover {
  background: var(--teal-soft);
}

.process-title,
.reference-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700);
}

.process-summary {
  min-width: 0;
  color: var(--ink-500);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.process-caret {
  color: var(--ink-500);
  font-size: 16px;
  line-height: 1;
  transform: rotate(-90deg);
  transition: transform 0.16s ease;
}

.process-caret.open {
  transform: rotate(0deg);
}

.reference-title {
  margin-bottom: 6px;
}

.process-list {
  margin: 0;
  padding: 0 12px 10px;
  list-style: none;
  color: var(--ink-500);
  font-size: 12px;
  line-height: 1.55;
}

.process-step {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 8px;
  padding: 4px 0;
}

.step-state {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 50%;
  border: 2px solid var(--border);
}

.process-step.done .step-state {
  border-color: var(--teal);
  background: var(--teal);
  box-shadow: inset 0 0 0 2px var(--panel);
}

.process-step.running .step-state {
  border-color: var(--teal-soft);
  border-top-color: var(--teal);
  animation: spin 0.8s linear infinite;
}

.process-step.error .step-state {
  border-color: #c62828;
  background: #c62828;
}

.step-content {
  min-width: 0;
  display: flex;
  gap: 6px;
  align-items: baseline;
  flex-wrap: wrap;
}

.step-label {
  color: var(--ink-700);
}

.step-detail {
  color: var(--ink-500);
  overflow-wrap: anywhere;
}

.reference-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reference-item {
  display: flex;
  gap: 8px;
  width: 100%;
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: var(--radius);
  padding: 8px;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.reference-item:hover:not(:disabled) {
  border-color: var(--teal);
}

.reference-item.active {
  border-color: var(--teal);
  box-shadow: 0 0 0 2px var(--teal-soft);
}

.reference-item:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.reference-item.unresolved {
  border-style: dashed;
}

.reference-index {
  flex-shrink: 0;
  color: var(--teal);
  font-weight: 600;
}

.reference-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reference-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
}

.reference-meta,
.reference-snippet,
.source-error {
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
}

.reference-snippet {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.source-error {
  margin-top: 6px;
  color: #c62828;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
