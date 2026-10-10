import Link from "next/link";

import { LogoMark } from "@/components/brand/logo";

const SOURCES = [
  { name: "OpenAQ", href: "https://openaq.org" },
  { name: "CPCB / DPCC / IMD via OpenAQ", href: "https://cpcb.nic.in" },
  { name: "Open-Meteo", href: "https://open-meteo.com" },
  { name: "Copernicus CAMS", href: "https://atmosphere.copernicus.eu" },
  { name: "NASA FIRMS", href: "https://firms.modaps.eosdis.nasa.gov" },
  { name: "© OpenStreetMap contributors", href: "https://www.openstreetmap.org/copyright" },
  { name: "OSRM / FOSSGIS", href: "https://routing.openstreetmap.de" },
  { name: "Photon", href: "https://photon.komoot.io" },
  { name: "OpenFreeMap", href: "https://openfreemap.org" },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1fr_2fr]">
        <div className="space-y-3">
          <div className="flex items-center gap-2 font-serif text-lg">
            <LogoMark className="size-5" /> AirGuard
          </div>
          <p className="max-w-xs text-sm text-muted-foreground">
            Exposure guidance from a forecast and stated assumptions. Not medical advice — if air pollution
            affects your health, talk to a doctor.
          </p>
          <div className="flex gap-4 text-sm">
            <Link href="/method" className="underline-offset-4 hover:underline">Method</Link>
            <Link href="/evidence" className="underline-offset-4 hover:underline">Evidence</Link>
            <Link href="/welcome" className="underline-offset-4 hover:underline">Set up profile</Link>
          </div>
        </div>
        <div>
          <p className="mb-3 text-xs font-medium tracking-[0.12em] text-muted-foreground uppercase">Data and services</p>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {SOURCES.map((s) => (
              <li key={s.name}>
                <a href={s.href} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-foreground">
                  {s.name}
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Weather and CAMS data are used under Open-Meteo&apos;s non-commercial terms (CC BY 4.0).
          </p>
        </div>
      </div>
    </footer>
  );
}
