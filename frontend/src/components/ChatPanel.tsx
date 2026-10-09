"use client";
import { useState, useRef, useEffect } from "react";
import { chat, type ToolCall } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string; calls?: ToolCall[]; cached?: boolean };

const SCRIPTED = [
  "Which route minimizes my PM2.5 inhalation, and should I wait to depart?",
  "Is the fastest route safe for someone with respiratory sensitivity?",
];

export default function ChatPanel({
  sens,
  mode,
  demo,
  tripId,
  fromPlace,
  toPlace,
  maxExtra,
  maxWait,
  offline = false,
  saved = [],
}: {
  sens: string;
  mode: string;
  demo: boolean;
  tripId: string | null;
  fromPlace?: string;
  toPlace?: string;
  maxExtra: number;
  maxWait: number;
  offline?: boolean;
  saved?: { question: string; answer: string; tool_calls: ToolCall[] }[];
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [msgs, busy]);

  async function send(preset?: string) {
    const q = (preset ?? text).trim();
    if (!q || busy) return;
    if (offline) {
      const hit = saved.find((item) => item.question.trim().toLowerCase() === q.toLowerCase());
      setText("");
      setMsgs([
        ...msgs,
        { role: "user", text: q },
        {
          role: "assistant",
          text: hit ? hit.answer : "Offline demo: only saved scripted questions can be answered.",
          calls: hit?.tool_calls,
          cached: true,
        },
      ]);
      return;
    }
    setText("");
    setBusy(true);
    const next: Msg[] = [...msgs, { role: "user", text: q }];
    setMsgs(next);
    try {
      const result = await chat({
        message: q,
        profile: { sensitivity: sens, mode, max_extra_min: maxExtra, max_wait_min: maxWait },
        demo,
        trip_id: tripId,
        from_place: fromPlace || undefined,
        to_place: toPlace || undefined,
        history: next.slice(-7, -1).map((message) => ({ role: message.role, text: message.text })),
      });
      setMsgs([
        ...next,
        { role: "assistant", text: result.answer, calls: result.tool_calls, cached: result.cached },
      ]);
    } catch (error) {
      setMsgs([...next, { role: "assistant", text: (error as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  const prompts = saved.length ? saved.map((item) => item.question) : SCRIPTED;

  return (
    <div className="surface-card p-4 mt-3">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-white/[0.06] text-zinc-300">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-zinc-200">
              AirGuard Assistant
            </h3>
          </div>
        </div>
        <span className="text-[11px] font-mono text-zinc-500">
          Powered by Strands
        </span>
      </div>

      {/* Message Stream */}
      {msgs.length > 0 && (
        <div
          ref={scrollRef}
          className="flex flex-col gap-2.5 max-h-72 overflow-y-auto pr-1 my-2"
        >
          {msgs.map((message, i) => (
            <div
              key={i}
              className={`max-w-[88%] rounded-xl p-3 text-xs leading-relaxed ${
                message.role === "user"
                  ? "self-end bg-zinc-800 text-zinc-100 rounded-br-sm"
                  : "self-start bg-[#161822] text-zinc-200 border border-white/[0.06] rounded-bl-sm"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.text}</p>

              {message.cached && (
                <p className="mt-1.5 text-[10px] text-amber-400">Offline cached answer.</p>
              )}

              {/* AWS Hackathon Tool Calls Inspector */}
              {!!message.calls?.length && (
                <div className="mt-2 pt-2 border-t border-white/[0.06]">
                  <details className="group">
                    <summary className="cursor-pointer font-mono text-[10px] text-zinc-400 hover:text-zinc-200 transition-colors select-none">
                      Tools invoked: {message.calls.map((c) => c.name).join(", ")}
                    </summary>
                    <div className="mt-2 space-y-1.5">
                      {message.calls.map((call, j) => (
                        <div
                          key={j}
                          className="rounded-lg bg-[#0c0d12] p-2 border border-white/[0.04] font-mono text-[10px] text-zinc-300 overflow-x-auto"
                        >
                          <div className="text-emerald-400 font-semibold mb-0.5">
                            {call.name}()
                          </div>
                          <div className="text-zinc-500">
                            Input: {JSON.stringify(call.input)}
                          </div>
                          {call.output && (
                            <div className="text-zinc-400 mt-1 pt-1 border-t border-white/[0.04]">
                              Output: {call.output}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              )}
            </div>
          ))}

          {busy && (
            <div className="self-start max-w-[85%] rounded-xl rounded-bl-sm bg-[#161822] border border-white/[0.06] p-3">
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 bg-zinc-400 rounded-full animate-bounce" />
                <span className="h-1.5 w-1.5 bg-zinc-400 rounded-full animate-bounce [animation-delay:0.15s]" />
                <span className="h-1.5 w-1.5 bg-zinc-400 rounded-full animate-bounce [animation-delay:0.3s]" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Suggested Quick Prompts */}
      {msgs.length === 0 && (
        <div className="my-2 space-y-1.5">
          <div className="text-[11px] text-zinc-500">Suggested questions:</div>
          <div className="flex flex-col gap-1.5">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                className="text-left rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-xs text-zinc-300 hover:bg-white/[0.05] hover:text-white transition-colors"
                onClick={() => send(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Box */}
      <div className="flex gap-2 mt-2 pt-2 border-t border-white/[0.06]">
        <input
          className="flex-1 rounded-xl border border-white/[0.08] bg-[#14161f] px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-zinc-400 focus:outline-none transition-colors"
          value={text}
          maxLength={500}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && send()}
          placeholder="Ask about route safety, asthma risks, etc..."
          aria-label="Message the assistant"
        />
        <button
          className="rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 px-3.5 py-2 text-xs font-semibold disabled:opacity-40 transition-colors"
          disabled={busy}
          onClick={() => send()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
