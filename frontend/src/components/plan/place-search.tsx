"use client";

import { useQuery } from "@tanstack/react-query";
import { LocateFixedIcon, MapPinIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Place } from "@/lib/profile";
import { cn } from "@/lib/utils";

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function PlaceSearch({
  label,
  value,
  onChange,
  placeholder,
  marker,
  allowLocate = false,
  autoFocus = false,
}: {
  label: string;
  value: Place | null;
  onChange: (p: Place | null) => void;
  placeholder?: string;
  marker: "origin" | "destination";
  allowLocate?: boolean;
  autoFocus?: boolean;
}) {
  const id = useId();
  const [text, setText] = useState(value?.name ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [locating, setLocating] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const q = useDebounced(text.trim(), 250);

  // Keep the text in sync when the selected place changes from outside (swap, quick trips).
  const [shownName, setShownName] = useState(value?.name);
  if (value?.name !== shownName) {
    setShownName(value?.name);
    setText(value?.name ?? "");
  }

  const { data = [], isFetching } = useQuery({
    queryKey: ["geocode", q],
    queryFn: () => api.geocode(q),
    enabled: open && q.length >= 2 && q !== value?.name,
    staleTime: 10 * 60_000,
  });

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const choose = (p: Place) => {
    onChange(p);
    setText(p.name);
    setOpen(false);
  };

  const locate = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        choose({ name: "My location", lat: pos.coords.latitude, lon: pos.coords.longitude, detail: "Current position" });
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  };

  const items = q.length >= 2 ? data : [];

  return (
    <div ref={wrap} className="relative">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div
        className={cn(
          "flex h-11 items-center gap-2.5 rounded-lg border bg-card px-3 transition-colors",
          "focus-within:border-foreground/40 focus-within:ring-3 focus-within:ring-ring/20",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "size-2.5 shrink-0 rounded-full",
            marker === "origin" ? "border-2 border-foreground bg-card" : "bg-foreground",
          )}
        />
        <span className="w-9 shrink-0 text-xs text-muted-foreground">{label}</span>
        <input
          id={id}
          value={text}
          autoFocus={autoFocus}
          autoComplete="off"
          placeholder={placeholder}
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            setActive(0);
            if (value) onChange(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, items.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && items[active]) {
              e.preventDefault();
              choose(items[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground/70"
        />
        {allowLocate && (
          <button
            type="button"
            onClick={locate}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Use my location"
            title="Use my location"
          >
            <LocateFixedIcon className={cn("size-4", locating && "animate-pulse")} />
          </button>
        )}
      </div>
      {open && q.length >= 2 && q !== value?.name && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute inset-x-0 top-[calc(100%+4px)] z-40 max-h-72 overflow-auto rounded-lg border bg-popover p-1 shadow-lg shadow-black/5"
        >
          {items.length === 0 && (
            <li className="px-3 py-2.5 text-sm text-muted-foreground">
              {isFetching ? "Searching…" : "No places found in Delhi NCR"}
            </li>
          )}
          {items.map((p, i) => (
            <li
              key={`${p.name}-${p.lat}-${p.lon}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(p);
              }}
              className={cn(
                "flex cursor-pointer items-start gap-2.5 rounded-md px-2.5 py-2 text-sm",
                i === active && "bg-muted",
              )}
            >
              <MapPinIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0">
                <span className="block truncate font-medium">{p.name}</span>
                <span className="block truncate text-xs text-muted-foreground">{p.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
