"use client";

import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import { useTheme } from "next-themes";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { StationSummary } from "@/lib/api";
import { bandStepExpression } from "@/lib/aq";
import { cn } from "@/lib/utils";

export interface MapRoute {
  id: string;
  selected: boolean;
  recommended: boolean;
  segments: { pm25: number; line: number[][] }[];
}

interface Props {
  stations?: StationSummary[];
  routes?: MapRoute[];
  origin?: { lat: number; lon: number } | null;
  destination?: { lat: number; lon: number } | null;
  onRouteClick?: (id: string) => void;
  interactive?: boolean;
  className?: string;
  fitPadding?: { top: number; bottom: number; left: number; right: number };
}

const STYLE = {
  light: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron",
  dark: process.env.NEXT_PUBLIC_MAP_STYLE_URL_DARK ?? "https://tiles.openfreemap.org/styles/dark",
};
const DELHI: [number, number] = [77.16, 28.62];

function stationFC(stations: StationSummary[] = []) {
  return {
    type: "FeatureCollection" as const,
    features: stations.map((s) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
      properties: { id: s.id, name: s.name, pm25: s.pm25_now, measured: s.measured ? 1 : 0, provider: s.provider ?? "" },
    })),
  };
}

function routeFC(routes: MapRoute[] = []) {
  // Unselected routes first so the selected one draws on top.
  const ordered = [...routes].sort((a, b) => Number(a.selected) - Number(b.selected));
  return {
    type: "FeatureCollection" as const,
    features: ordered.flatMap((r) =>
      r.segments.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: s.line },
        properties: { route: r.id, pm25: s.pm25, selected: r.selected ? 1 : 0 },
      })),
    ),
  };
}

function endpointFC(o?: Props["origin"], d?: Props["destination"]) {
  const f = [];
  if (o) f.push({ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [o.lon, o.lat] }, properties: { kind: "origin" } });
  if (d) f.push({ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [d.lon, d.lat] }, properties: { kind: "destination" } });
  return { type: "FeatureCollection" as const, features: f };
}

interface LayerProps {
  stations?: StationSummary[];
  routes?: MapRoute[];
  origin?: Props["origin"];
  destination?: Props["destination"];
  dark: boolean;
  onRouteClick?: (id: string) => void;
}

