"use client";

import posthog from "posthog-js";

let started = false;

export function initPostHog() {
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;

  if (started || !key || !host || typeof window === "undefined") {
    return null;
  }

  posthog.init(key, {
    api_host: host,
    capture_pageview: true,
    capture_pageleave: true,
    person_profiles: "identified_only",
    autocapture: false,
  });

  started = true;
  return posthog;
}

export { posthog };
