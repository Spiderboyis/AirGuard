"use client";
import { LngLatBounds, Map, NavigationControl, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Level, Route } from "@/lib/api";

if (typeof window !== "undefined") {
  setWorkerUrl("/maplibre-gl-worker.mjs");
}

const STYLE = process.env.NEXT_PUBLIC_MAP_STYLE_URL || "https://tiles.openfreemap.org/styles/liberty";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const colorExpr = (levels: Level[]): any => [
  "step",
  ["get", "pm25"],
  levels[0].color,
  ...levels.slice(0, -1).flatMap((level, i) => [(level.max as number) + 1e-6, levels[i + 1].color]),
];

export default function RouteMap({ routes, selected, levels }: { routes: Route[]; selected: string | null; levels: Level[] }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const fitted = useRef("");

  useEffect(() => {
    if (!box.current) return;
    const created = new Map({
      container: box.current,
      style: STYLE,
      center: [77.209, 28.614],
      zoom: 10.5,
    });
    created.addControl(new NavigationControl(), "top-right");
    map.current = created;
    return () => {
      created.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const current = map.current;
    if (!current || levels.length === 0) return;
    const draw = () => {
      const style = current.getStyle();
      (style?.layers ?? []).filter((layer) => layer.id.startsWith("rt-")).forEach((layer) => {
        if (current.getLayer(layer.id)) current.removeLayer(layer.id);
      });
      Object.keys(style?.sources ?? {}).filter((source) => source.startsWith("rt-")).forEach((source) => {
        if (current.getSource(source)) current.removeSource(source);
      });
      const bounds = new LngLatBounds();
      for (const route of routes) {
        const on = route.id === selected;
        route.geometry.forEach(([x, y]) => bounds.extend([x, y]));
        current.addSource(`rt-${route.id}-base`, {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: route.geometry } },
        });
        current.addLayer({
          id: `rt-${route.id}-base`,
          type: "line",
          source: `rt-${route.id}-base`,
          paint: { "line-color": "#ffffff", "line-width": on ? 9 : 6, "line-opacity": on ? 0.95 : 0.6 },
        });
        const features = route.segments
          .filter((segment) => segment.line.length > 1)
          .map((segment) => ({
            type: "Feature" as const,
            properties: { pm25: segment.pm25 },
            geometry: { type: "LineString" as const, coordinates: segment.line },
          }));
        current.addSource(`rt-${route.id}-seg`, { type: "geojson", data: { type: "FeatureCollection", features } });
        current.addLayer({
          id: `rt-${route.id}-seg`,
          type: "line",
          source: `rt-${route.id}-seg`,
          paint: { "line-color": colorExpr(levels), "line-width": on ? 5 : 3, "line-opacity": on ? 1 : 0.55 },
        });
      }
      const signature = routes.map((route) => `${route.id}:${route.geometry[0]?.join(",")}:${route.geometry.length}`).join("|");
      if (!bounds.isEmpty() && fitted.current !== signature) {
        current.fitBounds(bounds, { padding: 60, duration: 600 });
        fitted.current = signature;
      }
    };
    if (current.isStyleLoaded()) draw();
    else current.once("load", draw);
  }, [routes, selected, levels]);

  return <div ref={box} className="h-full min-h-[360px] w-full rounded-lg" />;
}
