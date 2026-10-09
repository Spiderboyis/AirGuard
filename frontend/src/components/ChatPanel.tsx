"use client";
import { useState } from "react";
import { chat, type ToolCall } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string; calls?: ToolCall[]; cached?: boolean };

const SCRIPTED = ["I cycle from Hauz Khas to DU North Campus. Which route should I take, and when should I leave?"];

export default function ChatPanel({
  sens, mode, demo, tripId, maxExtra, maxWait, offline = false, saved = [],
}: {
  sens: string;
  mode: string;
  demo: boolean;
  tripId: string | null;
  maxExtra: number;
  maxWait: number;
  offline?: boolean;
  saved?: { question: string; answer: string; tool_calls: ToolCall[] }[];
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(preset?: string) {
    const q = (preset ?? text).trim();
    if (!q || busy) return;
    if (offline) {
      const hit = saved.find((item) => item.question.trim().toLowerCase() === q.toLowerCase());
      setText("");
      setMsgs([...msgs, { role: "user", text: q }, {
        role: "assistant",
        text: hit ? hit.answer : "Offline demo: only the saved scripted questions can be answered.",
        calls: hit?.tool_calls,
        cached: true,
      }]);
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
        history: next.slice(-7, -1).map((message) => ({ role: message.role, text: message.text })),
      });
      setMsgs([...next, { role: "assistant", text: result.answer, calls: result.tool_calls, cached: result.cached }]);
    } catch (error) {
      setMsgs([...next, { role: "assistant", text: (error as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  const prompts = saved.length ? saved.map((item) => item.question) : SCRIPTED;
  return (
    <div className="flex flex-col gap-2">
      {msgs.map((message, i) => (
        <div key={i} className={message.role === "user" ? "self-end max-w-full rounded-lg bg-blue-50 p-2 text-sm" : "rounded-lg bg-slate-50 p-2 text-sm"}>
          <p className="whitespace-pre-wrap">{message.text}</p>
          {message.cached && <p className="mt-1 text-xs text-amber-700">Saved answer shown because the assistant was unavailable or this is the offline demo.</p>}
          {!!message.calls?.length && (
            <details className="mt-1 text-xs text-slate-600">
              <summary>Tools used: {message.calls.map((call) => call.name).join(", ")}</summary>
              {message.calls.map((call, j) => (
                <pre key={j} className="mt-1 overflow-x-auto rounded bg-white p-2">{call.name}({JSON.stringify(call.input)}){"\n→ "}{call.output}</pre>
              ))}
            </details>
          )}
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button key={prompt} className="rounded border border-slate-300 bg-white px-2 py-1 text-left text-xs" onClick={() => send(prompt)}>{prompt}</button>
        ))}
      </div>
      {busy && <p className="text-sm text-slate-500">Thinking…</p>}
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 bg-white p-2 text-sm"
          value={text}
          maxLength={500}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && send()}
          placeholder="Ask: which route and time should I choose?"
          aria-label="Message the assistant"
        />
        <button className="rounded bg-blue-600 px-3 text-sm text-white disabled:opacity-50" disabled={busy} onClick={() => send()}>Send</button>
      </div>
    </div>
  );
}
