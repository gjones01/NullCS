"use client";

import { MotionConfig } from "framer-motion";
import { useEffect } from "react";
import { initPostHog } from "@/lib/posthog";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    initPostHog();
  }, []);

  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
