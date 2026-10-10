"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/brand/theme-toggle";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/plan", label: "Plan a trip" },
  { href: "/evidence", label: "Evidence" },
  { href: "/method", label: "Method" },
];

export function SiteHeader({ className, compact = false }: { className?: string; compact?: boolean }) {
  const path = usePathname();
  return (
    <header
      className={cn(
        "z-30 flex items-center justify-between gap-4 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6",
        compact ? "h-14" : "h-16",
        className,
      )}
    >
      <Link href="/" className="rounded-md outline-offset-4" aria-label="AirGuard home">
        <Logo />
      </Link>
      <nav className="flex items-center gap-1 text-sm">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
              path.startsWith(n.href) && "text-foreground",
              n.href !== "/plan" && "hidden sm:inline-block",
            )}
          >
            {n.label}
          </Link>
        ))}
        <ThemeToggle />
      </nav>
    </header>
  );
}
