import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";

interface ToolUse {
  name: string;
  args: Record<string, unknown>;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
  tools?: ToolUse[];
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const STARTER = [
  "Which of my stocks has the strongest buy signal right now?",
  "Why is NVDA flagged as a buy?",
  "Compare AMD and INTC",
  "What changed for TSLA this week?",
];

export function ChatPanel() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Hi — I'm Sentinel's local assistant. I can read the live signals, " +
        "ticker breakdowns, historical data, and news for your watchlist. " +
        "Ask me anything. Not financial advice — research only.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    const next: Msg[] = [...messages, { role: "user", content: trimmed }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError(null);

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setMessages([
        ...next,
        {
          role: "assistant",
          content: data.reply || "(empty reply)",
          tools: data.tools_used ?? [],
        },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setMessages([
        ...next,
        {
          role: "assistant",
          content:
            "I couldn't reach the chat backend. Make sure the backend is " +
            "running and Ollama is installed (https://ollama.com/download/windows). " +
            `Error: ${msg}`,
        },
      ]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const showStarters = messages.length <= 1 && !busy;

  return (
    <div className="panel chat-panel">
      <div className="panel-header">
        <span className="panel-title">Assistant</span>
        <span className="panel-meta">
          Local LLM · Ollama · grounds every answer in your live signals
        </span>
      </div>

      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role}`}>
            <div className="chat-avatar">
              {m.role === "user" ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className="chat-bubble-wrap">
              <div className="chat-bubble">{m.content}</div>
              {m.tools && m.tools.length > 0 && (
                <div className="chat-tools">
                  looked at:{" "}
                  {Array.from(new Set(m.tools.map((t) => t.name))).join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="chat-msg chat-msg-assistant">
            <div className="chat-avatar">
              <Bot size={14} />
            </div>
            <div className="chat-bubble-wrap">
              <div className="chat-bubble chat-bubble-thinking">
                <Loader2 size={14} className="chat-spin" /> thinking…
              </div>
            </div>
          </div>
        )}

        {showStarters && (
          <div className="chat-starters">
            {STARTER.map((s) => (
              <button
                key={s}
                className="chat-starter"
                onClick={() => send(s)}
                disabled={busy}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask about your signals… (Enter to send, Shift+Enter for newline)"
          rows={2}
          disabled={busy}
        />
        <button
          className="chat-send"
          onClick={() => send(input)}
          disabled={busy || !input.trim()}
          title="Send"
        >
          <Send size={16} />
        </button>
      </div>

      {error && <div className="chat-error">Last error: {error}</div>}
    </div>
  );
}
