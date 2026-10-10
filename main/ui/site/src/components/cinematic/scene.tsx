"use client";

import { useEffect, useRef, useState } from "react";
import type { SceneOptions, SceneState } from "./instrument-engine";

export function InstrumentScene({
  mode,
  progress = 0,
  progressRef,
  stage = 0,
  channel = 0,
  samples,
  motion = true,
}: {
  mode: SceneOptions["mode"];
  progress?: number;
  progressRef?: { current: number };
  stage?: number;
  channel?: number;
  samples?: number[][];
  motion?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef<SceneState>({ progress, stage, channel, motion });
  state.current = { progress, stage, channel, motion };
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let disposed = false,
      started = false,
      cleanup: (() => void) | undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting || started) return;
        started = true;
        void import("./instrument-engine")
          .then(({ mountInstrument }) => {
            if (disposed) return;
            try {
              cleanup = mountInstrument(element, {
                mode,
                samples,
                read: () => ({
                  ...state.current,
                  progress: progressRef?.current ?? state.current.progress,
                }),
                ready: (value) => {
                  if (!disposed) {
                    setReady(value);
                    if (!value) setFailed(true);
                  }
                },
              });
            } catch {
              setFailed(true);
            }
          })
          .catch(() => {
            if (!disposed) setFailed(true);
          });
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => {
      disposed = true;
      observer.disconnect();
      cleanup?.();
    };
  }, [mode, samples, progressRef]);
  return (
    <div
      className={`instrument-scene ${ready ? "scene-ready" : ""}`}
      data-mode={mode}
    >
      {mode === "hero" ? (
        <div className="hero-agent" aria-hidden="true">
          <div className="agent-portrait" />
          <span className="agent-registration agent-registration-top">CS2 / ENCOUNTER STUDY</span>
          <span className="agent-registration agent-registration-bottom">AIM / MOVEMENT / TIMING</span>
        </div>
      ) : (
        <div className="instrument-fallback" aria-hidden="true">
          <div />
          <div />
          <div />
          <span>NULLCS</span>
        </div>
      )}
      <div className="webgl-surface" ref={host} />
      {failed && (
        <span className="scene-fallback-note">
          Still view / interactive graphics unavailable
        </span>
      )}
    </div>
  );
}
