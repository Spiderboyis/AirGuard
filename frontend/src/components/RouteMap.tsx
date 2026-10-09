"use client";
import { LngLatBounds, Map, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Level, Route } from "@/lib/api";

if (typeof window !== "undefined") {
  setWorkerUrl("/maplibre-gl-worker.mjs");
}

const DARK_STYLE = "https://tiles.openfreemap.org/styles/dark";
const LIGHT_STYLE = "https://tiles.openfreemap.org/styles/liberty";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const colorExpr = (levels: Level[]): any => [
  "step",
  ["get", "pm25"],
  levels[0]?.color ?? "#10b981",
  ...levels.slice(0, -1).flatMap((level, i) => [(level.max as number) + 1e-6, levels[i + 1]?.color ?? "#f43f5e"]),
];

export default function RouteMap({
  routes,
  selected,
  levels,
  onSelect,
}: {
  routes: Route[];
  selected: string | null;
  levels: Level[];
  onSelect?: (routeId: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const fitted = useRef("");
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapTheme, setMapTheme] = useState<"dark" | "light">("dark");
  const [isStyleLoading, setIsStyleLoading] = useState(false);
  const [bearing, setBearing] = useState(0);

  const drawRef = useRef<() => void>(() => {});
  const mapThemeRef = useRef<"dark" | "light">("dark");
  mapThemeRef.current = mapTheme;

  const selectedRoute = routes.find((r) => r.id === selected) ?? routes[0];

  // Draw or redraw route polylines and indicators
  const draw = useCallback(() => {
    const current = map.current;
    if (!current || !current.getStyle() || levels.length === 0) return;

    // Remove previous AirGuard layers and sources
    const style = current.getStyle();
    (style?.layers ?? [])
      .filter((layer) => layer.id.startsWith("rt-"))
      .forEach((layer) => {
        if (current.getLayer(layer.id)) current.removeLayer(layer.id);
      });

    Object.keys(style?.sources ?? {})
      .filter((source) => source.startsWith("rt-"))
      .forEach((source) => {
        if (current.getSource(source)) current.removeSource(source);
      });

    if (routes.length === 0) return;

    const bounds = new LngLatBounds();
    const sortedRoutes = [...routes].sort((a, b) =>
      a.id === selected ? 1 : b.id === selected ? -1 : 0
    );

    const isLight = mapThemeRef.current === "light";

    for (const route of sortedRoutes) {
      const on = route.id === selected;
      route.geometry.forEach(([x, y]) => bounds.extend([x, y]));

      // Outer Casing Layer (glow and contrast outline)
      current.addSource(`rt-${route.id}-base`, {
        type: "geojson",
        data: {
          type: "Feature",
          properties: { routeId: route.id },
          geometry: { type: "LineString", coordinates: route.geometry },
        },
      });

      current.addLayer({
        id: `rt-${route.id}-base`,
        type: "line",
        source: `rt-${route.id}-base`,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": on ? (isLight ? "#18181b" : "#ffffff") : (isLight ? "#a1a1aa" : "#27272a"),
          "line-width": on ? 7 : 3.5,
          "line-opacity": on ? 0.95 : 0.35,
        },
      });

      // Heatmap Segmented PM2.5 Core Line
      const features = route.segments
        .filter((segment) => segment.line.length > 1)
        .map((segment) => ({
          type: "Feature" as const,
          properties: { pm25: segment.pm25, routeId: route.id },
          geometry: { type: "LineString" as const, coordinates: segment.line },
        }));

      current.addSource(`rt-${route.id}-seg`, {
        type: "geojson",
        data: { type: "FeatureCollection", features },
      });

      current.addLayer({
        id: `rt-${route.id}-seg`,
        type: "line",
        source: `rt-${route.id}-seg`,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": colorExpr(levels),
          "line-width": on ? 4.5 : 2,
          "line-opacity": on ? 1.0 : 0.45,
        },
      });

      // Interactive hover & click selection
      if (onSelect) {
        current.on("click", `rt-${route.id}-base`, () => onSelect(route.id));
        current.on("click", `rt-${route.id}-seg`, () => onSelect(route.id));
      }
    }

    // Add origin and destination endpoint markers for the selected route
    const activeRoute = routes.find((r) => r.id === selected) ?? routes[0];
    if (activeRoute && activeRoute.geometry.length > 1) {
      const origin = activeRoute.geometry[0];
      const destination = activeRoute.geometry[activeRoute.geometry.length - 1];

      current.addSource("rt-endpoints", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { type: "origin" },
              geometry: { type: "Point", coordinates: origin },
            },
            {
              type: "Feature",
              properties: { type: "destination" },
              geometry: { type: "Point", coordinates: destination },
            },
          ],
        },
      });

      current.addLayer({
        id: "rt-endpoints-pulse",
        type: "circle",
        source: "rt-endpoints",
        paint: {
          "circle-radius": 10,
          "circle-color": [
            "match",
            ["get", "type"],
            "origin",
            "#10b981",
            "destination",
            "#f43f5e",
            "#ffffff",
          ],
          "circle-opacity": 0.25,
        },
      });

      current.addLayer({
        id: "rt-endpoints-point",
        type: "circle",
        source: "rt-endpoints",
        paint: {
          "circle-radius": 5,
          "circle-color": [
            "match",
            ["get", "type"],
            "origin",
            "#10b981",
            "destination",
            "#f43f5e",
            "#ffffff",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": isLight ? "#18181b" : "#ffffff",
        },
      });
    }

    // Auto-fit new routes when route signature changes
    const signature = routes
      .map((route) => `${route.id}:${route.geometry[0]?.join(",")}:${route.geometry.length}`)
      .join("|");

    if (!bounds.isEmpty() && fitted.current !== signature) {
      current.fitBounds(bounds, { padding: 60, duration: 600 });
      fitted.current = signature;
    }
  }, [routes, selected, levels, onSelect]);

  useEffect(() => {
    drawRef.current = draw;
  }, [draw]);

  // Mount map once on load
  useEffect(() => {
    if (!box.current || map.current) return;
    const created = new Map({
      container: box.current,
      style: DARK_STYLE,
      center: [77.209, 28.614],
      zoom: 11,
      pitch: 0,
    });

    created.on("rotate", () => {
      setBearing(Math.round(created.getBearing()));
    });
    created.on("pitch", () => {
      setBearing(Math.round(created.getBearing()));
    });

    // Handle initial load and every theme / style switch
    created.on("style.load", () => {
      setIsStyleLoading(false);
      drawRef.current();
    });

    created.once("load", () => {
      setMapLoaded(true);
      drawRef.current();
    });

    map.current = created;

    return () => {
      created.remove();
      map.current = null;
      setMapLoaded(false);
    };
  }, []);

  // Redraw whenever routes, selected, levels, or map readiness changes
  useEffect(() => {
    const current = map.current;
    if (!current || !mapLoaded || levels.length === 0) return;
    draw();
  }, [draw, mapLoaded, levels.length]);

  // Map Control Actions with guaranteed event isolation
  const zoomIn = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current) return;
    map.current.zoomIn({ duration: 250 });
  };

  const zoomOut = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current) return;
    map.current.zoomOut({ duration: 250 });
  };

  const resetNorth = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current) return;
    map.current.resetNorthPitch({ duration: 350 });
    setBearing(0);
  };

  const fitActiveBounds = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current) return;
    if (routes.length > 0) {
      const bounds = new LngLatBounds();
      routes.forEach((r) => r.geometry.forEach(([x, y]) => bounds.extend([x, y])));
      if (!bounds.isEmpty()) {
        map.current.fitBounds(bounds, { padding: 60, duration: 600 });
        return;
      }
    }
    // Default Delhi NCR framing if no routes are loaded
    map.current.fitBounds(
      [
        [76.85, 28.40],
        [77.40, 28.88],
      ],
      { padding: 40, duration: 600 }
    );
  };

  const centerDelhi = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current) return;
    map.current.flyTo({
      center: [77.209, 28.614],
      zoom: 11,
      duration: 600,
      pitch: 0,
      bearing: 0,
    });
    setBearing(0);
  };

  const toggleTheme = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!map.current || isStyleLoading) return;
    const next = mapTheme === "dark" ? "light" : "dark";
    mapThemeRef.current = next;
    setMapTheme(next);
    setIsStyleLoading(true);
    const nextStyle = next === "dark" ? DARK_STYLE : LIGHT_STYLE;
    map.current.setStyle(nextStyle, { diff: false });
  };

  return (
    <div className="relative h-full w-full overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0c0d12]">
      <div ref={box} className="h-full min-h-[460px] w-full" />

      {/* Floating HUD: Top Left */}
      {selectedRoute && (
        <div className="absolute top-3 left-3 z-20 pointer-events-auto max-w-[calc(100%-280px)] rounded-lg border border-white/[0.08] bg-[#111318]/90 px-3 py-1.5 backdrop-blur-md text-xs font-mono truncate shadow-lg">
          <span className="text-zinc-400">Selected: </span>
          <span className="text-white font-medium">Route {selectedRoute.id.replace(/^r/i, "")}</span>
          <span className="text-zinc-500 mx-1.5">·</span>
          <span className="text-emerald-400 font-medium">{selectedRoute.duration_min} min</span>
          <span className="text-zinc-500 mx-1.5">·</span>
          <span className="text-zinc-300">{selectedRoute.distance_km} km</span>
        </div>
      )}

      {/* Modern Map Control Bar: Top Right */}
      <div
        className="absolute top-3 right-3 z-30 flex items-center gap-1.5 select-none pointer-events-auto"
        onMouseDown={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
        onTouchStart={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
      >
        {/* Reset North Compass Pill (visible when map is rotated) */}
        {bearing !== 0 && (
          <button
            type="button"
            onClick={resetNorth}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-[#111318]/90 px-2 py-1 text-xs text-emerald-400 hover:bg-emerald-500/10 active:scale-95 transition-all backdrop-blur-md cursor-pointer font-mono shadow-lg"
            title="Reset North orientation (0°)"
            aria-label="Reset North orientation"
          >
            <svg
              className="h-3.5 w-3.5 transition-transform"
              style={{ transform: `rotate(${-bearing}deg)` }}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 19 21 12 17 5 21 12 2" />
            </svg>
            <span>{bearing}°</span>
          </button>
        )}

        {/* Zoom Controls */}
        <div className="flex items-center rounded-lg border border-white/[0.08] bg-[#111318]/90 p-0.5 backdrop-blur-md shadow-lg">
          <button
            type="button"
            onClick={zoomIn}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex h-7 w-7 items-center justify-center rounded-md text-zinc-300 hover:bg-white/[0.08] hover:text-white active:scale-95 transition-all cursor-pointer"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <div className="h-3.5 w-px bg-white/[0.08]" />
          <button
            type="button"
            onClick={zoomOut}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex h-7 w-7 items-center justify-center rounded-md text-zinc-300 hover:bg-white/[0.08] hover:text-white active:scale-95 transition-all cursor-pointer"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-0.5 rounded-lg border border-white/[0.08] bg-[#111318]/90 p-0.5 backdrop-blur-md shadow-lg">
          <button
            type="button"
            onClick={fitActiveBounds}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs text-zinc-300 hover:bg-white/[0.08] hover:text-white active:scale-95 transition-all cursor-pointer font-medium"
            title={routes.length > 0 ? "Fit all routes in view" : "Fit Delhi NCR in view"}
          >
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 3 21 3 21 9" />
              <polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </svg>
            <span>Fit</span>
          </button>

          <button
            type="button"
            onClick={centerDelhi}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs text-zinc-300 hover:bg-white/[0.08] hover:text-white active:scale-95 transition-all cursor-pointer font-medium"
            title="Center on Delhi NCR"
          >
            <svg className="h-3 w-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
            </svg>
            <span>Delhi</span>
          </button>

          <button
            type="button"
            onClick={toggleTheme}
            onMouseDown={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            disabled={isStyleLoading}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs text-zinc-300 hover:bg-white/[0.08] hover:text-white active:scale-95 disabled:opacity-50 transition-all cursor-pointer font-medium"
            title={`Switch to ${mapTheme === "dark" ? "Light" : "Dark"} map style`}
          >
            {isStyleLoading ? (
              <svg className="h-3 w-3 animate-spin text-zinc-400" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : mapTheme === "dark" ? (
              <svg className="h-3 w-3 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            ) : (
              <svg className="h-3 w-3 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            )}
            <span>{mapTheme === "dark" ? "Dark" : "Light"}</span>
          </button>
        </div>
      </div>

      {/* AirGuard AQI Spectrum Legend: Bottom */}
      <div className="absolute bottom-3 inset-x-3 z-20 pointer-events-auto">
        <div className="rounded-xl border border-white/[0.08] bg-[#111318]/90 p-2.5 backdrop-blur-md shadow-xl">
          <div className="flex items-center justify-between mb-1.5 text-[10px] text-zinc-400">
            <span>Air Quality Segments (PM2.5 µg/m³)</span>
            <span className="text-zinc-500 font-mono">OpenAQ Live</span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 text-[10px]">
            {levels.map((level, idx) => (
              <div
                key={level.name}
                className="flex items-center gap-1.5 rounded-md bg-black/30 px-2 py-1 border border-white/[0.04]"
              >
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: level.color }}
                />
                <span className="truncate text-zinc-300 font-mono text-[9px]">
                  {level.max === null ? `> ${levels[idx - 1]?.max}` : `≤ ${level.max}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
