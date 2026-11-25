import { reactive, computed } from "vue";

const STORAGE_KEY = "tcm-dor-chat-history-v1";

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function persist(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    /* ignore */
  }
}

export function stamp() {
  return new Date().toISOString().slice(0, 16).replace("T", " ");
}

function newId() {
  return `conv-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

export function titleOf(messages) {
  const firstUser = (messages || []).find((m) => m.role === "user");
  if (!firstUser) return "新对话";
  const text = String(firstUser.text || "").replace(/\s+/g, " ").trim();
  return text.length > 22 ? `${text.slice(0, 22)}…` : text || "新对话";
}

export function cloneMessages(list) {
  return (list || []).map((m) => ({ ...m, cites: (m.cites || []).map((c) => ({ ...c })) }));
}

const initial = load();

const state = reactive({
  conversations: initial,
  activeId: initial.length
    ? [...initial].sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)))[0].id
    : "",
});

function sortDesc() {
  state.conversations.sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
}

export const chatStore = {
  state,

  get conversations() {
    return state.conversations;
  },

  active: computed(() => state.conversations.find((c) => c.id === state.activeId) || null),

  create(messages = []) {
    const conv = {
      id: newId(),
      title: titleOf(messages),
      createdAt: stamp(),
      updatedAt: stamp(),
      messages: cloneMessages(messages),
    };
    state.conversations.unshift(conv);
    state.activeId = conv.id;
    persist(state.conversations);
    return conv;
  },

  update(id, messages) {
    const conv = state.conversations.find((c) => c.id === id);
    if (!conv) return;
    conv.messages = cloneMessages(messages);
    conv.title = titleOf(messages);
    conv.updatedAt = stamp();
    sortDesc();
    persist(state.conversations);
  },

  select(id) {
    if (state.conversations.some((c) => c.id === id)) state.activeId = id;
  },

  remove(id) {
    state.conversations = state.conversations.filter((c) => c.id !== id);
    if (state.activeId === id) {
      state.activeId = state.conversations[0]?.id || "";
    }
    persist(state.conversations);
  },

  group() {
    const today = [];
    const yesterday = [];
    const earlier = [];
    const now = new Date();
    const dayKey = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    const todayKey = dayKey(now);
    const yest = new Date(now);
    yest.setDate(now.getDate() - 1);
    const yestKey = dayKey(yest);
    for (const conv of state.conversations) {
      const d = new Date(String(conv.updatedAt || "").replace(" ", "T"));
      const key = Number.isNaN(d.getTime()) ? "" : dayKey(d);
      if (key === todayKey) today.push(conv);
      else if (key === yestKey) yesterday.push(conv);
      else earlier.push(conv);
    }
    return { today, yesterday, earlier };
  },
};
