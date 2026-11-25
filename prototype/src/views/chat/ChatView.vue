<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-text">
        <h1>智能问答</h1>
        <p class="header-sub">基于 DOR 文献与病案的 AI 助手（原型演示）</p>
      </div>
      <button class="btn-sm" @click="clearChat">清空对话</button>
    </div>

    <div class="chat-layout">
      <section class="card chat-card">
        <div ref="scrollRef" class="msg-list">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="msg-row"
            :class="msg.role"
          >
            <div v-if="msg.role === 'assistant'" class="avatar">AI</div>
            <div class="bubble-wrap">
              <div class="bubble" :class="msg.role">
                <p class="bubble-text">{{ msg.text }}</p>
                <div v-if="msg.cites.length" class="cite-chips">
                  <span
                    v-for="cite in msg.cites"
                    :key="cite.id"
                    class="cite-chip"
                    :class="{ active: activeCite === cite.id }"
                    @click="activeCite = cite.id"
                  >
                    {{ cite.id }}
                  </span>
                </div>
              </div>
              <div class="meta">{{ roleLabel(msg.role) }} · {{ msg.time }}</div>
            </div>
          </div>

          <div v-if="sending" class="msg-row assistant">
            <div class="avatar">AI</div>
            <div class="bubble-wrap">
              <div class="bubble assistant typing">
                <span class="dot" />
                <span class="dot" />
                <span class="dot" />
              </div>
            </div>
          </div>
        </div>

        <div class="composer">
          <input
            ref="inputRef"
            v-model="draft"
            class="composer-input"
            type="text"
            :disabled="sending"
            placeholder="请输入问题，如：DOR 常见证型有哪些？"
            @keydown.enter.prevent="send"
          />
          <button
            class="btn-primary send-btn"
            :disabled="sending || !draft.trim()"
            @click="send"
          >
            {{ sending ? "回答中…" : "发送" }}
          </button>
        </div>
      </section>

      <aside class="card source-card">
        <div class="source-head">
          <h2>检索来源</h2>
          <span class="source-count">{{ lastCites.length }} 条</span>
        </div>
        <template v-if="lastCites.length">
          <div
            v-for="cite in lastCites"
            :key="cite.id"
            class="source-item"
            :class="{ active: activeCite === cite.id }"
            @click="activeCite = cite.id"
          >
            <div class="source-top">
              <span class="badge badge-teal">{{ cite.id }}</span>
              <span class="source-year">{{ cite.year }}</span>
            </div>
            <p class="source-title">{{ cite.title }}</p>
            <p class="source-author">{{ cite.author }}</p>
          </div>
          <p class="source-tip">点击卡片可高亮对应引用编号</p>
        </template>
        <div v-else class="source-empty">
          本次回答暂未引用文献，提问后将在此展示最近一次引用的 2 条文献。
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { LIT_RECORDS } from "../../data/dorMock";
import { chatStore, cloneMessages } from "../../stores/chat";

const LIT_BY_ID = new Map(LIT_RECORDS.map((record) => [record.id, record]));

function nowTime() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function welcomeMessage() {
  return {
    id: 0,
    role: "assistant",
    text:
      "您好，我是 DOR 知识库智能助手。您可以询问卵巢储备功能减退（DOR）相关的诊断指标、中医证型分布、方剂与针灸方案或病案结局，我会结合文献库与病案库为您解答。",
    cites: [],
    time: nowTime(),
  };
}

const messages = ref([]);
const draft = ref("");
const sending = ref(false);
const activeCite = ref("");
const scrollRef = ref(null);
const inputRef = ref(null);
let uid = 0;

const lastCites = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const msg = messages.value[i];
    if (msg.role === "assistant" && msg.cites.length) return msg.cites;
  }
  return [];
});

function roleLabel(role) {
  return role === "user" ? "我" : "AI 助手";
}

function toCite(record) {
  return {
    id: record.id,
    title: record.values.lit_1,
    author: record.values.lit_2 || "—",
    year: record.values.lit_3 || "—",
  };
}

function citesOf(ids) {
  return ids.map((id) => LIT_BY_ID.get(id)).filter(Boolean).map(toCite);
}

function buildReply(text) {
  if (/证型|辨证|肾虚|肝郁|痰湿|血瘀|阴虚|阳虚/.test(text)) {
    return {
      text:
        "文献库与病案库联合检索显示，DOR 不孕症的中医证型以肾虚证最为常见，其次为肝肾阴虚证、肝郁气滞证、痰湿证与肾虚血瘀证，临床亦多见肾虚肝郁、肾虚血瘀等复合证型。治法以补肾填精为基本，兼以疏肝、化痰、活血。可参考以下文献：",
      cites: citesOf(["LIT-004", "LIT-002"]),
    };
  }
  if (/方剂|中药|处方|汤|针灸|穴位|埋线|艾灸/.test(text)) {
    return {
      text:
        "针对肾虚证，补肾填精方（熟地黄、菟丝子、山茱萸、枸杞子、女贞子、当归、白芍等）联合常规西药是文献中出现频次最高的方案，疗程多为 3 个月经周期；痰湿证多用苍附导痰汤加减，肝肾阴虚证多用左归丸加减，并可配合针灸、穴位埋线增强疗效。相关依据见：",
      cites: citesOf(["LIT-001", "LIT-003"]),
    };
  }
  if (/AMH|卵巢|FSH|AFC|储备/i.test(text)) {
    return {
      text:
        "AMH、基础 FSH 与 AFC 是评估卵巢储备的核心指标。文献库中多采用 AMH<1.1 ng/mL、基础 FSH>10 IU/L、AFC<5~7 个作为 DOR 诊断阈值。中医药干预 3 个月经周期后，AMH 常见由 0.6~0.8 ng/mL 提升至 0.8~1.0 ng/mL，基础 FSH 下降约 3 IU/L，AFC 增加约 1~2 个。相关依据见：",
      cites: citesOf(["LIT-001", "LIT-005"]),
    };
  }
  return {
    text:
      "已收到您的问题。当前原型为演示模式，知识库覆盖 DOR 文献与病案各 6 条。建议从「中医证型」「方剂 / 针灸」「AMH / 卵巢功能」等角度提问，或前往「智能搜索」按关键词检索原始记录。",
    cites: [],
  };
}

