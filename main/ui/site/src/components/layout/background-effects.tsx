"use client";

import dynamic from "next/dynamic";

const SignalConstellation = dynamic(
  () => import("@/components/layout/signal-constellation").then((mod) => mod.SignalConstellation),
  { ssr: false }
);

export function BackgroundEffects() {
  return <SignalConstellation />;
}
