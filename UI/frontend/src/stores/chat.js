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

  async function fetchConversations() {
    const { data } = await getConversations();
    conversations.value = data.items || [];
  }

  async function newConversation(title) {
    const { data } = await createConversation(title);
    conversations.value.unshift(data);
    currentConversationId.value = data.id;
    messages.value = [];
    return data;
  }

  async function selectConversation(id) {
    currentConversationId.value = id;
    loading.value = true;
    try {
      const { data } = await getMessages(id);
      messages.value = data.items || [];
    } finally {
      loading.value = false;
    }
  }

  async function removeConversation(id) {
    await deleteConversation(id);
    conversations.value = conversations.value.filter((c) => c.id !== id);
    if (currentConversationId.value === id) {
      currentConversationId.value = null;
      messages.value = [];
    }
  }

  function addMessage(msg) {
    messages.value.push(msg);
  }

  function appendToLastAssistant(content) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === "assistant") {
      last.content += content;
    }
  }

  function addStepToLastAssistant(step) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === "assistant") {
      last.agent_steps = [...(last.agent_steps || []), step];
    }
  }

  function mergeLastAssistantMeta(meta) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === "assistant") {
      Object.assign(last, meta);
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

  function replaceLastAssistant(savedMessage) {
    const index = messages.value.length - 1;
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
    appendToLastAssistant,
    addStepToLastAssistant,
    mergeLastAssistantMeta,
    upsertConversation,
    replaceLastAssistant,
  };
});
