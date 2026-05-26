import { useCallback, useEffect, useRef, useState } from "react";

type LaunchPhase = "intro" | "transition";

type DesktopLaunchSequenceProps = {
  active: boolean;
  reducedMotion: boolean;
  onComplete: () => void;
  onAmbientCue?: () => void;
};

export function DesktopLaunchSequence({ active, reducedMotion, onComplete, onAmbientCue }: DesktopLaunchSequenceProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fallbackTimerRef = useRef<number | null>(null);
  const completeTimerRef = useRef<number | null>(null);
  const ambientCueTimerRef = useRef<number | null>(null);
  const hasTransitionedRef = useRef(false);
  const introStartedAtRef = useRef<number>(0);
  const replayAttemptedRef = useRef(false);
  const ambientStartedRef = useRef(false);
  const [phase, setPhase] = useState<LaunchPhase>("intro");

  const clearTimers = useCallback(() => {
    if (fallbackTimerRef.current !== null) {
      window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    if (completeTimerRef.current !== null) {
      window.clearTimeout(completeTimerRef.current);
      completeTimerRef.current = null;
    }
    if (ambientCueTimerRef.current !== null) {
      window.clearTimeout(ambientCueTimerRef.current);
      ambientCueTimerRef.current = null;
    }
  }, []);

  const finishLaunch = useCallback(() => {
    clearTimers();
    onComplete();
  }, [clearTimers, onComplete]);

  const beginTransition = useCallback(() => {
    if (hasTransitionedRef.current) return;
    const elapsed = Date.now() - introStartedAtRef.current;
    const minimumVisibleMs = reducedMotion ? 320 : 2200;
    if (elapsed < minimumVisibleMs) {
      completeTimerRef.current = window.setTimeout(beginTransition, minimumVisibleMs - elapsed);
      return;
    }
    hasTransitionedRef.current = true;
    setPhase("transition");
    completeTimerRef.current = window.setTimeout(
      finishLaunch,
      reducedMotion ? 220 : 760
    );
  }, [finishLaunch, reducedMotion]);

  useEffect(() => {
    if (!active) return;
    const video = videoRef.current;
    if (!video) return;

    hasTransitionedRef.current = false;
    replayAttemptedRef.current = false;
    ambientStartedRef.current = false;
    introStartedAtRef.current = Date.now();
    setPhase("intro");
    clearTimers();

    const playVideo = async () => {
      if (reducedMotion) {
        beginTransition();
        return;
      }
      try {
        video.pause();
        video.muted = false;
        video.volume = 1;
        video.currentTime = 0;
        await video.play();
      } catch {
        try {
          video.muted = true;
          video.currentTime = 0;
          await video.play();
          window.setTimeout(() => {
            const activeVideo = videoRef.current;
            if (!activeVideo) return;
            activeVideo.muted = false;
            activeVideo.volume = 1;
          }, 120);
        } catch {
          beginTransition();
        }
      }
    };

    const handleLoadedMetadata = () => {
      if (reducedMotion) return;
      const durationMs = Number.isFinite(video.duration) && video.duration > 0 ? Math.ceil(video.duration * 1000) : 5000;
      ambientCueTimerRef.current = window.setTimeout(() => {
        if (ambientStartedRef.current) return;
        ambientStartedRef.current = true;
        onAmbientCue?.();
      }, Math.max(0, durationMs - 1000));
      fallbackTimerRef.current = window.setTimeout(beginTransition, durationMs + 1200);
    };

    const handleLoadedData = () => {
      void playVideo();
    };

    const handleEnded = () => {
      if (!replayAttemptedRef.current && video.currentTime < 0.25) {
        replayAttemptedRef.current = true;
        video.currentTime = 0;
        void video.play().catch(() => beginTransition());
        return;
      }
      beginTransition();
    };

    video.pause();
    video.currentTime = 0;
    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("loadeddata", handleLoadedData);
    video.addEventListener("ended", handleEnded);
    video.load();

    return () => {
      video.pause();
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("loadeddata", handleLoadedData);
      video.removeEventListener("ended", handleEnded);
      clearTimers();
    };
  }, [active, beginTransition, clearTimers, onAmbientCue, reducedMotion]);

  if (!active) return null;

  return (
    <div className={`launch-sequence launch-sequence-${phase}`} role="presentation">
      <video
        ref={videoRef}
        className="launch-sequence-video"
        src="/NullCSRenderForest.mp4"
        playsInline
        preload="metadata"
        onError={beginTransition}
      />
      <div className="launch-sequence-vignette" aria-hidden />
      <button type="button" className="launch-sequence-skip" onClick={finishLaunch}>
        Skip intro
      </button>
    </div>
  );
}
