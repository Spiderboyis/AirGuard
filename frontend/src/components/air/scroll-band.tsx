"use client";

import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";

import { BANDS } from "@/lib/aq";

/**
 * Reading-progress bar in the CPCB colours: fixed to the top of the window, revealed left to right as
 * the page scrolls down and hidden again on the way up. The colours stay put; only the reveal moves.
 */
export function ScrollBand() {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const eased = useSpring(scrollYProgress, { stiffness: 260, damping: 36, mass: 0.35 });
  const clipPath = useTransform(reduce ? scrollYProgress : eased, (v) => `inset(0 ${(1 - v) * 100}% 0 0)`);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px]">
      <div className="absolute inset-0 bg-foreground/[0.06]" />
      <motion.div className="absolute inset-0 flex" style={{ clipPath }}>
        {BANDS.map((b) => (
          <span key={b.key} className="flex-1" style={{ background: b.color }} />
        ))}
      </motion.div>
    </div>
  );
}
