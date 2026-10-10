"use client";

import { ArrowUpIcon, CheckIcon, ChevronRightIcon, CircleAlertIcon, LoaderIcon, RotateCcwIcon, SquareIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { streamChat, type AgentEvent } from "@/lib/api";
import { useProfile } from "@/lib/profile";
import { cn } from "@/lib/utils";

interface ToolUI {
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
  ms?: number;
  ok?: boolean;
  pending: boolean;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
  tools?: ToolUI[];
  status?: "streaming" | "done" | "error";
  source?: "model" | "fallback" | "cache";
  rejected?: string[];
  reason?: string;
  model?: string | null;
  ms?: number;
}

const SUGGESTIONS_TRIP = ["Which route should I take?", "Why not just leave now?", "How sure is this forecast?"];
const SUGGESTIONS_FREE = [
  "What's the air like near India Gate right now?",
  "When should I cycle from Hauz Khas to Connaught Place?",
];

const TOOL_LABEL: Record<string, string> = {
  now_ist: "Checked the time",
  geocode: "Looked up a place",
  get_trip_result: "Read your trip analysis",
  get_forecast: "Got a PM2.5 forecast",
  score_routes: "Scored routes",
  best_departure_time: "Searched departure times",
};

/** Render **bold** and paragraphs; everything else stays plain text (no HTML injection). */
function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="[&+&]:mt-2">
          {para.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? (
              <strong key={j} className="font-semibold">{part.slice(2, -2)}</strong>
            ) : (
              <Fragment key={j}>{part}</Fragment>
            ),
          )}
        </p>
      ))}
    </>
  );
}

