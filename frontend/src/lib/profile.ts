"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Mode, Sensitivity } from "./api";

export interface Place {
  name: string;
  lat: number;
  lon: number;
  detail?: string;
}

export interface Profile {
  onboarded: boolean;
  name: string;
  mode: Mode;
  sensitivity: Sensitivity;
  maxExtraMin: number;
  maxWaitMin: number;
  usualFrom: Place | null;
  usualTo: Place | null;
}

interface ProfileStore extends Profile {
  update: (p: Partial<Profile>) => void;
  reset: () => void;
}

const DEFAULTS: Profile = {
  onboarded: false,
  name: "",
  mode: "cycle",
  sensitivity: "normal",
  maxExtraMin: 15,
  maxWaitMin: 120,
  usualFrom: null,
  usualTo: null,
};

/** The traveller's profile lives only in this browser (no account needed). */
export const useProfile = create<ProfileStore>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      update: (p) => set(p),
      reset: () => set(DEFAULTS),
    }),
    { name: "airguard-profile", version: 1 },
  ),
);

export const MODE_LABEL: Record<Mode, string> = {
  walk: "Walk",
  cycle: "Cycle",
  two_wheeler: "Two-wheeler",
  car: "Car",
};

export const SENSITIVITY_COPY: Record<Sensitivity, { title: string; body: string; short: string }> = {
  normal: {
    title: "Not especially",
    body: "Healthy adult. Pick a cleaner option when it costs only a little extra time.",
    short: "Standard",
  },
  sensitive: {
    title: "I'm sensitive to it",
    body: "Asthma, allergies, pregnancy, or 60+. Trade more time for cleaner air.",
    short: "Sensitive",
  },
  high: {
    title: "It hits me hard",
    body: "Severe asthma, COPD, a heart condition, or travelling with small children.",
    short: "Highly sensitive",
  },
};
