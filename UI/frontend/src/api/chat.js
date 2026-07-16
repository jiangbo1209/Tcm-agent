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

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.done) {
            onDone?.(data);
          } else if (data.event && data.event !== "answer_delta") {
            onEvent?.(data.event, data.payload || {});
          } else {
            onChunk?.(data.content || "");
          }
        } catch {}
      }
    }
  }
}