function ToolRow({ t }: { t: ToolUI }) {
  const [open, setOpen] = useState(false);
  const args = Object.entries(t.input)
    .map(([k, v]) => `${k}=${typeof v === "number" ? Number(v).toFixed(4).replace(/\.?0+$/, "") : JSON.stringify(v)}`)
    .join(", ");
  return (
    <li className="text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-muted"
        aria-expanded={open}
      >
        {t.pending ? (
          <LoaderIcon className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
        ) : t.ok ? (
          <CheckIcon className="size-3.5 shrink-0 text-good" />
        ) : (
          <CircleAlertIcon className="size-3.5 shrink-0 text-destructive" />
        )}
        <span className="text-muted-foreground">{TOOL_LABEL[t.name] ?? t.name}</span>
        <code className="min-w-0 flex-1 truncate font-mono text-[11px]">
          {t.name}({args})
        </code>
        {t.ms != null && <span className="font-mono text-[10px] text-muted-foreground tabular">{t.ms} ms</span>}
        <ChevronRightIcon className={cn("size-3 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
      </button>
      {open && t.output !== undefined && (
        <pre className="mt-1 mb-1.5 max-h-56 overflow-auto rounded-md border bg-paper p-2 font-mono text-[10.5px] leading-relaxed">
          {JSON.stringify(t.output, null, 2)}
        </pre>
      )}
    </li>
  );
}

export function Assistant({ tripId, className }: { tripId: string | null; className?: string }) {
  const profile = useProfile();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  // Bumped on every reset so a stream that is still arriving can't write into the new chat.
  const session = useRef(0);

  // Scroll only the message list (scrollIntoView would also scroll the panel and the page).
  useEffect(() => {
    const el = list.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const reset = () => {
    session.current += 1;
    abort.current?.abort();
    abort.current = null;
    setBusy(false);
    setMsgs([]);
    setText("");
    input.current?.focus();
  };

  // Stop any answer still streaming when the chat goes away (the planner remounts it per trip).
  useEffect(() => () => abort.current?.abort(), []);

  const patchFor = (sid: number) => (fn: (m: Msg) => Msg) =>
    setMsgs((all) => {
      if (sid !== session.current || !all.length) return all;
      const copy = [...all];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });

  async function send(message: string) {
    const q = message.trim();
    if (!q || busy) return;
    const history = msgs
      .filter((m) => m.status !== "error" && m.content)
      .map((m) => ({ role: m.role, content: m.content }))
      .slice(-6);
    const sid = session.current;
    const patchLast = patchFor(sid);
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", tools: [], status: "streaming" }]);
    setText("");
    setBusy(true);
    abort.current = new AbortController();
    try {
      await streamChat(
        {
          message: q,
          trip_id: tripId,
          history,
          profile: {
            name: profile.name || null,
            mode: profile.mode,
            sensitivity: profile.sensitivity,
            max_extra_min: profile.maxExtraMin,
            max_wait_min: profile.maxWaitMin,
          },
        },
        (e: AgentEvent) => {
          if (e.type === "tool_start") {
            patchLast((m) => ({ ...m, tools: [...(m.tools ?? []), { name: e.name, input: e.input, pending: true }] }));
          } else if (e.type === "tool_end") {
            patchLast((m) => {
              const tools = [...(m.tools ?? [])];
              const i = tools.findLastIndex((t) => t.name === e.name && t.pending);
              const done = { name: e.name, input: e.input, output: e.output, ms: e.ms, ok: e.ok, pending: false };
              if (i >= 0) tools[i] = done;
              else tools.push(done);
              return { ...m, tools };
            });
          } else if (e.type === "token") {
            patchLast((m) => ({ ...m, content: m.content + e.text }));
          } else if (e.type === "reset") {
            patchLast((m) => ({ ...m, content: "" }));
          } else if (e.type === "done") {
            patchLast((m) => ({
              ...m,
              content: e.answer,
              status: "done",
              source: e.source,
              rejected: e.ungrounded_numbers,
              reason: e.fallback_reason,
              model: e.model,
              ms: e.ms,
              tools: e.tool_calls.map((t) => ({ ...t, input: t.input as Record<string, unknown>, pending: false })),
            }));
          }
        },
        abort.current.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patchLast((m) => ({ ...m, status: "error", content: (err as Error).message }));
      } else {
        patchLast((m) => ({ ...m, status: "done" }));
      }
    } finally {
      if (sid === session.current) {
        setBusy(false);
        abort.current = null;
      }
    }
  }

  const suggestions = tripId ? SUGGESTIONS_TRIP : SUGGESTIONS_FREE;

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b pb-2.5">
        <p className="text-xs text-muted-foreground">
          {tripId ? "Answers use the trip you planned" : "No trip planned yet"}
        </p>
        <button
          type="button"
          onClick={reset}
          disabled={!msgs.length && !text}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <RotateCcwIcon className="size-3.5" /> New chat
        </button>
      </div>
      <div ref={list} className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-1 pt-4 pb-4">
        {msgs.length === 0 && (
          <div className="space-y-4 pt-2">
            <div>
              <p className="font-serif text-xl leading-snug">Ask about your trip.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The assistant runs on the Strands Agents SDK. It answers only with numbers returned by AirGuard&apos;s
                tools, and you can open every tool call below its answer.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border bg-card px-3 py-1.5 text-sm transition-colors hover:border-foreground/30"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <AnimatePresence initial={false}>
          {msgs.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn(m.role === "user" ? "flex justify-end" : "space-y-2")}
            >
              {m.role === "user" ? (
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-primary-foreground">
                  {m.content}
                </div>
              ) : (
                <>
                  {!!m.tools?.length && (
                    <div className="rounded-lg border bg-card/60 p-1.5">
                      <p className="px-1.5 pt-0.5 pb-1 text-[10px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
                        Tool calls
                      </p>
                      <ul>{m.tools.map((t, j) => <ToolRow key={j} t={t} />)}</ul>
                    </div>
                  )}
                  <div className={cn("text-[15px] leading-relaxed", m.status === "error" && "text-destructive")}>
                    {m.content ? (
                      <Rich text={m.content} />
                    ) : m.status === "streaming" ? (
                      <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                        <LoaderIcon className="size-3.5 animate-spin" /> Thinking…
                      </span>
                    ) : null}
                  </div>
                  {m.status === "done" && (
                    <p className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
                      {m.source === "model" ? (
                        <>
                          <CheckIcon className="size-3 text-good" /> Every number checked against tool results
                        </>
                      ) : (
                        <>
                          <CircleAlertIcon className="size-3" />
                          {m.rejected?.length
                            ? `Model draft used numbers no tool returned (${m.rejected.join(", ")}); showing the verified explanation`
                            : "Explained from the saved analysis without the language model"}
                        </>
                      )}
                      {m.model && <span className="font-mono">· {m.model}</span>}
                      {m.ms != null && <span className="font-mono tabular">· {(m.ms / 1000).toFixed(1)} s</span>}
                    </p>
                  )}
                </>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
        className="flex items-end gap-2 rounded-xl border bg-card p-1.5 focus-within:border-foreground/40"
      >
        <textarea
          ref={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(text);
            }
          }}
          rows={1}
          maxLength={600}
          placeholder={tripId ? "Ask about this trip…" : "Ask about air or a commute in Delhi…"}
          className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground/70"
          aria-label="Message"
        />
        {busy ? (
          <Button type="button" size="icon" variant="secondary" onClick={() => abort.current?.abort()} aria-label="Stop">
            <SquareIcon className="size-3.5" />
          </Button>
        ) : (
          <Button type="submit" size="icon" disabled={!text.trim()} aria-label="Send">
            <ArrowUpIcon />
          </Button>
        )}
      </form>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">General guidance only, not medical advice.</p>
    </div>
  );
}
