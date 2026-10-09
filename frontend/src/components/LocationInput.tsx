"use client";
import { useState, useEffect, useRef } from "react";
import { searchPlaces, type PlaceResult } from "@/lib/api";

export default function LocationInput({
  value,
  onChange,
  placeholder,
  ariaLabel,
  iconType = "pin",
  onSubmit,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
  iconType?: "origin" | "destination" | "pin";
  onSubmit?: () => void;
}) {
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleGps = () => {
    if (typeof window === "undefined" || !navigator.geolocation) return;
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
        onChange(coords);
        setLoading(false);
      },
      (err) => {
        console.warn("GPS error:", err);
        setLoading(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    onChange(val);

    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);

    if (val.trim().length >= 3) {
      setLoading(true);
      setIsOpen(true);
      typingTimeoutRef.current = setTimeout(async () => {
        try {
          const res = await searchPlaces(val);
          setResults(res.results);
        } catch (error) {
          console.error(error);
          setResults([]);
        } finally {
          setLoading(false);
        }
      }, 300);
    } else {
      setResults([]);
      setIsOpen(false);
    }
  };

  const handleSelect = (place: PlaceResult) => {
    onChange(place.name);
    setIsOpen(false);
  };

  const handleClear = () => {
    onChange("");
    setResults([]);
    setIsOpen(false);
  };

  const isMetro = (name: string, desc: string) => {
    const combined = `${name} ${desc}`.toLowerCase();
    return combined.includes("metro") || combined.includes("station") || combined.includes("line");
  };

  return (
    <div className="relative w-full" ref={containerRef}>
      <div className="group relative flex items-center rounded-xl border border-white/[0.08] bg-[#14161f] transition-all hover:border-white/[0.15] focus-within:border-zinc-400 focus-within:bg-[#181a24]">
        {/* Leading Indicator */}
        <div className="flex h-10 w-9 items-center justify-center pl-1 text-zinc-500">
          {iconType === "origin" ? (
            <span className="h-2 w-2 rounded-full border border-zinc-400 bg-zinc-200" />
          ) : iconType === "destination" ? (
            <span className="h-2 w-2 rounded-full border border-emerald-500/80 bg-emerald-400" />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          )}
        </div>

        {/* Input Field */}
        <input
          type="text"
          className="h-10 w-full bg-transparent pr-12 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none"
          placeholder={placeholder}
          aria-label={ariaLabel}
          value={value}
          onChange={handleInputChange}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              if (isOpen && results.length > 0) {
                handleSelect(results[0]);
              } else if (onSubmit) {
                onSubmit();
              }
            }
          }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
        />

        {/* Loading / GPS / Clear Button */}
        <div className="absolute right-2.5 flex items-center gap-1">
          {loading ? (
            <svg className="h-3.5 w-3.5 animate-spin text-zinc-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          ) : (
            <>
              {iconType === "origin" && !value && (
                <button
                  type="button"
                  onClick={handleGps}
                  className="flex items-center gap-1 rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                  title="Use current GPS location"
                >
                  <svg className="h-3 w-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <circle cx="12" cy="12" r="3" strokeWidth={2} />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                  </svg>
                  <span>GPS</span>
                </button>
              )}
              {value && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="flex h-5 w-5 items-center justify-center rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors"
                  title="Clear"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Dropdown Suggestions */}
      {isOpen && (
        <div className="absolute z-50 mt-1.5 w-full rounded-xl border border-white/[0.1] bg-[#161822] p-1 shadow-2xl backdrop-blur-xl">
          {results.length > 0 ? (
            <ul className="max-h-60 overflow-y-auto space-y-0.5">
              {results.map((place, idx) => {
                const metro = isMetro(place.name, place.display_name);
                return (
                  <li
                    key={idx}
                    onClick={() => handleSelect(place)}
                    className="flex flex-col justify-between rounded-lg px-3 py-2 cursor-pointer hover:bg-white/[0.04] transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-200 text-xs sm:text-sm">
                        {place.name}
                      </span>
                      {metro && (
                        <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono text-zinc-400 bg-white/[0.06] border border-white/[0.06]">
                          Metro
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-zinc-500 truncate mt-0.5">
                      {place.display_name}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            !loading && value.length >= 3 && (
              <div className="px-4 py-3 text-center text-xs text-zinc-500">
                No matching Delhi NCR locations found.
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
