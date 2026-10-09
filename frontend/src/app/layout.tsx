import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });

export const metadata: Metadata = {
  title: "AirGuard — Clean-Air Route Planner for Delhi NCR",
  description: "Minimize PM2.5 inhalation exposure with hourly multi-station forecasts and intelligent departure timing.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${outfit.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-200">
        {/* Minimalist Navigation Bar */}
        <header className="sticky top-0 z-50 border-b border-white/[0.08] bg-[#090a0d]/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 py-3">
            {/* Brand */}
            <div className="flex items-center gap-3">
              <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-90">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="font-display font-semibold text-white tracking-tight text-base">
                    AirGuard
                  </span>
                  <span className="text-xs text-zinc-500 font-mono">
                    Delhi NCR
                  </span>
                </div>
              </Link>
            </div>

            {/* Navigation links & Status indicator */}
            <nav className="flex items-center gap-1 sm:gap-4 text-xs font-medium">
              <Link
                href="/"
                className="px-3 py-1.5 rounded-lg text-zinc-200 hover:text-white hover:bg-white/[0.04] transition-colors"
              >
                Planner
              </Link>
              <Link
                href="/eval"
                className="px-3 py-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.04] transition-colors"
              >
                Evaluation
              </Link>
              <Link
                href="/about"
                className="px-3 py-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.04] transition-colors"
              >
                Documentation
              </Link>

              {/* Live status badge */}
              <div className="hidden sm:flex items-center gap-1.5 pl-3 border-l border-white/[0.08] text-[11px] font-mono text-zinc-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                <span>Live Feed</span>
              </div>
            </nav>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-5">
          {children}
        </div>
      </body>
    </html>
  );
}
