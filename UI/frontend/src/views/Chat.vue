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

      <div v-if="streaming" class="message assistant">
        <div class="message-avatar">
          <div class="avatar ai-avatar">AI</div>
        </div>
        <div class="message-body">
          <div class="message-content">{{ streamingContent }}<span class="cursor">|</span></div>
        </div>
      </div>
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
const streamingContent = ref("");

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
  streamingContent.value = "";

  chatStore.addMessage({
    id: Date.now() + 1,
    conversation_id: convId,
    role: "assistant",
    content: "",
    created_at: new Date().toISOString(),
  });

  try {
    await sendMessageStream(
      convId,
      content,
      (chunk) => {
        streamingContent.value += chunk;
        chatStore.appendToLastAssistant(chunk);
        nextTick(() => scrollToBottom());
      },
      () => {
        streaming.value = false;
      }
    );
  } catch {
    streaming.value = false;
    chatStore.appendToLastAssistant("\n\n[消息发送失败，请重试]");
  }
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

.message {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
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

.ai-avatar {
  background: linear-gradient(135deg, var(--teal), #4db6ac);
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message-content {
  display: inline-block;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--panel);
  color: var(--ink-900);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.cursor {
  animation: blink 0.8s infinite;
  color: var(--teal);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
