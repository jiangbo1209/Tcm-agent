<template>
  <div class="chat-input-wrap">
    <form class="chat-input-form" @submit.prevent="handleSend">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="chat-textarea"
        placeholder="输入消息..."
        rows="1"
        @keydown.enter.exact.prevent="handleSend"
        @input="autoResize"
      ></textarea>
      <button type="submit" class="btn-send" :disabled="!text.trim() || disabled">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref, nextTick } from "vue";

const props = defineProps({
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["send"]);

const text = ref("");
const textareaRef = ref(null);

function autoResize() {
  const el = textareaRef.value;
  if (el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }
}

async function handleSend() {
  const content = text.value.trim();
  if (!content || props.disabled) return;
  text.value = "";
  emit("send", content);
  await nextTick();
  autoResize();
}
</script>

<style scoped>
.chat-input-wrap {
  padding: 16px 24px;
  background: var(--panel);
  border-top: 1px solid var(--border);
}

.chat-input-form {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 8px 8px 8px 16px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.chat-input-form:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px var(--teal-soft);
}

.chat-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-900);
  resize: none;
  max-height: 120px;
  padding: 4px 0;
}

.chat-textarea::placeholder {
  color: var(--ink-500);
}

.btn-send {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: var(--teal);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.16s ease;
  flex-shrink: 0;
}

.btn-send:hover:not(:disabled) {
  background: var(--teal-deep);
  transform: scale(1.05);
}

.btn-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
