"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { posthog } from "@/lib/posthog";

export function PageViewTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname || !posthog.__loaded) return;
    posthog.capture("$pageview", {
      $current_url: `${window.location.origin}${pathname}`,
    });
  }, [pathname]);

  return null;
}