function maxMessageId(list) {
  return list.reduce((max, m) => Math.max(max, Number(m.id) || 0), 0);
}

function persistCurrent() {
  if (chatStore.state.activeId) {
    chatStore.update(chatStore.state.activeId, messages.value);
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

function send() {
  const text = draft.value.trim();
  if (!text || sending.value) return;

  uid += 1;
  messages.value.push({
    id: uid,
    role: "user",
    text,
    cites: [],
    time: nowTime(),
  });
  draft.value = "";
  sending.value = true;
  persistCurrent();
  scrollToBottom();

  setTimeout(() => {
    const reply = buildReply(text);
    uid += 1;
    messages.value.push({
      id: uid,
      role: "assistant",
      text: reply.text,
      cites: reply.cites,
      time: nowTime(),
    });
    sending.value = false;
    activeCite.value = "";
    persistCurrent();
    scrollToBottom();
  }, 800);
}

function clearChat() {
  messages.value = [welcomeMessage()];
  draft.value = "";
  sending.value = false;
  activeCite.value = "";
  persistCurrent();
  nextTick(() => inputRef.value && inputRef.value.focus());
}
/* 初始化：与侧栏共享会话；无会话时创建欢迎会话 */
function loadActiveMessages() {
  const active = chatStore.active.value;
  if (active && (!active.messages || active.messages.length === 0)) {
    messages.value = [welcomeMessage()];
    chatStore.update(active.id, messages.value);
  } else {
    messages.value = active ? cloneMessages(active.messages) : [];
  }
  uid = messages.value.reduce((max, m) => Math.max(max, Number(m.id) || 0), 0);
}

if (!chatStore.conversations.length) {
  chatStore.create([welcomeMessage()]);
}
loadActiveMessages();

watch(
  () => chatStore.state.activeId,
  () => {
    loadActiveMessages();
    activeCite.value = "";
    nextTick(() => inputRef.value && inputRef.value.focus());
    scrollToBottom();
  },
);
</script>

<style scoped>
.header-text h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}

.chat-layout {
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.chat-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.msg-list {
  flex: 1;
  min-height: 320px;
  max-height: calc(100vh - 300px);
  overflow-y: auto;
  padding: 20px 22px 8px;
  background: linear-gradient(180deg, #fbfdfd 0%, #ffffff 60%);
}

.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
  align-items: flex-start;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: 0 0 32px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--teal);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.5px;
}

.bubble-wrap {
  max-width: 76%;
  display: flex;
  flex-direction: column;
}

.msg-row.user .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  padding: 11px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink-700);
}

.bubble.assistant {
  background: #fff;
  border: 1px solid var(--line);
  border-top-left-radius: 4px;
}

.bubble.user {
  background: var(--teal);
  color: #fff;
  border-top-right-radius: 4px;
}

.bubble-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.cite-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.cite-chip {
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-size: 11px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.cite-chip.active {
  background: var(--teal);
  color: #fff;
}

.meta {
  margin-top: 5px;
  font-size: 11px;
  color: var(--ink-400);
}

.bubble.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 14px 16px;
}

.bubble.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal-border);
  animation: blink 1.2s infinite ease-in-out;
}

.bubble.typing .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.bubble.typing .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

.composer {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid var(--line);
  background: #fafcfc;
}

.composer-input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  background: #fff;
}

.composer-input:focus {
  border-color: var(--teal);
}

.composer-input:disabled {
  background: #f5f7f7;
  color: var(--ink-400);
}

.send-btn {
  min-width: 84px;
  border-radius: 8px;
}

.send-btn:disabled {
  background: #cfd8d7;
  cursor: not-allowed;
}

.source-card {
  flex: 0 0 268px;
  width: 268px;
  padding: 16px;
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 9px;
}

.source-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-900);
}

.source-count {
  font-size: 11px;
  color: var(--ink-400);
}

.source-item {
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  background: #fff;
}

.source-item:hover {
  border-color: var(--teal-border);
}

.source-item.active {
  border-color: var(--teal);
  background: #f1faf8;
  box-shadow: 0 0 0 2px rgba(0, 121, 107, 0.12);
}

.source-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.source-year {
  font-size: 11px;
  color: var(--ink-400);
}

.source-title {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-700);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.source-author {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}

.source-tip {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--ink-400);
  line-height: 1.6;
}

.source-empty {
  padding: 18px 12px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-400);
  background: #fafafa;
  border: 1px dashed var(--line);
  border-radius: 8px;
  text-align: center;
}

@media (max-width: 900px) {
  .chat-layout {
    flex-direction: column;
  }

  .source-card {
    width: 100%;
    flex-basis: auto;
  }

  .msg-list {
    max-height: none;
  }
}
</style>
