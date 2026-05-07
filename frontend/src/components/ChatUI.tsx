import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api/chat";

type Role = "user" | "assistant";
type Message = { role: Role; content: string };

export function ChatUI() {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;

    setError(null);
    setInput("");
    setStreaming(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);

    try {
      for await (const chunk of streamChat(text, threadId)) {
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + chunk };
          return next;
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStreaming(false);
    }
  }

  function reset() {
    setMessages([]);
    setThreadId(crypto.randomUUID());
    setError(null);
  }

  return (
    <div className="chat">
      <div className="chat-toolbar">
        <button type="button" onClick={reset} disabled={streaming}>
          新規チャット
        </button>
        <span className="chat-thread">thread: {threadId.slice(0, 8)}</span>
      </div>

      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && (
          <div className="chat-empty">メッセージを入力して送信してください。</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-${m.role}`}>
            <div className="chat-role">{m.role === "user" ? "あなた" : "AI"}</div>
            <div className="chat-content">
              {m.content || (m.role === "assistant" && streaming && i === messages.length - 1
                ? "…"
                : "")}
            </div>
          </div>
        ))}
      </div>

      {error && <div className="chat-error">エラー: {error}</div>}

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="メッセージを入力 (Enter で送信 / Shift+Enter で改行)"
          rows={2}
          disabled={streaming}
        />
        <button type="submit" disabled={streaming || !input.trim()}>
          {streaming ? "生成中…" : "送信"}
        </button>
      </form>
    </div>
  );
}
