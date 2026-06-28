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
  };
});
