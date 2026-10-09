import { cn } from "@/lib/utils";

/** Mark: three particles settling out of a curve of air. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn("size-6", className)}>
      <path d="M3 9.5c3.2-3 6.8-3 10 0s6.8 3 8 1.6" fill="none" stroke="currentColor" strokeWidth="1.9"
        strokeLinecap="round" />
      <circle cx="7" cy="15.2" r="1.7" fill="var(--aq-poor)" />
      <circle cx="12.4" cy="17.4" r="1.25" fill="var(--aq-moderate)" />
      <circle cx="16.8" cy="19.2" r="0.9" fill="var(--aq-good)" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-serif text-[1.35rem] leading-none font-medium tracking-[-0.01em]">AirGuard</span>
    </span>
  );
}
