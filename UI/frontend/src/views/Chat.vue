<template>
  <div class="chat-page">
    <div class="chat-messages" ref="messagesRef">
      <div v-if="chatStore.messages.length === 0" class="chat-welcome">
        <div class="welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <h2>中医智能对话助手</h2>
        <p>输入您的问题，AI 将为您提供专业的中医文献与病案分析</p>
      </div>

      <ChatMessage
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />
    </div>

    <ChatInput :disabled="streaming" @send="handleSend" />
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from "vue";
import { useChatStore } from "../stores/chat";
import { sendMessageStream } from "../api/chat";
import ChatMessage from "../components/ChatMessage.vue";
import ChatInput from "../components/ChatInput.vue";

const chatStore = useChatStore();
const messagesRef = ref(null);
const streaming = ref(false);

watch(() => chatStore.messages.length, () => {
  nextTick(() => scrollToBottom());
});

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  }
}

async function handleSend(content) {
  if (!chatStore.currentConversationId) {
    await chatStore.newConversation();
  }

  const convId = chatStore.currentConversationId;

  chatStore.addMessage({
    id: Date.now(),
    conversation_id: convId,
    role: "user",
    content,
    created_at: new Date().toISOString(),
  });

  streaming.value = true;

  chatStore.addMessage({
    id: Date.now() + 1,
    conversation_id: convId,
    role: "assistant",
    content: "",
    streaming: true,
    agent_steps: [],
    created_at: new Date().toISOString(),
  });

  try {
    await sendMessageStream(
      convId,
      content,
      (chunk) => {
        if (!chunk) return;
        chatStore.appendToLastAssistant(chunk);
        nextTick(() => scrollToBottom());
      },
      (data) => {
        if (data.conversation) {
          chatStore.upsertConversation(data.conversation);
        }
        chatStore.replaceLastAssistant({ ...(data.message || data), streaming: false });
        streaming.value = false;
        nextTick(() => scrollToBottom());
      },
      (event, payload) => {
        handleAgentEvent(event, payload);
      }
    );
  } catch {
    streaming.value = false;
    chatStore.mergeLastAssistantMeta({ streaming: false });
    chatStore.appendToLastAssistant("\n\n[消息发送失败，请重试]");
  }
}

function handleAgentEvent(event, payload) {
  if (event === "conversation_updated") {
    chatStore.upsertConversation(payload);
    return;
  }

  const stepMap = {
    started: "开始处理问题",
    query_plan: "完成问题理解",
    retrieval_done: "完成知识库检索",
    answer_done: "完成回答生成",
    validation_done: "完成医学边界校验",
    done: "完成响应组装",
    error: "处理过程出现错误",
  };

  chatStore.addStepToLastAssistant({
    event,
    label: stepMap[event] || event,
    detail: buildStepDetail(event, payload),
    at: new Date().toISOString(),
  });

  if (event === "query_plan") {
    chatStore.mergeLastAssistantMeta({
      query_plan: payload,
      intent: payload.intent,
      retrieval_query: payload.rewritten_query,
    });
  } else if (event === "retrieval_done") {
    chatStore.mergeLastAssistantMeta({
      retrieval_used: true,
      retrieval_total: payload.total,
      evidence_status: payload.evidence_status,
      references: payload.references || [],
      warnings: payload.warnings || [],
    });
  } else if (event === "validation_done") {
    chatStore.mergeLastAssistantMeta({ validation_result: payload });
  } else if (event === "done") {
    chatStore.mergeLastAssistantMeta({
      query_plan: payload.query_plan,
      intent: payload.query_plan?.intent,
      retrieval_query: payload.query_plan?.rewritten_query,
      retrieval_used: Boolean(payload.references?.length),
      retrieval_total: payload.total,
      evidence_status: payload.evidence_status,
      references: payload.references || [],
      validation_result: payload.validation,
      warnings: payload.warnings || [],
    });
  }

  nextTick(() => scrollToBottom());
}

function buildStepDetail(event, payload) {
  if (event === "query_plan") {
    return [
      taskTypeLabel(payload.task_type),
      answerModeLabel(payload.answer_mode),
      retrievalStrategyLabel(payload.retrieval_strategy),
      payload.rewritten_query,
    ].filter(Boolean).join(" · ");
  }
  if (event === "retrieval_done") {
    const total = payload.total ?? 0;
    const refs = payload.references?.length ?? 0;
    if (payload.evidence_status === "source_only") {
      return "已定位上一轮引用，未重新检索知识库";
    }
    if (payload.evidence_status === "no_direct_evidence") {
      return "没有直接依据，将使用通用医学回答";
    }
    if (payload.evidence_status === "weak_evidence") {
      return `命中 ${total} 条相关主题资料，但不足以支撑当前问题`;
    }
    return `命中 ${total} 条，采用 ${refs} 条来源`;
  }
  if (event === "validation_done") {
    return payload.message || (payload.grounded ? "回答基于知识库检索结果" : "缺少直接依据");
  }
  if (event === "error") {
    return payload.message || "请稍后重试";
  }
  return "";
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
</script>

<style scoped>
.chat-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--ink-500);
}

.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--teal-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.chat-welcome h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}

.chat-welcome p {
  font-size: 14px;
  color: var(--ink-500);
}

</style>
