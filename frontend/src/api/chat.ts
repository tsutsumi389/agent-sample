import type { StreamEvent, ToolEvent } from "../types";

export type ChatStreamItem =
  | { kind: "text"; text: string }
  | { kind: "tool"; event: ToolEvent };

export async function* streamChat(
  message: string,
  threadId: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamItem> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      buf += decoder.decode(value, { stream: true });

      const events = buf.split("\n\n");
      buf = events.pop() ?? "";

      for (const raw of events) {
        const line = raw.trim();
        if (!line.startsWith("data:")) continue;
        let payload: StreamEvent;
        try {
          payload = JSON.parse(line.slice(5).trim()) as StreamEvent;
        } catch {
          continue;
        }

        if (payload.type === "error") throw new Error(payload.error);
        if (payload.type === "done") return;
        if (payload.type === "content") {
          yield { kind: "text", text: payload.content };
          continue;
        }
        if (payload.type === "tool") {
          yield { kind: "tool", event: payload.result };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
