import type { Metadata } from "next";

import { Planner } from "./planner";

export const metadata: Metadata = { title: "Plan a trip" };

export default function PlanPage() {
  return <Planner />;
}
