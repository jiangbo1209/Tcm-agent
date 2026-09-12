import request from "./request";

export function getConversations() {
  return request.get("/chat/conversations");
}

export function createConversation(title = "新对话") {
  return request.post("/chat/conversations", { title });
}

export function getMessages(conversationId) {
  return request.get(`/chat/conversations/${conversationId}/messages`);
}

export function deleteConversation(conversationId) {
  return request.delete(`/chat/conversations/${conversationId}`);
}

export async function sendMessageStream(conversationId, content, onChunk, onDone, onEvent) {
  const token = localStorage.getItem("token");
  const response = await fetch(`/api/chat/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`消息发送失败：${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedDone = false;

  function processLine(line) {
    if (!line.startsWith("data:")) return;
    const raw = line.slice(5).trimStart();
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      if (data.done) {
        receivedDone = true;
        onDone?.(data);
      } else if (data.event && data.event !== "answer_delta") {
        onEvent?.(data.event, data.payload || {});
      } else {
        onChunk?.(data.content || "");
      }
    } catch (error) {
      console.warn("忽略无法解析的流式响应", error);
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    lines.forEach(processLine);
  }

  buffer += decoder.decode();
  if (buffer.trim()) processLine(buffer);
  return { done: receivedDone };
}
