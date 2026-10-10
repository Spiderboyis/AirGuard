import { BANDS } from "@/lib/aq";
import { cn } from "@/lib/utils";

/** The CPCB scale as a thin stepped rule: the page's top edge and the marker above section headings. */
export function BandRule({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("flex h-[3px] w-full overflow-hidden", className)}>
      {BANDS.map((b) => (
        <span key={b.key} className="flex-1" style={{ background: b.color }} />
      ))}
    </div>
  );
}