export function AirMap({ stations, routes, origin, destination, onRouteClick, interactive = true, className, fitPadding }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(0);
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const props = useRef<LayerProps>({ stations, routes, origin, destination, dark, onRouteClick });
  useLayoutEffect(() => {
    props.current = { stations, routes, origin, destination, dark, onRouteClick };
  });

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let instance: MlMap | null = null;
    (async () => {
      const maplibregl = await import("maplibre-gl");
      if (cancelled || !el.current) return;
      maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
      instance = new maplibregl.Map({
        container: el.current,
        style: props.current.dark ? STYLE.dark : STYLE.light,
        center: DELHI,
        zoom: 10.2,
        attributionControl: { compact: true },
        interactive,
        dragRotate: false,
        pitchWithRotate: false,
      });
      if (interactive) instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
      instance.touchZoomRotate?.disableRotation();

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
      instance.on("style.load", () => {
        addLayers(instance!, props.current);
        setReady((n) => n + 1);
      });
      instance.on("mousemove", "stations", (e) => {
        const f = (e.features?.[0] ?? null) as unknown as { properties: Record<string, string | number>; geometry: { coordinates: [number, number] } } | null;
        if (!f) return;
        instance!.getCanvas().style.cursor = "pointer";
        const p = f.properties;
        popup
          .setLngLat(f.geometry.coordinates)
          .setHTML(
            `<div style="font-size:12px;line-height:1.35"><div style="font-weight:600;margin-bottom:2px">${String(p.name)
              .replace(/</g, "&lt;")}</div><div><b style="font-size:15px">${Math.round(Number(p.pm25))}</b> µg/m³ · ${
              Number(p.measured) ? "measured" : "estimated (feed delayed)"
            }</div><div style="opacity:.6">${String(p.provider || "")}</div></div>`,
          )
          .addTo(instance!);
      });
      instance.on("mouseleave", "stations", () => {
        instance!.getCanvas().style.cursor = "";
        popup.remove();
      });
      instance.on("click", "routes-hit", (e) => {
        const id = e.features?.[0]?.properties?.route as string | undefined;
        if (id) props.current.onRouteClick?.(id);
      });
      instance.on("mouseenter", "routes-hit", () => (instance!.getCanvas().style.cursor = "pointer"));
      instance.on("mouseleave", "routes-hit", () => (instance!.getCanvas().style.cursor = ""));
      map.current = instance;
      if (process.env.NODE_ENV === "development") (window as unknown as { __airmap?: MlMap }).__airmap = instance;
    })();
    return () => {
      cancelled = true;
      instance?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Theme switch: swap the basemap; layers are re-added on style.load.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    m.setStyle(dark ? STYLE.dark : STYLE.light);
  }, [dark]);

  // Data updates.
  useEffect(() => {
    const m = map.current;
    if (!m || !m.getSource("stations")) return;
    (m.getSource("stations") as GeoJSONSource).setData(stationFC(stations));
    (m.getSource("routes") as GeoJSONSource).setData(routeFC(routes));
    (m.getSource("endpoints") as GeoJSONSource).setData(endpointFC(origin, destination));
    for (const id of ["routes-line", "stations"]) {
      if (m.getLayer(id)) {
        m.setPaintProperty(id, id === "routes-line" ? "line-color" : "circle-color", bandStepExpression("pm25", dark) as never);
      }
    }
  }, [stations, routes, origin, destination, ready, dark]);

  // Fit to the trip when a new one arrives.
  const routeKey = routes?.map((r) => r.id + r.segments.length).join("|") ?? "";
  useEffect(() => {
    const m = map.current;
    if (!m || !routes?.length) return;
    const pts = routes.flatMap((r) => r.segments.flatMap((s) => s.line));
    if (!pts.length) return;
    let [w, s, e, n] = [180, 90, -180, -90];
    for (const [x, y] of pts) {
      w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y);
    }
    m.fitBounds([[w, s], [e, n]], { padding: fitPadding ?? { top: 60, bottom: 60, left: 60, right: 60 }, duration: 900 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeKey, ready > 0]);

  return <div ref={el} className={cn("h-full w-full", className)} aria-label="Map of Delhi air quality and routes" />;
}

function addLayers(m: MlMap, p: LayerProps) {
  const { stations, routes, origin, destination, dark } = p;
  const ink = dark ? "#ebe8e0" : "#16161a";
  const paper = dark ? "#141412" : "#f8f6f1";
  m.addSource("stations", { type: "geojson", data: stationFC(stations) });
  m.addSource("routes", { type: "geojson", data: routeFC(routes) });
  m.addSource("endpoints", { type: "geojson", data: endpointFC(origin, destination) });

  m.addLayer({
    id: "routes-casing",
    type: "line",
    source: "routes",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ink,
      "line-width": ["case", ["==", ["get", "selected"], 1], 9, 5],
      "line-opacity": ["case", ["==", ["get", "selected"], 1], 0.9, 0.18],
    },
  });
  m.addLayer({
    id: "routes-line",
    type: "line",
    source: "routes",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": bandStepExpression("pm25", dark) as never,
      "line-width": ["case", ["==", ["get", "selected"], 1], 6, 3],
      "line-opacity": ["case", ["==", ["get", "selected"], 1], 1, 0.55],
    },
  });
  m.addLayer({
    id: "routes-hit",
    type: "line",
    source: "routes",
    paint: { "line-color": "#000", "line-width": 16, "line-opacity": 0 },
  });
  m.addLayer({
    id: "stations",
    type: "circle",
    source: "stations",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 4, 13, 8],
      "circle-color": bandStepExpression("pm25", dark) as never,
      "circle-opacity": ["case", ["==", ["get", "measured"], 1], 0.95, 0.45],
      "circle-stroke-color": ["case", ["==", ["get", "measured"], 1], paper, ink],
      "circle-stroke-width": ["case", ["==", ["get", "measured"], 1], 1.5, 1],
      "circle-stroke-opacity": ["case", ["==", ["get", "measured"], 1], 1, 0.35],
    },
  });
  m.addLayer({
    id: "endpoints",
    type: "circle",
    source: "endpoints",
    paint: {
      "circle-radius": 7,
      "circle-color": ["case", ["==", ["get", "kind"], "origin"], paper, ink],
      "circle-stroke-color": ink,
      "circle-stroke-width": 3,
    },
  });
}
