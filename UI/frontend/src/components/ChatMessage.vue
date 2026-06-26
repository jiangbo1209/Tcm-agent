<template>
  <div class="message" :class="message.role">
    <div class="message-avatar">
      <div v-if="message.role === 'user'" class="avatar user-avatar">U</div>
      <div v-else class="avatar ai-avatar">AI</div>
    </div>
    <div class="message-body">
      <div class="message-content">{{ message.content }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: Object, required: true },
});
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
</style>
