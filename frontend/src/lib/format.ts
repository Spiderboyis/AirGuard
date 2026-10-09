const IST = "Asia/Kolkata";

export function istTime(iso: string | Date) {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST });
}

export function istDateTime(iso: string | Date) {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: IST,
  });
}

/** Compact duration for tight spaces: "45 min", "1h 18m". */
export function dur(m: number) {
  const r = Math.round(m);
  if (r < 60) return `${r} min`;
  const h = Math.floor(r / 60);
  const mm = r % 60;
  return mm ? `${h}h ${mm}m` : `${h}h`;
}

export function minutes(m: number) {
  const r = Math.round(m);
  if (Math.abs(r) < 60) return `${r} min`;
  const h = Math.floor(Math.abs(r) / 60);
  const mm = Math.abs(r) % 60;
  return `${r < 0 ? "−" : ""}${h} h${mm ? ` ${mm} min` : ""}`;
}

export function signedPct(p: number) {
  const r = Math.round(p);
  if (r === 0) return "0%";
  return `${r < 0 ? "−" : "+"}${Math.abs(r)}%`;
}

export function signedMin(m: number) {
  const r = Math.round(m);
  if (r === 0) return "±0 min";
  return `${r < 0 ? "−" : "+"}${minutes(Math.abs(r))}`;
}

export function num(v: number, digits = 0) {
  return v.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function ago(iso: string) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
}
