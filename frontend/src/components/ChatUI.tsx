import { memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "../api/chat";
import type { ToolEvent } from "../types";
import { ToolEventView } from "./ToolEventView";

type Role = "user" | "assistant";

type Message = {
  id: string;
  role: Role;
  content: string;
  toolEvents?: ToolEvent[];
};

const SCROLL_FOLLOW_THRESHOLD_PX = 80;

export function ChatUI() {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useLayoutEffect(() => {
    if (!isAtBottom) return;
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, isAtBottom]);

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function handleScroll() {
    const el = listRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsAtBottom(distanceFromBottom < SCROLL_FOLLOW_THRESHOLD_PX);
  }

  function scrollToBottom() {
    const el = listRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setIsAtBottom(true);
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;

    const controller = new AbortController();
    abortRef.current = controller;

    setError(null);
    setInput("");
    setStreaming(true);
    setIsAtBottom(true);
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: crypto.randomUUID(), role: "assistant", content: "", toolEvents: [] },
    ]);

    try {
      for await (const item of streamChat(text, threadId, controller.signal)) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          const patch: Partial<Message> =
            item.kind === "text"
              ? { content: last.content + item.text }
              : { toolEvents: [...(last.toolEvents ?? []), item.event] };
          return [...prev.slice(0, -1), { ...last, ...patch }];
        });
      }
    } catch (err) {
      const aborted =
        controller.signal.aborted ||
        (err instanceof DOMException && err.name === "AbortError");
      if (!aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      abortRef.current = null;
      setStreaming(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  function reset() {
    setMessages([]);
    setThreadId(crypto.randomUUID());
    setError(null);
    setIsAtBottom(true);
  }

  return (
    <div className="chat">
      <div className="chat-toolbar">
        <button type="button" onClick={reset} disabled={streaming}>
          新規チャット
        </button>
        <span className="chat-thread">thread: {threadId.slice(0, 8)}</span>
      </div>

      <div className="chat-list" ref={listRef} onScroll={handleScroll}>
        {messages.length === 0 && (
          <div className="chat-empty">
            「白いTシャツを探して」など、ECサイトでの買い物を試してみてください。
          </div>
        )}
        {messages.map((m, i) => (
          <ChatMessage
            key={m.id}
            message={m}
            showPlaceholder={
              streaming &&
              i === messages.length - 1 &&
              m.role === "assistant" &&
              !m.content &&
              (m.toolEvents?.length ?? 0) === 0
            }
          />
        ))}
      </div>

      {!isAtBottom && messages.length > 0 && (
        <button
          type="button"
          className="scroll-to-bottom"
          onClick={scrollToBottom}
          aria-label="最新メッセージへスクロール"
        >
          ↓ 新着
        </button>
      )}

      {error && <div className="chat-error">エラー: {error}</div>}

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="メッセージを入力 (Enter で送信 / Shift+Enter で改行)"
        />
        <button
          type={streaming ? "button" : "submit"}
          onClick={streaming ? stop : undefined}
          disabled={!streaming && !input.trim()}
        >
          {streaming ? "停止" : "送信"}
        </button>
      </form>
    </div>
  );
}

const ChatMessage = memo(function ChatMessage({
  message,
  showPlaceholder,
}: {
  message: Message;
  showPlaceholder: boolean;
}) {
  const hasContent = !!message.content;
  const toolEvents = message.toolEvents ?? [];

  return (
    <div className={`chat-bubble chat-${message.role}`}>
      <div className="chat-role">{message.role === "user" ? "あなた" : "AI"}</div>
      {(hasContent || showPlaceholder) && (
        <div className="chat-content">
          <MessageBody
            role={message.role}
            content={message.content}
            showPlaceholder={showPlaceholder}
          />
        </div>
      )}
      {toolEvents.length > 0 && (
        <div className="chat-tool-events">
          {toolEvents.map((te, j) => (
            <div className="tool-event-block" key={j}>
              <div className="tool-event-name">[{te.name}]</div>
              <ToolEventView event={te} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

function MessageBody({
  role,
  content,
  showPlaceholder,
}: {
  role: Role;
  content: string;
  showPlaceholder: boolean;
}) {
  if (!content) {
    if (!showPlaceholder) return null;
    return (
      <span className="typing-indicator" aria-label="生成中" role="status">
        <span />
        <span />
        <span />
      </span>
    );
  }
  if (role === "assistant") {
    return (
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }
  return <>{content}</>;
}
