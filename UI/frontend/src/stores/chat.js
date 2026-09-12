import { defineStore } from "pinia";
import { ref } from "vue";
import {
  getConversations,
  createConversation,
  getMessages,
  deleteConversation,
} from "../api/chat";

export const useChatStore = defineStore("chat", () => {
  const conversations = ref([]);
  const currentConversationId = ref(null);
  const messages = ref([]);
  const loading = ref(false);
  let conversationRequestId = 0;

  async function fetchConversations() {
    const { data } = await getConversations();
    conversations.value = data.items || [];
  }

  async function newConversation(title) {
    const requestId = ++conversationRequestId;
    loading.value = false;
    const { data } = await createConversation(title);
    conversations.value.unshift(data);
    if (requestId === conversationRequestId) {
      currentConversationId.value = data.id;
      messages.value = [];
    }
    return data;
  }

  async function selectConversation(id) {
    const requestId = ++conversationRequestId;
    const previousConversationId = currentConversationId.value;
    const previousMessages = messages.value;
    currentConversationId.value = id;
    loading.value = true;
    try {
      const { data } = await getMessages(id);
      if (requestId !== conversationRequestId || currentConversationId.value !== id) return;
      messages.value = data.items || [];
    } catch (error) {
      if (requestId === conversationRequestId && currentConversationId.value === id) {
        currentConversationId.value = previousConversationId;
        messages.value = previousMessages;
      }
      throw error;
    } finally {
      if (requestId === conversationRequestId) loading.value = false;
    }
  }

  async function removeConversation(id) {
    await deleteConversation(id);
    conversations.value = conversations.value.filter((c) => c.id !== id);
    if (currentConversationId.value === id) {
      conversationRequestId += 1;
      currentConversationId.value = null;
      messages.value = [];
      loading.value = false;
    }
  }

  function addMessage(msg) {
    messages.value.push(msg);
  }

  function findAssistant(messageId) {
    return messages.value.find((message) => message.id === messageId && message.role === "assistant");
  }

  function appendToAssistant(messageId, content) {
    const message = findAssistant(messageId);
    if (message) {
      message.content += content;
    }
  }

  function addStepToAssistant(messageId, step) {
    const message = findAssistant(messageId);
    if (message) {
      message.agent_steps = [...(message.agent_steps || []), step];
    }
  }

  function mergeAssistantMeta(messageId, meta) {
    const message = findAssistant(messageId);
    if (message) {
      Object.assign(message, meta);
    }
  }

  function upsertConversation(conversation) {
    if (!conversation?.id) return;
    const index = conversations.value.findIndex((item) => item.id === conversation.id);
    if (index >= 0) {
      const updated = {
        ...conversations.value[index],
        ...conversation,
      };
      conversations.value = [
        updated,
        ...conversations.value.filter((item) => item.id !== conversation.id),
      ];
      return;
    }
    conversations.value.unshift(conversation);
  }

  function replaceAssistant(messageId, savedMessage) {
    const index = messages.value.findIndex((message) => message.id === messageId);
    const current = messages.value[index];
    if (index >= 0 && current?.role === "assistant" && savedMessage) {
      messages.value[index] = {
        ...savedMessage,
        agent_steps: current.agent_steps || savedMessage.agent_steps,
      };
    }
  }

  return {
    conversations,
    currentConversationId,
    messages,
    loading,
    fetchConversations,
    newConversation,
    selectConversation,
    removeConversation,
    addMessage,
    appendToAssistant,
    addStepToAssistant,
    mergeAssistantMeta,
    upsertConversation,
    replaceAssistant,
  };
});
