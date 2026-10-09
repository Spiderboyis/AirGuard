import type { Metadata } from "next";

import { Onboarding } from "./onboarding";

export const metadata: Metadata = { title: "Set up your profile" };

export default function WelcomePage() {
  return <Onboarding />;
}
