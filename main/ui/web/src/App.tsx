import { AnimatePresence, motion } from "framer-motion";
import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import {
  type DemoStatus,
  type EvidenceTable,
  type ExplainReport,
  type HealthResponse,
  type InterpretationMetric,
  type InterpretationModel,
  type PlayerRow,
  type ScoreTrace,
  type SignalComponent,
  explainPlayer,
  getEvidenceTable,
  getExplainReport,
  getHealth,
  getPlayerScoreTrace,
  getPlayers,
  getStatus,
  queueLocalDemoPath,
  runDemo,
  uploadDemo,
} from "./lib/api";
import { getDesktopServiceStatus, isDesktopShell, openExternalUrl, pickDesktopDemoFile, startDesktopService, type DesktopServiceStatus } from "./desktopBridge";
import type { ReviewBundle } from "./reviewBundle";
import { openBundledSampleReview, openImportedReviewBundle } from "./reviewDataSource";
import { SAMPLE_STEAMID } from "./mockData";
import { setApiAccessToken, setApiBaseUrl } from "./runtimeConfig";
import { AntigravityField } from "./components/AntigravityField";
import { DesktopLaunchSequence } from "./components/DesktopLaunchSequence";
import { ImmersiveHeroScene } from "./components/ImmersiveHeroScene";
import { MetallicLogo } from "./components/MetallicLogo";
import { ProcessingOverlay } from "./components/ProcessingOverlay";

type Stage = "home" | "about" | "processing" | "results" | "report";
type ReportTab = "overview" | "reasons" | "trace";
type PlayerVizTab = "signal" | "match" | "process";
type Tone = "critical" | "warning" | "elevated" | "good" | "cool" | "neutral";
type ReviewPriority = "highest" | "priority" | "review" | "monitor";
type AnalystAction = "escalate_context" | "review_sequence" | "hold_for_context" | "close_low_priority";
const SESSION_KEY = "nullcs_desktop_session_v1";
const BETA_NOTICE_KEY = "nullcs_beta_notice_v1_acknowledged";
const PIPELINE_STEPS = ["Uploading", "Parsing", "Feature Build", "Model", "Explanation"];
const POINTS = [
  { id: "n1", x: 9, y: 18, size: 2.5, value: 54 }, { id: "n2", x: 18, y: 34, size: 2, value: 68 }, { id: "n3", x: 29, y: 24, size: 2.2, value: 31 },
  { id: "n4", x: 40, y: 44, size: 1.8, value: 82 }, { id: "n5", x: 54, y: 20, size: 2.8, value: 49 }, { id: "n6", x: 63, y: 38, size: 1.8, value: 63 },
  { id: "n7", x: 73, y: 28, size: 2.1, value: 27 }, { id: "n8", x: 83, y: 42, size: 2.4, value: 77 }, { id: "n9", x: 91, y: 26, size: 2.1, value: 14 },
  { id: "n10", x: 15, y: 72, size: 2.2, value: 21 }, { id: "n11", x: 30, y: 64, size: 1.9, value: 96 }, { id: "n12", x: 48, y: 78, size: 2.7, value: 35 },
  { id: "n13", x: 66, y: 70, size: 2.2, value: 72 }, { id: "n14", x: 84, y: 76, size: 2.6, value: 91 },
] as const;
const LINKS = [["n1","n2"],["n2","n3"],["n3","n5"],["n5","n7"],["n7","n9"],["n2","n10"],["n10","n11"],["n11","n12"],["n12","n13"],["n13","n14"],["n4","n6"],["n6","n8"],["n5","n6"],["n7","n8"]] as const;
const SIGNAL_SCALE_ANCHORS = [
  { raw: 0, display: 0 },
  { raw: 5, display: 8 },
  { raw: 10, display: 18 },
  { raw: 18, display: 42 },
  { raw: 40, display: 72 },
  { raw: 70, display: 100 },
] as const;

const pct = (v?: number | null) => (v === null || v === undefined || Number.isNaN(v) ? "--" : `${(v * 100).toFixed(1)}%`);
const num = (v?: number | null, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "--" : v.toFixed(d));
const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
const shortId = (value: string, start = 6, end = 4) => (value.length > start + end ? `${value.slice(0, start)}...${value.slice(-end)}` : value);
const looksLikeGeneratedDemoId = (value: string) => /^TEST_\d{8}_\d{6}_[A-Za-z0-9]+$/i.test(value);
const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const displayDemoLabel = (demoId: string, originalFilename: string) => originalFilename ? originalFilename.replace(/\.dem$/i, "") : (looksLikeGeneratedDemoId(demoId) ? "Uploaded Demo" : demoId);
const isRateMetric = (key: string) => /(rate|pct|share|confidence|risk|prob|percentile)/i.test(key);
const safeText = (value: unknown, fallback = "") => {
  if (typeof value !== "string") return fallback;
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (!cleaned || cleaned.toLowerCase() === "nan" || cleaned.toLowerCase() === "none") return fallback;
  return cleaned;
};
const safeNumber = (value: unknown, fallback = 0) => {
  if (typeof value === "number") return Number.isFinite(value) ? value : fallback;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
};
const safeMaybeNumber = (value: unknown) => {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const validSteamId = (steamid: string) => /^\d{17}$/.test(steamid);
const steamCommunityUrl = (steamid: string) => `https://steamcommunity.com/profiles/${encodeURIComponent(steamid)}`;
const csStatsUrl = (steamid: string) => `https://csstats.gg/player/${encodeURIComponent(steamid)}`;
const userErrorMessage = (err: unknown) => {
  const raw = err instanceof Error ? err.message : String(err || "Unknown error");
  return raw.replace(/^Error:\s*/i, "").trim() || "Something went wrong.";
};
const METRIC_INFO: Record<string, string> = {
  "Review Lane": "A neutral workflow label based on how unusual this player looks relative to others in the same match. It is not a cheating verdict.",
  "Evidence Confidence": "How stable and well-supported the current behavior signal is. High confidence means the score has enough supporting evidence to review carefully, not that the case is settled.",
  "Lobby Rank": "Where the player sits relative to others in this specific match by behavioral deviation. Rank is match-relative only.",
  "Reaction Window": "Median visibility-to-shot timing across tracked kill events. Lower values can be unusual, but context matters.",
  "Shot Discipline": "Share of kills where the shot timing suggests prefire-like behavior before or immediately as visibility begins.",
  "Accuracy Concentration": "Headshot share within the player's tracked kill sample. Strong aim alone can be legitimate, especially for top players.",
  "Occlusion Anomaly": "Share of smoke-occluded kills. Elevated values can merit context review, but are not decisive on their own.",
};
const DEFAULT_PRODUCT_IDENTITY = "Single-match behavioral review workspace";
const DEFAULT_PRODUCT_TAGLINE = "Match-relative behavioral review with explainable evidence and neutral analysis.";
const detectLowPowerDefault = () => {
  const nav = navigator as Navigator & { deviceMemory?: number };
  return (navigator.hardwareConcurrency || 8) <= 4 || (nav.deviceMemory || 8) <= 4;
};

const ABOUT_PILLARS = [
  {
    title: "Research project first",
    body: "NullCS is a data science and machine learning research project focused on whether suspicious in-game behavior can be surfaced in a measurable, explainable way.",
  },
  {
    title: "Focused on measurable behavior",
    body: "Instead of relying on one headline stat, the system studies timing, sequence, visibility pressure, movement, and encounter structure to see what patterns stand out.",
  },
  {
    title: "Built to stay understandable",
    body: "The goal is not to produce a final verdict. The goal is to surface useful signals, show supporting context, and help a human reviewer understand why a player was raised.",
  },
] as const;

const ABOUT_STEPS = [
  "Load one demo and score the whole lobby.",
  "Raise the strongest standouts relative to that match.",
  "Show why the signal was raised and what weakens it.",
  "Leave the final judgment to the person reviewing the case.",
] as const;

const NEUTRAL_METRIC_KEYS = new Set([
  "signal_stability",
]);

const BENCHMARK_BANDS: Record<
  string,
  { yellow: number; orange: number; red: number; direction?: "higher" | "lower"; format?: "percent" | "number" }
> = {
  aim_process_global_score: { yellow: 0.206, orange: 0.223, red: 0.23, direction: "higher", format: "number" },
  enc_input_burst_score: { yellow: 0.316, orange: 0.393, red: 0.443, direction: "higher", format: "number" },
  enc_input_stability_score: { yellow: 0.186, orange: 0.246, red: 0.283, direction: "higher", format: "number" },
  enc_precision_under_difficulty: { yellow: 0.478, orange: 0.514, red: 0.538, direction: "higher", format: "number" },
  enc_process_abnormality: { yellow: 0.31, orange: 0.335, red: 0.346, direction: "higher", format: "number" },
  enc_acquire_shot_lag_p90: { yellow: 78, orange: 92, red: 104, direction: "higher", format: "number" },
  enc_aim_dwell_mean: { yellow: 60, orange: 68, red: 74, direction: "higher", format: "number" },
  enc_damage_end_rate: { yellow: 0.12, orange: 0.24, red: 0.42, direction: "higher", format: "percent" },
  enc_ttdmg_high_rate: { yellow: 0.12, orange: 0.24, red: 0.42, direction: "higher", format: "percent" },
  aim_process_global_pct: { yellow: 0.72, orange: 0.88, red: 0.96, direction: "higher", format: "percent" },
  difficulty_precision_pct: { yellow: 0.72, orange: 0.88, red: 0.96, direction: "higher", format: "percent" },
  process_contradiction_pct: { yellow: 0.45, orange: 0.68, red: 0.85, direction: "higher", format: "percent" },
  mechanics_pct: { yellow: 0.72, orange: 0.88, red: 0.96, direction: "higher", format: "percent" },
  prefire_pct: { yellow: 0.72, orange: 0.88, red: 0.96, direction: "higher", format: "percent" },
  thrusmoke_pct: { yellow: 0.72, orange: 0.88, red: 0.96, direction: "higher", format: "percent" },
  visibility: { yellow: 0.45, orange: 0.7, red: 0.9, direction: "higher", format: "number" },
  engagements: { yellow: 0.45, orange: 0.7, red: 0.9, direction: "higher", format: "number" },
  rounds: { yellow: 0.45, orange: 0.7, red: 0.9, direction: "higher", format: "number" },
  halves: { yellow: 0.45, orange: 0.7, red: 0.9, direction: "higher", format: "number" },
  weapons: { yellow: 0.45, orange: 0.7, red: 0.9, direction: "higher", format: "number" },
  enn_score_top3_mean: { yellow: 0.78, orange: 0.84, red: 0.89, direction: "higher", format: "number" },
  enn_kill_end_mean: { yellow: 0.38, orange: 0.46, red: 0.53, direction: "higher", format: "number" },
  enn_score_median: { yellow: 0.34, orange: 0.43, red: 0.52, direction: "higher", format: "number" },
  enn_score_mean: { yellow: 0.37, orange: 0.45, red: 0.51, direction: "higher", format: "number" },
  enn_low_vis_mean: { yellow: 0.37, orange: 0.45, red: 0.51, direction: "higher", format: "number" },
  enn_hard_mean: { yellow: 0.37, orange: 0.45, red: 0.51, direction: "higher", format: "number" },
  rt_median: { yellow: 90, orange: 75, red: 65, direction: "lower", format: "number" },
  prefire_rate: { yellow: 0.091, orange: 0.132, red: 0.154, direction: "higher", format: "percent" },
  thrusmoke_kill_rate: { yellow: 0.154, orange: 0.208, red: 0.235, direction: "higher", format: "percent" },
  headshot_rate: { yellow: 0.562, orange: 0.667, red: 0.706, direction: "higher", format: "percent" },
  enc_mouse_burst_mean: { yellow: 19.722, orange: 31.803, red: 43.219, direction: "higher", format: "number" },
};

function normalizePlayer(player: PlayerRow): PlayerRow {
  const features = player && typeof player.features_summary === "object" && player.features_summary !== null ? player.features_summary : {};
  return {
    steamid: safeText(player?.steamid, "unknown"),
    attacker_name: safeText(player?.attacker_name, "Unknown player"),
    proba_cheater_infer: safeNumber(player?.proba_cheater_infer, 0),
    risk: safeMaybeNumber(player?.risk) ?? undefined,
    confidence: safeMaybeNumber(player?.confidence) ?? undefined,
    ci_low: safeMaybeNumber(player?.ci_low),
    ci_high: safeMaybeNumber(player?.ci_high),
    risk_band: safeText(player?.risk_band, ""),
    top_reasons: Array.isArray(player?.top_reasons) ? player.top_reasons : [],
    features_summary: Object.fromEntries(
      Object.entries(features).map(([key, value]) => [key, safeMaybeNumber(value)])
    ),
    interpretation: player?.interpretation,
  };
}

function useAnimatedNumber(value: number, duration = 650) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    let frame = 0;
    const start = display;
    const target = value;
    const startedAt = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + (target - start) * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return display;
}

function metricTone(key: string, value?: number | null): Tone {
  if (value === null || value === undefined || Number.isNaN(value)) return "neutral";
  if (NEUTRAL_METRIC_KEYS.has(key)) return "neutral";
  const k = key.toLowerCase();
  if (NEUTRAL_METRIC_KEYS.has(k)) return "neutral";
  const bands = BENCHMARK_BANDS[key];
  if (bands) {
    if (bands.direction === "lower") {
      if (value <= bands.red) return "critical";
      if (value <= bands.orange) return "warning";
      if (value <= bands.yellow) return "elevated";
      return "good";
    }
    if (value >= bands.red) return "critical";
    if (value >= bands.orange) return "warning";
    if (value >= bands.yellow) return "elevated";
    return "good";
  }
  if (k.includes("confidence") || k.includes("support")) return value >= 0.75 ? "good" : value >= 0.45 ? "elevated" : value >= 0.25 ? "warning" : "critical";
  if (k.includes("percentile") || k.endsWith(" pct") || k.endsWith("_pct")) return value >= 0.96 ? "critical" : value >= 0.88 ? "warning" : value >= 0.72 ? "elevated" : "good";
  if (k.includes("risk") || k.includes("prob")) return signalTone(value);
  if (k.includes("rt_median") || k.includes("median rt")) return value <= 3.5 ? "critical" : value <= 5.5 ? "warning" : value <= 8.5 ? "elevated" : "good";
  if (k.includes("prefire")) return value >= 0.33 ? "critical" : value >= 0.22 ? "warning" : value >= 0.12 ? "elevated" : "good";
  if (k.includes("headshot")) return value >= 0.88 ? "critical" : value >= 0.72 ? "warning" : value >= 0.58 ? "elevated" : "good";
  if (k.includes("long_range_fast_rt")) return value >= 0.65 ? "critical" : value >= 0.45 ? "warning" : value >= 0.25 ? "elevated" : "good";
  if (k.includes("thrusmoke")) return value >= 0.18 ? "critical" : value >= 0.1 ? "warning" : value >= 0.04 ? "elevated" : "good";
  return value >= 0.7 ? "critical" : value >= 0.45 ? "warning" : value >= 0.2 ? "elevated" : "good";
}

function toneLabel(tone: Tone) {
  if (tone === "critical") return "Critical";
  if (tone === "warning") return "High";
  if (tone === "elevated") return "Elevated";
  if (tone === "good") return "Low";
  if (tone === "cool") return "Verified";
  return "Neutral";
}

function reviewPriority(score: number | null | undefined, rank: number, total: number): ReviewPriority {
  const safeScore = score ?? 0;
  const topSlice = total > 0 ? rank / total : 1;
  if (rank === 1 || safeScore >= 0.2 || topSlice <= 0.15) return "highest";
  if (rank <= 2 || safeScore >= 0.12 || topSlice <= 0.3) return "priority";
  if (rank <= Math.max(3, Math.ceil(total * 0.5)) || safeScore >= 0.06) return "review";
  return "monitor";
}

function reviewPriorityLabel(priority: ReviewPriority) {
  if (priority === "highest") return "Top deviation in match";
  if (priority === "priority") return "Above match baseline";
  if (priority === "review") return "Analyst watchlist";
  return "Within expected spread";
}

function reviewPriorityHint(priority: ReviewPriority) {
  if (priority === "highest") return "largest behavioral deviation in this lobby, still not a verdict";
  if (priority === "priority") return "above the lobby baseline and worth contextual review";
  if (priority === "review") return "some atypical patterns worth keeping on the analyst radar";
  return "not meaningfully elevated relative to this lobby";
}

function confidenceBand(confidence: number | null | undefined) {
  const value = confidence ?? 0;
  if (value >= 0.82) return "Well-supported";
  if (value >= 0.58) return "Moderately supported";
  if (value >= 0.38) return "Thin support";
  return "Sparse support";
}

function uncertaintyNote(confidence: number | null | undefined, ciLow?: number | null, ciHigh?: number | null) {
  if (ciLow !== null && ciLow !== undefined && ciHigh !== null && ciHigh !== undefined) {
    const width = Math.max(0, ciHigh - ciLow);
    if (width >= 0.28) return "wide uncertainty band";
    if (width >= 0.16) return "moderate uncertainty band";
    return "tight uncertainty band";
  }
  return confidenceBand(confidence);
}

function analystAction(priority: ReviewPriority, confidence: number | null | undefined): AnalystAction {
  const value = confidence ?? 0;
  if (priority === "highest" && value >= 0.58) return "escalate_context";
  if (priority === "priority" || (priority === "highest" && value < 0.58)) return "review_sequence";
  if (priority === "review") return "hold_for_context";
  return "close_low_priority";
}

function analystActionLabel(action: AnalystAction) {
  if (action === "escalate_context") return "Escalate with context";
  if (action === "review_sequence") return "Review sequence evidence";
  if (action === "hold_for_context") return "Hold for more context";
  return "Close as low priority";
}

function analystActionSummary(action: AnalystAction) {
  if (action === "escalate_context") return "Top match-relative deviation with enough support to compare against POV, utility timing, and external match context.";
  if (action === "review_sequence") return "Behavior looks elevated, but the next step is evidence review rather than conclusion.";
  if (action === "hold_for_context") return "Keep this player on the analyst board and wait for corroborating rounds or additional metadata.";
  return "Current evidence does not justify deeper review relative to the rest of the lobby.";
}

function analystActionDetail(action: AnalystAction) {
  if (action === "escalate_context") return "Recommended next step: cross-check standout rounds, opponents' perspective, and match-level context before raising severity.";
  if (action === "review_sequence") return "Recommended next step: inspect reasons, evidence CSVs, and reaction trace for clustering instead of isolated highlight plays.";
  if (action === "hold_for_context") return "Recommended next step: preserve the report and revisit only if adjacent signals, player history, or external reports align.";
  return "Recommended next step: document the rank and confidence, then deprioritize unless new evidence appears.";
}

function normalizedSignalWidth(key: string, value: number | null) {
  if (value === null || !Number.isFinite(value)) return 0.08;
  if (NEUTRAL_METRIC_KEYS.has(key) || NEUTRAL_METRIC_KEYS.has(key.toLowerCase())) {
    return isRateMetric(key) ? clamp01(value) : clamp01(Math.min(Math.abs(value), 1));
  }
  const bands = BENCHMARK_BANDS[key];
  if (bands) {
    if (bands.direction === "lower") {
      const worst = Math.max(1e-6, bands.yellow - bands.red);
      return clamp01((bands.yellow - value) / worst);
    }
    return clamp01(value / Math.max(bands.red, 1e-6));
  }
  const k = key.toLowerCase();
  if (/(confidence|risk|rate|share|percentile|prob)/i.test(k)) return clamp01(value);
  if (k.includes("rt_median")) return clamp01(1 - Math.min(value, 24) / 24);
  if (k.includes("distance")) return clamp01(Math.min(value, 1500) / 1500);
  return clamp01(Math.min(Math.abs(value), 1));
}

function formatSignalValue(key: string, value: number | null) {
  if (value === null || !Number.isFinite(value)) return "--";
  const bands = BENCHMARK_BANDS[key];
  if (bands?.format === "percent") return pct(value);
  return isRateMetric(key) ? pct(value) : num(value, key.toLowerCase().includes("rt") ? 1 : 2);
}

const FEATURE_COPY: Record<string, { label: string; summary: string }> = {
  rt_median: {
    label: "Typical shot timing",
    summary: "Median time from visibility to shot; lower values can mean unusually fast engagement timing.",
  },
  prefire_rate: {
    label: "Prefire tendency",
    summary: "Share of kills where the shot timing looks pre-aimed or fired as visibility begins.",
  },
  thrusmoke_kill_rate: {
    label: "Low-visibility kills",
    summary: "Share of kills through smoke or similar low-information situations.",
  },
  headshot_rate: {
    label: "Headshot share",
    summary: "How often tracked kills ended as headshots; useful context, not decisive by itself.",
  },
  enc_acquire_shot_lag_p90: {
    label: "Slowest acquire-to-shot window",
    summary: "Upper-end delay between aim settling and shooting; extreme values can reveal unusual engagement rhythm.",
  },
  enc_aim_dwell_mean: {
    label: "Aim hold duration",
    summary: "Average time the crosshair stays settled during tracked fights.",
  },
  aim_process_global_score: {
    label: "Aim-process anomaly",
    summary: "How unusual the player's aim-settling pattern is compared with normal encounter behavior.",
  },
  enn_score_mean: {
    label: "Encounter model average",
    summary: "Average suspiciousness across the player's tracked fight windows.",
  },
  enn_low_vis_mean: {
    label: "Low-visibility encounter signal",
    summary: "Encounter-model support from fights with limited visual information.",
  },
  enn_hard_mean: {
    label: "Hard-fight encounter signal",
    summary: "Encounter-model support from longer, faster, or harder-to-control fights.",
  },
  enn_score_top3_mean: {
    label: "Strongest encounter cluster",
    summary: "Average of the player's three strongest fight-window signals.",
  },
  enc_precision_under_difficulty: {
    label: "Precision under pressure",
    summary: "How clean aim remains when fights are harder because of distance, speed, or visibility.",
  },
  enc_process_abnormality: {
    label: "Process mismatch",
    summary: "Combined signal for aim, timing, and visibility behavior that does not degrade as expected.",
  },
  enc_damage_end_rate: {
    label: "Damage conversion rate",
    summary: "Share of tracked encounters that convert into damage-ending outcomes.",
  },
  enc_ttdmg_high_rate: {
    label: "Delayed damage pressure",
    summary: "Share of encounters with unusually high time-to-damage pressure.",
  },
  enc_mouse_burst_mean: {
    label: "Mouse burst level",
    summary: "How much mouse-input burst appears around tracked engagements.",
  },
};

function metricRows(player: PlayerRow | null, rank: number, total: number) {
  if (!player) return [];
  const priority = reviewPriority(player.risk, rank, total);
  const lobbyPct = total > 1 ? 1 - (rank - 1) / (total - 1) : 1;
  return [
    { label: "Review Lane", key: "review_lane", raw: null, value: reviewPriorityLabel(priority), hint: reviewPriorityHint(priority) },
    { label: "Evidence Confidence", key: "confidence", raw: player.confidence ?? null, value: pct(player.confidence), hint: confidenceBand(player.confidence) },
    { label: "Lobby Rank", key: "lobby_rank", raw: rank, value: `#${rank}/${total}`, hint: `${Math.round(lobbyPct * 100)}th percentile in current lobby` },
    { label: "Reaction Window", key: "rt_median", raw: player.features_summary.rt_median ?? null, value: `${num(player.features_summary.rt_median, 1)} ticks`, hint: "median visibility-to-shot timing" },
    { label: "Shot Discipline", key: "prefire_rate", raw: player.features_summary.prefire_rate ?? null, value: pct(player.features_summary.prefire_rate), hint: "prefire share per kill" },
    { label: "Accuracy Concentration", key: "headshot_rate", raw: player.features_summary.headshot_rate ?? null, value: pct(player.features_summary.headshot_rate), hint: "headshot share" },
  ];
}

function ConstellationBackground({ reducedMotion }: { reducedMotion: boolean }) {
  const pointMap = Object.fromEntries(POINTS.map((point) => [point.id, point])) as Record<string, (typeof POINTS)[number]>;
  return (
    <div className="constellation-field" aria-hidden>
      <motion.svg viewBox="0 0 100 100" className="constellation-svg" initial={false} animate={reducedMotion ? { opacity: 0.52 } : { opacity: [0.4, 0.66, 0.48] }} transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}>
        {LINKS.map(([from, to], index) => (
          <motion.line key={`${from}-${to}`} x1={pointMap[from].x} y1={pointMap[from].y} x2={pointMap[to].x} y2={pointMap[to].y} className="constellation-link" initial={false} animate={reducedMotion ? { opacity: 0.3 } : { opacity: [0.16, 0.58, 0.24] }} transition={{ duration: 5 + (index % 5), repeat: Infinity, repeatType: "mirror", delay: index * 0.18 }} />
        ))}
        {POINTS.map((point, index) => (
          <g key={point.id}>
            <motion.circle cx={point.x} cy={point.y} r={point.size} className="constellation-node" initial={false} animate={reducedMotion ? { opacity: 0.7, scale: 1 } : { opacity: [0.45, 1, 0.55], scale: [1, 1.35, 1] }} transition={{ duration: 3.5 + (index % 4), repeat: Infinity, repeatType: "mirror", delay: index * 0.2 }} />
            <motion.text
              x={point.x + 1.4}
              y={point.y + 3.6}
              className="constellation-label"
              initial={false}
              animate={reducedMotion ? { opacity: 0.45 } : { opacity: [0.2, 0.72, 0.24] }}
              transition={{ duration: 4.5 + (index % 5), repeat: Infinity, repeatType: "mirror", delay: index * 0.14 }}
            >
              {String(point.value).padStart(2, "0")}
            </motion.text>
          </g>
        ))}
      </motion.svg>
      <div className="beam beam-left" />
      <div className="beam beam-right" />
      <div className="beam beam-center" />
    </div>
  );
}

function AnimatedNumber({ value, decimals = 1, prefix = "", suffix = "" }: { value: number; decimals?: number; prefix?: string; suffix?: string }) {
  const animated = useAnimatedNumber(value);
  return <span>{prefix}{animated.toFixed(decimals)}{suffix}</span>;
}

function Gauge({ label, value, tone, hint, displayOverride }: { label: string; value: number; tone: Tone; hint?: string; displayOverride?: string }) {
  const clamped = clamp01(value);
  const animated = useAnimatedNumber(clamped * 100, 700);
  const radius = 74;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className={`orb-gauge tone-${tone}`}>
      <div className="orb-halo" />
      <svg viewBox="0 0 200 200" className="orb-svg" aria-hidden>
        <defs>
          <linearGradient id={`gauge-${label}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.98)" />
            <stop offset="55%" stopColor="var(--tone-main)" />
            <stop offset="100%" stopColor="var(--tone-deep)" />
          </linearGradient>
        </defs>
        <circle cx="100" cy="100" r={radius} className="orb-track" />
        <motion.circle cx="100" cy="100" r={radius} className="orb-progress" stroke={`url(#gauge-${label})`} initial={false} animate={{ strokeDashoffset: circumference * (1 - clamped) }} transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }} style={{ strokeDasharray: circumference }} />
      </svg>
      <div className="orb-center">
        <div className="orb-value">{displayOverride || <AnimatedNumber value={animated} decimals={0} suffix="%" />}</div>
        <div className="orb-label">{label}</div>
        <div className="orb-hint">{hint || toneLabel(tone)}</div>
      </div>
    </div>
  );
}

function InfoDot({ text }: { text: string }) {
  return (
    <span className="info-dot" tabIndex={0}>
      i
      <span className="info-popover">{text}</span>
    </span>
  );
}

function MetricCard({ label, raw, hint, display, tone, forceText = false, infoText }: { label: string; raw: number | null; hint: string; display: string; tone: Tone; forceText?: boolean; infoText?: string }) {
  const isPercent = display.includes("%");
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-meta">
        <span className="eyebrow metric-title">{label}{infoText ? <InfoDot text={infoText} /> : null}</span>
        <span className={`severity-chip tone-${tone}`}>{toneLabel(tone)}</span>
      </div>
      <strong className="metric-value">{forceText || raw === null || Number.isNaN(raw) ? display : isPercent ? <AnimatedNumber value={raw * 100} decimals={1} suffix="%" /> : <AnimatedNumber value={raw} decimals={label === "Median RT" ? 1 : 2} />}</strong>
      <span className="metric-hint">{hint}</span>
    </article>
  );
}

function SignalBar({ label, value, width, tone }: { label: string; value: string; width: number; tone: Tone }) {
  return (
    <div className={`signal-row tone-${tone}`}>
      <div className="signal-row-top"><span>{label}</span><span>{value}</span></div>
      <div className="signal-track">
        <motion.div className="signal-fill" initial={false} animate={{ scaleX: Math.max(0.06, clamp01(width)) }} transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }} style={{ originX: 0 }} />
      </div>
    </div>
  );
}

function scoreBucket(value: number | null | undefined, high = 0.75, medium = 0.45) {
  const safe = clamp01(value ?? 0);
  if (safe >= high) return "High";
  if (safe >= medium) return "Elevated";
  return "Limited";
}

function primarySignalLabel(interpretation: InterpretationModel) {
  const components = [...interpretation.signal_components].sort((a, b) => (b.share ?? 0) - (a.share ?? 0));
  const top = components[0];
  if (!top) return "Mixed signal";
  if ((top.share ?? 0) < 0.34) return "Mixed signal";
  return top.label;
}

function breadthLabel(value: number | null | undefined) {
  const safe = value ?? 0;
  if (safe >= 75) return "Broad across the match";
  if (safe >= 45) return "Moderately broad";
  return "Mostly narrow";
}

function findDisplayStat(stats: InterpretationModel["match_profile"]["stats"], key: string) {
  return stats.find((item) => item.key === key)?.display_value || "--";
}

function EvidenceChart({ values }: { values: number[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (!values.length) return null;
  const width = 760;
  const height = 270;
  const padLeft = 56;
  const padRight = 34;
  const padTop = 24;
  const padBottom = 38;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-6, max - min);
  const toX = (index: number) => padLeft + (index / Math.max(1, values.length - 1)) * (width - padLeft - padRight);
  const toY = (value: number) => padTop + (1 - (value - min) / span) * (height - padTop - padBottom);
  const yTicks = [min, min + span * 0.25, min + span * 0.5, min + span * 0.75, max];
  const path = values.map((value, index) => `${index === 0 ? "M" : "L"} ${toX(index)} ${toY(value)}`).join(" ");
  const areaPath = `${path} L ${toX(values.length - 1)} ${height - padBottom} L ${toX(0)} ${height - padBottom} Z`;
  return (
    <div className="chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="line-chart" role="img" aria-label="Fast reaction evidence over indexed events">
        <defs>
          <linearGradient id="chartArea" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(235, 233, 255, 0.32)" />
            <stop offset="100%" stopColor="rgba(235, 233, 255, 0.02)" />
          </linearGradient>
        </defs>
        {yTicks.map((tick, idx) => <g key={idx}><line x1={padLeft} x2={width - padRight} y1={toY(tick)} y2={toY(tick)} className="chart-grid-line" /><text x={padLeft - 10} y={toY(tick) + 4} textAnchor="end" className="chart-label">{tick.toFixed(1)}</text></g>)}
        <line x1={padLeft} x2={width - padRight} y1={height - padBottom} y2={height - padBottom} className="chart-axis-line" />
        <line x1={padLeft} x2={padLeft} y1={padTop} y2={height - padBottom} className="chart-axis-line" />
        {values.map((_, idx) => <text key={idx} x={toX(idx)} y={height - 12} textAnchor="middle" className="chart-label">{idx + 1}</text>)}
        <path d={areaPath} className="chart-area" />
        <motion.path d={path} className="chart-series" initial={{ pathLength: 0.2, opacity: 0.5 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 0.85 }} />
        {values.map((value, idx) => <circle key={idx} cx={toX(idx)} cy={toY(value)} r={hovered === idx ? 5 : 3.4} className="chart-point" onMouseEnter={() => setHovered(idx)} onMouseLeave={() => setHovered(null)} />)}
      </svg>
      <div className="chart-meta"><span className="muted small">Event index</span><span className="muted small">{hovered === null ? "Hover nodes for exact values" : `Event ${hovered + 1}: ${values[hovered].toFixed(1)} ticks`}</span></div>
    </div>
  );
}

function HeroModel({ reducedMotion }: { reducedMotion: boolean }) {
  const shards = [
    { id: "s1", x: "18%", y: "22%", size: 78, delay: 0 },
    { id: "s2", x: "54%", y: "14%", size: 92, delay: 0.2 },
    { id: "s3", x: "76%", y: "26%", size: 70, delay: 0.4 },
    { id: "s4", x: "28%", y: "54%", size: 98, delay: 0.1 },
    { id: "s5", x: "58%", y: "48%", size: 86, delay: 0.35 },
    { id: "s6", x: "78%", y: "64%", size: 74, delay: 0.5 },
  ];
  return (
    <div className="hero-model" aria-hidden>
      <div className="hero-model-core" />
      <div className="hero-model-grid" />
      <div className="hero-model-ring hero-model-ring-a" />
      <div className="hero-model-ring hero-model-ring-b" />
      {shards.map((shard, index) => (
        <motion.div
          key={shard.id}
          className="hero-shard"
          style={{ left: shard.x, top: shard.y, width: shard.size, height: shard.size }}
          initial={false}
          animate={
            reducedMotion
              ? { rotate: 8 + index * 9, y: 0 }
              : { rotate: [8 + index * 9, 18 + index * 9, 8 + index * 9], y: [-6, 8, -6] }
          }
          transition={{ duration: 6 + index, repeat: Infinity, ease: "easeInOut", delay: shard.delay }}
        />
      ))}
      {POINTS.slice(0, 9).map((point, index) => (
        <motion.div
          key={`hero-node-${point.id}`}
          className="hero-node"
          style={{ left: `${point.x}%`, top: `${point.y}%` }}
          initial={false}
          animate={reducedMotion ? { opacity: 0.55 } : { opacity: [0.35, 1, 0.4], scale: [1, 1.18, 1] }}
          transition={{ duration: 3 + (index % 4), repeat: Infinity, ease: "easeInOut", delay: index * 0.15 }}
        />
      ))}
    </div>
  );
}

function intensityTone(value: number | null | undefined): Tone {
  const safe = clamp01(value ?? 0);
  if (safe >= 0.76) return "critical";
  if (safe >= 0.58) return "warning";
  if (safe >= 0.38) return "elevated";
  if (safe >= 0.18) return "good";
  return "neutral";
}

function SignalMixChart({ components }: { components: SignalComponent[] }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const total = Math.max(components.reduce((sum, item) => sum + Math.max(0, item.share || 0), 0), 1e-6);
  const radius = 92;
  const center = 118;
  let angle = -Math.PI / 2;
  const tones: Tone[] = ["critical", "warning", "elevated", "cool", "good"];
  return (
    <div className="signal-mix-chart">
      <svg viewBox="0 0 236 236" className="signal-mix-svg" aria-label="Signal composition chart">
        <circle cx={center} cy={center} r={radius + 12} className="signal-mix-backdrop" />
        <circle cx={center} cy={center} r={radius} className="signal-mix-track" />
        {components.map((component, index) => {
          const share = Math.max(0, component.share || 0) / total;
          const start = angle;
          const end = angle + share * Math.PI * 2;
          angle = end;
          const largeArc = end - start > Math.PI ? 1 : 0;
          const x1 = center + Math.cos(start) * radius;
          const y1 = center + Math.sin(start) * radius;
          const x2 = center + Math.cos(end) * radius;
          const y2 = center + Math.sin(end) * radius;
          const tone = tones[index % tones.length];
          const active = hovered === component.key;
          const path = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
          return (
            <motion.path
              key={component.key}
              d={path}
              className={`signal-mix-arc tone-${tone}${active ? " active" : ""}`}
              initial={{ pathLength: 0, opacity: 0.4 }}
              animate={{ pathLength: 1, opacity: active ? 1 : 0.92 }}
              transition={{ duration: 0.7, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
              onMouseEnter={() => setHovered(component.key)}
              onMouseLeave={() => setHovered(null)}
            />
          );
        })}
        <circle cx={center} cy={center} r={56} className="signal-mix-core" />
      </svg>
      <div className="signal-mix-center">
        <span className="eyebrow">Signal mix</span>
        <strong>{hovered ? components.find((item) => item.key === hovered)?.label : "Behavioral shape"}</strong>
        <p>{hovered ? components.find((item) => item.key === hovered)?.summary : "Hover any lane to inspect which evidence family is carrying the player upward."}</p>
      </div>
      <div className="signal-mix-legend">
        {components.map((component, index) => {
          const tone = tones[index % tones.length];
          return (
            <button
              key={component.key}
              type="button"
              className={`signal-mix-legend-row tone-${tone}${hovered === component.key ? " active" : ""}`}
              onMouseEnter={() => setHovered(component.key)}
              onMouseLeave={() => setHovered(null)}
            >
              <span>{component.label}</span>
              <strong>{Math.round((component.share || 0) * 100)}%</strong>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function LobbySignalScatter({
  players,
  selectedSteamid,
}: {
  players: PlayerRow[];
  selectedSteamid: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const width = 620;
  const height = 320;
  const padX = 52;
  const padTop = 24;
  const padBottom = 42;
  const selected = players.find((player) => player.steamid === selectedSteamid) || players[0] || null;
  const points = players.map((player, index) => {
    const interpretation = player.interpretation;
    const x = clamp01((player.risk ?? player.proba_cheater_infer) * 0.52 + (1 - clamp01(interpretation?.context_fit ?? 0.65)) * 0.48);
    const y = clamp01((interpretation?.global_process_anomaly ?? player.features_summary.prefire_rate ?? 0) * 0.58 + (player.features_summary.headshot_rate ?? 0) * 0.42);
    const depth = clamp01(player.confidence ?? 0.3);
    const tone = signalTone(player.risk ?? player.proba_cheater_infer);
    return {
      id: player.steamid,
      label: player.attacker_name,
      x: padX + x * (width - padX * 2),
      y: padTop + (1 - y) * (height - padTop - padBottom),
      depth,
      signal: scoreDisplay(player.risk ?? player.proba_cheater_infer),
      tone,
      rank: index + 1,
    };
  });
  const hoveredPoint = points.find((point) => point.id === hovered) || points.find((point) => point.id === selected?.steamid) || null;
  return (
    <div className="scatter-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="scatter-chart" aria-label="Lobby signal scatterplot">
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <g key={ratio}>
            <line x1={padX} x2={width - padX} y1={padTop + ratio * (height - padTop - padBottom)} y2={padTop + ratio * (height - padTop - padBottom)} className="chart-grid-line" />
            <line x1={padX + ratio * (width - padX * 2)} x2={padX + ratio * (width - padX * 2)} y1={padTop} y2={height - padBottom} className="chart-grid-line" />
          </g>
        ))}
        <line x1={padX} x2={width - padX} y1={height - padBottom} y2={height - padBottom} className="chart-axis-line" />
        <line x1={padX} x2={padX} y1={padTop} y2={height - padBottom} className="chart-axis-line" />
        <text x={padX} y={18} className="chart-label">Higher process abnormality + precision</text>
        <text x={width - padX} y={height - 10} textAnchor="end" className="chart-label">Lower normal context explanation</text>
        <text x={padX} y={height - 10} className="chart-label">Ordinary</text>
        {points.map((point, index) => (
          <motion.g
            key={point.id}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: hovered === point.id || point.id === selectedSteamid ? 1.12 : 0.92 + point.depth * 0.3 }}
            transition={{ duration: 0.4, delay: index * 0.02 }}
            onMouseEnter={() => setHovered(point.id)}
            onMouseLeave={() => setHovered(null)}
          >
            <circle cx={point.x} cy={point.y} r={8 + point.depth * 9} className={`scatter-glow tone-${point.tone}`} />
            <circle cx={point.x} cy={point.y} r={3.8 + point.depth * 4.4} className={`scatter-point tone-${point.tone}${point.id === selectedSteamid ? " selected" : ""}`} />
          </motion.g>
        ))}
      </svg>
      <div className="scatter-footer">
        {hoveredPoint ? (
          <div className={`scatter-tooltip tone-${hoveredPoint.tone}`}>
            <span className="eyebrow">Lobby signal space</span>
            <strong>{hoveredPoint.label}</strong>
            <p>Rank #{hoveredPoint.rank} | Signal {hoveredPoint.signal} | Confidence depth {Math.round((players.find((item) => item.steamid === hoveredPoint.id)?.confidence ?? 0) * 100)}%</p>
          </div>
        ) : (
          <div className="scatter-tooltip">
            <span className="eyebrow">Lobby signal space</span>
            <strong>Hover a player</strong>
            <p>Points further up and right are harder for ordinary match context to explain away.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricBarMatrix({
  title,
  subtitle,
  items,
}: {
  title: string;
  subtitle: string;
  items: InterpretationMetric[];
}) {
  return (
    <article className="glass-card console-panel">
      <div className="section-heading compact">
        <div>
          <span className="eyebrow">{title}</span>
          <h3>{subtitle}</h3>
        </div>
      </div>
      <div className="metric-bar-grid">
        {items.map((item) => {
          const value = safeMaybeNumber(item.value);
          const tone = metricTone(item.key, value);
          return (
            <div key={item.key} className={`metric-bar-card tone-${tone}`}>
              <div className="metric-bar-head">
                <span>{item.label}</span>
                <strong>{item.display_value || formatSignalValue(item.key, value)}</strong>
              </div>
              <div className="metric-bar-track">
                <motion.div
                  className="metric-bar-fill"
                  initial={{ scaleX: 0.08, opacity: 0.3 }}
                  animate={{ scaleX: Math.max(0.08, normalizedSignalWidth(item.key, value)), opacity: 1 }}
                  transition={{ duration: 0.72, ease: [0.22, 1, 0.36, 1] }}
                  style={{ originX: 0 }}
                />
              </div>
              <p>{item.summary}</p>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function scaledSignalScore(value: number | null | undefined) {
  const rawScore = clamp01(value ?? 0) * 100;
  const first = SIGNAL_SCALE_ANCHORS[0];
  const last = SIGNAL_SCALE_ANCHORS[SIGNAL_SCALE_ANCHORS.length - 1];
  if (rawScore <= first.raw) return first.display;
  if (rawScore >= last.raw) return last.display;
  for (let index = 1; index < SIGNAL_SCALE_ANCHORS.length; index += 1) {
    const left = SIGNAL_SCALE_ANCHORS[index - 1];
    const right = SIGNAL_SCALE_ANCHORS[index];
    if (rawScore <= right.raw) {
      const span = Math.max(1e-6, right.raw - left.raw);
      const t = (rawScore - left.raw) / span;
      return left.display + (right.display - left.display) * t;
    }
  }
  return last.display;
}

function signalTone(value: number | null | undefined): Tone {
  const score = scaledSignalScore(value);
  if (score >= 60) return "critical";
  if (score >= 26) return "warning";
  if (score >= 11) return "elevated";
  return "good";
}

function supportTone(value: number | null | undefined): Tone {
  const safe = clamp01(value ?? 0);
  if (safe >= 0.75) return "good";
  if (safe >= 0.45) return "elevated";
  if (safe >= 0.25) return "warning";
  return "critical";
}

function invertedTone(value: number | null | undefined): Tone {
  return intensityTone(1 - clamp01(value ?? 0));
}

function explanationTone(status: string): Tone {
  const normalized = status.toLowerCase();
  if (["high", "strong"].includes(normalized)) return "warning";
  if (["partial", "plausible"].includes(normalized)) return "elevated";
  if (["mixed"].includes(normalized)) return "neutral";
  return "good";
}

function interpretationOrFallback(player: PlayerRow | null, report: ExplainReport | null): InterpretationModel | null {
  return report?.interpretation || player?.interpretation || null;
}

function scoreDisplay(value: number | null | undefined) {
  return `${Math.round(scaledSignalScore(value))}`;
}

function triageLabel(
  value: number | null | undefined,
  rank?: number,
  total?: number,
  contextFit?: number | null | undefined,
  support?: number | null | undefined,
  process?: number | null | undefined
) {
  const safe = scaledSignalScore(value);
  const safeRank = rank ?? 999;
  const safeTotal = Math.max(total ?? 1, 1);
  const topSlice = safeRank / safeTotal;
  const weakContext = clamp01(contextFit ?? 1) < 0.4;
  const strongSupport = clamp01(support ?? 0) >= 0.75;
  const strongProcess = clamp01(process ?? 0) >= 0.35;

  if (safe >= 70) return "Strong review";
  if (safe >= 40) return "Needs review";
  if ((safeRank === 1 || topSlice <= 0.2) && weakContext && strongSupport && strongProcess) return "Needs review";
  if (safe >= 20) return "Light watch";
  if ((safeRank === 1 || topSlice <= 0.2) && weakContext && strongSupport) return "Light watch";
  return "Typical range";
}

function contextLabel(value: number | null | undefined) {
  const safe = clamp01(value ?? 0);
  if (safe >= 0.7) return "Mostly explained";
  if (safe >= 0.4) return "Partly explained";
  return "Poorly explained";
}

function supportLabel(value: number | null | undefined) {
  const safe = clamp01(value ?? 0);
  if (safe >= 0.75) return "Stable signal";
  if (safe >= 0.45) return "Some support";
  return "Thin support";
}

function primarySummaryLine(
  overallRisk: number | null | undefined,
  process: number | null | undefined,
  contextFit: number | null | undefined,
  rank?: number,
  total?: number,
  support?: number | null | undefined
) {
  const risk = scaledSignalScore(overallRisk);
  const processScore = clamp01(process ?? 0);
  const context = clamp01(contextFit ?? 0);
  const safeRank = rank ?? 999;
  const safeTotal = Math.max(total ?? 1, 1);
  const topSlice = safeRank / safeTotal;
  const stable = clamp01(support ?? 0) >= 0.75;
  if (risk < 20 && processScore < 0.25) return "This player sits inside the typical range we have seen on held-out legit matches.";
  if (risk >= 70 && context < 0.35) return "This player stands out strongly and the match context does not explain much of it.";
  if (processScore >= 0.55 && context < 0.35) return "The main concern is unusually strong process signal that normal context does not explain well.";
  if ((safeRank === 1 || topSlice <= 0.2) && context < 0.35 && stable) return "This player is one of the strongest standouts in the match, but the absolute model score is still moderate rather than decisive.";
  if (context >= 0.6) return "There is some signal here, but ordinary match context explains a meaningful share of it.";
  return "This player stands out enough to review, but the case is not clean-cut from the model alone.";
}

function traceFocusMetrics(scoreTrace: ScoreTrace | null) {
  const row = scoreTrace?.feature_row || {};
  const candidates: Array<{ label: string; key: string; value: number | null; hint: string; toneKey?: string }> = [
    { label: FEATURE_COPY.aim_process_global_score.label, key: "aim_process_global_score", value: safeMaybeNumber(row.aim_process_global_score), hint: FEATURE_COPY.aim_process_global_score.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enn_score_mean.label, key: "enn_score_mean", value: safeMaybeNumber(row.enn_score_mean), hint: FEATURE_COPY.enn_score_mean.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enn_low_vis_mean.label, key: "enn_low_vis_mean", value: safeMaybeNumber(row.enn_low_vis_mean), hint: FEATURE_COPY.enn_low_vis_mean.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enn_hard_mean.label, key: "enn_hard_mean", value: safeMaybeNumber(row.enn_hard_mean), hint: FEATURE_COPY.enn_hard_mean.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enn_score_top3_mean.label, key: "enn_score_top3_mean", value: safeMaybeNumber(row.enn_score_top3_mean), hint: FEATURE_COPY.enn_score_top3_mean.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_precision_under_difficulty.label, key: "enc_precision_under_difficulty", value: safeMaybeNumber(row.enc_precision_under_difficulty), hint: FEATURE_COPY.enc_precision_under_difficulty.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_process_abnormality.label, key: "enc_process_abnormality", value: safeMaybeNumber(row.enc_process_abnormality), hint: FEATURE_COPY.enc_process_abnormality.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_acquire_shot_lag_p90.label, key: "enc_acquire_shot_lag_p90", value: safeMaybeNumber(row.enc_acquire_shot_lag_p90), hint: FEATURE_COPY.enc_acquire_shot_lag_p90.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_aim_dwell_mean.label, key: "enc_aim_dwell_mean", value: safeMaybeNumber(row.enc_aim_dwell_mean), hint: FEATURE_COPY.enc_aim_dwell_mean.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_damage_end_rate.label, key: "enc_damage_end_rate", value: safeMaybeNumber(row.enc_damage_end_rate), hint: FEATURE_COPY.enc_damage_end_rate.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_ttdmg_high_rate.label, key: "enc_ttdmg_high_rate", value: safeMaybeNumber(row.enc_ttdmg_high_rate), hint: FEATURE_COPY.enc_ttdmg_high_rate.summary, toneKey: "risk" },
    { label: FEATURE_COPY.enc_mouse_burst_mean.label, key: "enc_mouse_burst_mean", value: safeMaybeNumber(row.enc_mouse_burst_mean), hint: FEATURE_COPY.enc_mouse_burst_mean.summary },
  ];
  return candidates.filter((item) => item.value !== null).slice(0, 8);
}

function ScorePill({ label, value, tone, hint }: { label: string; value: number | null | undefined; tone: Tone; hint: string }) {
  return (
    <article className={`score-pill tone-${tone}`}>
      <span className="eyebrow">{label}</span>
      <strong>{scoreDisplay(value)}</strong>
      <span className="muted small">{hint}</span>
    </article>
  );
}

function SignalLegend() {
  const items: Array<{ label: string; range: string; tone: Tone }> = [
    { range: "0-10", label: "Typical", tone: "good" },
    { range: "11-25", label: "Watch", tone: "elevated" },
    { range: "26-59", label: "Review", tone: "warning" },
    { range: "60-100", label: "Strong", tone: "critical" },
  ];
  return (
    <div className="signal-legend" aria-label="Signal scale guide">
      {items.map((item) => (
        <span key={item.range} className={`signal-legend-chip tone-${item.tone}`}>
          <strong>{item.range}</strong>
          <em>{item.label}</em>
        </span>
      ))}
    </div>
  );
}

function GuideOverlay({
  open,
  doNotShowAgain,
  onToggleDoNotShowAgain,
  onClose,
}: {
  open: boolean;
  doNotShowAgain: boolean;
  onToggleDoNotShowAgain: (checked: boolean) => void;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <AnimatePresence>
      <motion.div
        className="guide-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.38 }}
      >
        <motion.div
          className="guide-overlay-panel shell-card"
          initial={{ opacity: 0, scale: 1.04, filter: "blur(18px)" }}
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, scale: 0.98, filter: "blur(18px)" }}
          transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="guide-overlay-hero" aria-hidden>
            <div className="guide-overlay-hero-image" />
            <div className="guide-overlay-hero-scrim" />
            <div className="guide-overlay-hero-copy">
              <span className="eyebrow">NullCS beta notice</span>
              <strong>Local demo review, not anti-cheat enforcement.</strong>
            </div>
          </div>
          <div className="guide-overlay-head">
            <div>
              <h2>NullCS is still in beta</h2>
              <p>NullCS is a local Counter-Strike demo review tool that ranks match-relative behavioral standouts and produces evidence for review. It is not an anti-cheat or ban system.</p>
            </div>
            <button className="button button-secondary" onClick={onClose}>Continue</button>
          </div>
          <div className="guide-overlay-scroll">
            <section className="guide-block">
              <h3>What it does</h3>
              <p>It parses a demo, builds behavioral features, scores the lobby, and shows which players deserve manual review first.</p>
              <p>The model and interface are still being trained, benchmarked, and polished, so wording and thresholds can change between beta builds.</p>
            </section>
            <section className="guide-block">
              <h3>Severity tiers</h3>
              <div className="guide-bullet-list">
                <span><strong>Typical</strong> means the player is within the expected range for the current match.</span>
                <span><strong>Watch</strong> means the player is unusual enough to keep in view, but the signal is not suspicious by itself.</span>
                <span><strong>Review</strong> means signals are starting to align with irregular play patterns and should be checked with round context, POV, and supporting evidence.</span>
                <span><strong>Strong</strong> means numerous signals are elevated at once and the case should be reviewed before lower-priority players.</span>
              </div>
            </section>
            <section className="guide-block">
              <h3>How to read values</h3>
              <p>Signal is review priority inside one match. Support is how much usable evidence the match contains for that player. Process metrics summarize aim, input, timing, visibility, and shot behavior.</p>
              <div className="guide-bullet-list">
                <span>Higher signal means review sooner, not that the case is settled.</span>
                <span>Low support should make the read more cautious.</span>
                <span>Colors mark benchmark severity, not a final verdict.</span>
              </div>
            </section>
            <section className="guide-block">
              <h3>What it is not</h3>
              <div className="guide-bullet-list">
                <span>It is not VAC, server-side enforcement, or an accusation generator.</span>
                <span>It does not replace watching the demo or checking external match context.</span>
                <span>It should not be used to make account-level claims from one match.</span>
              </div>
            </section>
          </div>
          <div className="guide-overlay-foot">
            <label className="toggle-chip">
              <input type="checkbox" checked={doNotShowAgain} onChange={(e) => onToggleDoNotShowAgain(e.target.checked)} />
              <span>Do not show this beta notice again</span>
            </label>
            <button className="button button-primary" onClick={onClose}>I understand</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function StatChip({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className={`stat-chip tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

type PersistedSession = {
  stage?: Stage;
  demoId?: string;
  displayName?: string;
  selectedSteamid?: string;
  playerVizTab?: PlayerVizTab;
  reportTab?: ReportTab;
};

function readPersistedSession(): PersistedSession {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) as PersistedSession : {};
  } catch {
    return {};
  }
}

function App() {
  const persistedSession = useMemo(readPersistedSession, []);
  const [stage, setStage] = useState<Stage>("home");
  const [demoId, setDemoId] = useState(persistedSession.demoId || "");
  const [caseLabel, setCaseLabel] = useState("");
  const [displayName, setDisplayName] = useState(persistedSession.displayName || "");
  const [file, setFile] = useState<File | null>(null);
  const [desktopDemoPath, setDesktopDemoPath] = useState("");
  const [bundleFile, setBundleFile] = useState<File | null>(null);
  const [activeBundle, setActiveBundle] = useState<ReviewBundle | null>(null);
  const [status, setStatus] = useState<DemoStatus>({ demo_id: "", state: "queued", logs_tail: "", error: "" });
  const [players, setPlayers] = useState<PlayerRow[]>([]);
  const [selectedSteamid, setSelectedSteamid] = useState(persistedSession.selectedSteamid || "");
  const [scoreTrace, setScoreTrace] = useState<ScoreTrace | null>(null);
  const [report, setReport] = useState<ExplainReport | null>(null);
  const [evidenceTables, setEvidenceTables] = useState<Record<string, EvidenceTable>>({});
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [reportTab, setReportTab] = useState<ReportTab>(persistedSession.reportTab === "reasons" ? "reasons" : "overview");
  const [playerVizTab, setPlayerVizTab] = useState<PlayerVizTab>(persistedSession.playerVizTab || "signal");
  const [guideDismissed, setGuideDismissed] = useState(() => window.localStorage.getItem(BETA_NOTICE_KEY) === "1");
  const [guideOpen, setGuideOpen] = useState(() => window.localStorage.getItem(BETA_NOTICE_KEY) !== "1");
  const [error, setError] = useState("");
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [desktopStatus, setDesktopStatus] = useState<DesktopServiceStatus | null>(null);
  const [desktopStarting, setDesktopStarting] = useState(false);
  const [launchSequenceVisible, setLaunchSequenceVisible] = useState(false);
  const [launchRevealActive, setLaunchRevealActive] = useState(false);
  const [launchRevealNonce, setLaunchRevealNonce] = useState(0);
  const bundleInputRef = useRef<HTMLInputElement | null>(null);
  const demoInputRef = useRef<HTMLInputElement | null>(null);
  const ambientAudioRef = useRef<HTMLAudioElement | null>(null);
  const launchRevealTimerRef = useRef<number | null>(null);
  const desktopAutoStartAttemptedRef = useRef(false);
  const [musicEnabled, setMusicEnabled] = useState(() => {
    const stored = window.localStorage.getItem("nullcs_music_enabled");
    return stored === "1";
  });
  const [reducedMotion, setReducedMotion] = useState(() => {
    const stored = window.localStorage.getItem("nullcs_reduced_motion");
    if (stored === "1") return true;
    if (stored === "0") return false;
    return detectLowPowerDefault() || isDesktopShell();
  });

  useEffect(() => {
    void (async () => {
      let desktop = false;
      let initialDesktopStatus: DesktopServiceStatus | null = null;
      try {
        desktop = isDesktopShell();
        const status = await getDesktopServiceStatus();
        if (status) {
          desktop = true;
          initialDesktopStatus = status;
          setDesktopStatus(status);
          setApiBaseUrl(status.api_base_url);
          setApiAccessToken(status.api_key);
        } else if (desktop) {
          setDesktopStatus({
            is_desktop: true,
            api_base_url: "http://127.0.0.1:8011/api",
            api_key: "",
            running: false,
            healthy: false,
            can_start: false,
            launched_by_app: false,
            error: "Desktop bridge did not return a runtime status.",
          });
        }
      } catch (err) {
          setDesktopStatus({
            is_desktop: true,
            api_base_url: "http://127.0.0.1:8011/api",
            api_key: "",
            running: false,
            healthy: false,
            can_start: false,
          launched_by_app: false,
          error: String(err),
        });
      }

      try {
        if (desktop && initialDesktopStatus && !initialDesktopStatus.healthy) {
          setBackendAvailable(false);
          return;
        }
        setBackendHealth(await getHealth());
        setBackendAvailable(true);
      } catch {
        setBackendAvailable(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!desktopStatus?.is_desktop || (!desktopStarting && (desktopStatus.healthy || !desktopStatus.running))) {
      return;
    }

    let cancelled = false;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      void (async () => {
          try {
            const status = await getDesktopServiceStatus();
            if (!status || cancelled) return;
            setDesktopStatus(status);
            setApiBaseUrl(status.api_base_url);
            setApiAccessToken(status.api_key);
            if (status.healthy) {
              const health = await getHealth();
            if (cancelled) return;
            setBackendHealth(health);
            setBackendAvailable(true);
            setDesktopStarting(false);
            window.clearInterval(timer);
            return;
          }
          if (Date.now() - startedAt > 20000 || status.error) {
            setDesktopStarting(false);
            setBackendAvailable(false);
            if (status.error) setError(status.error);
            window.clearInterval(timer);
          }
        } catch (err) {
          if (cancelled) return;
          setDesktopStarting(false);
          setBackendAvailable(false);
          setError(userErrorMessage(err));
          window.clearInterval(timer);
        }
      })();
    }, 900);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [desktopStarting, desktopStatus]);

  useEffect(() => {
    if (!desktopStatus?.is_desktop || !desktopStatus.healthy || backendAvailable === true) {
      return;
    }

    let cancelled = false;
    let timer = 0;
    const syncHealth = () => {
      void (async () => {
        try {
          const { ready } = await refreshBackendReadiness();
          if (cancelled || !ready) return;
          setError("");
          window.clearInterval(timer);
        } catch {
          if (cancelled) return;
          setBackendAvailable(false);
        }
      })();
    };

    syncHealth();
    timer = window.setInterval(syncHealth, 1200);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [backendAvailable, desktopStatus]);

  useEffect(() => {
    if (!desktopStatus?.is_desktop || desktopStatus.healthy || !desktopStatus.can_start || desktopStarting || desktopAutoStartAttemptedRef.current) {
      return;
    }
    desktopAutoStartAttemptedRef.current = true;
    void connectLocalReviewEngine();
  }, [desktopStarting, desktopStatus]);

  useEffect(() => {
    window.localStorage.setItem("nullcs_music_enabled", musicEnabled ? "1" : "0");
    const audio = ambientAudioRef.current;
    if (!audio) return;
    if (!musicEnabled) {
      audio.pause();
      return;
    }
    if (!launchSequenceVisible && audio.paused) {
      void audio.play().catch(() => {});
    }
  }, [launchSequenceVisible, musicEnabled]);

  useEffect(() => {
    window.localStorage.setItem("nullcs_reduced_motion", reducedMotion ? "1" : "0");
    document.documentElement.dataset.motion = reducedMotion ? "reduced" : "full";
  }, [reducedMotion]);

  useEffect(() => {
    if (guideDismissed) {
      window.localStorage.setItem(BETA_NOTICE_KEY, "1");
    } else {
      window.localStorage.removeItem(BETA_NOTICE_KEY);
    }
  }, [guideDismissed]);

  useEffect(() => {
    const payload: PersistedSession = {
      stage,
      demoId,
      displayName,
      selectedSteamid,
      playerVizTab,
      reportTab,
    };
    try {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    } catch {
      // Session restore is best-effort only.
    }
  }, [stage, demoId, displayName, selectedSteamid, playerVizTab, reportTab]);

  useEffect(() => {
    if (!demoId || players.length || activeBundle) return;
    let cancelled = false;
    void (async () => {
      try {
        const next = await getStatus(demoId);
        if (cancelled) return;
        setStatus(next);
        if (next.original_filename) setDisplayName(next.original_filename);
        if (next.state === "done") {
          const loaded = ((await getPlayers(demoId)).players || []).map(normalizePlayer);
          if (cancelled) return;
          setPlayers(loaded);
          const steamid = selectedSteamid || loaded[0]?.steamid || "";
          setSelectedSteamid(steamid);
          if (stage === "processing") setStage("results");
          if (steamid) void selectPlayer(steamid, loaded);
        } else if (next.state && next.state !== "error" && stage !== "processing") {
          setStage("processing");
        }
      } catch {
        // A stale saved demo id should not block the intake surface.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeBundle, demoId, players.length]);

  useEffect(() => () => {
    if (launchRevealTimerRef.current !== null) {
      window.clearTimeout(launchRevealTimerRef.current);
    }
    if (ambientAudioRef.current) {
      ambientAudioRef.current.pause();
    }
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    let frame = 0;
    const update = (event: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const x = (event.clientX / window.innerWidth - 0.5) * 2;
        const y = (event.clientY / window.innerHeight - 0.5) * 2;
        document.documentElement.style.setProperty("--pointer-x", x.toFixed(4));
        document.documentElement.style.setProperty("--pointer-y", y.toFixed(4));
      });
    };
    window.addEventListener("pointermove", update, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", update);
    };
  }, [reducedMotion]);

  useEffect(() => {
    if (stage !== "processing" || !demoId) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStatus(demoId);
        if (cancelled) return;
        setStatus(next);
        if (next.original_filename) setDisplayName(next.original_filename);
        if (next.state === "done") {
          const loaded = ((await getPlayers(demoId)).players || []).map(normalizePlayer);
          if (cancelled) return;
          startTransition(() => {
            setPlayers(loaded);
            setStage("results");
          });
          if (loaded[0]) void selectPlayer(loaded[0].steamid, loaded);
        }
        if (next.state === "error") {
          setError(next.error || "Analysis failed.");
          setStage("home");
        }
      } catch (err) {
        const message = String(err);
        if (/429|rate limit/i.test(message)) return;
        setError(message);
        setStage("home");
      }
    }, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [stage, demoId]);

  const publicUploadAvailable = backendAvailable === true && !!backendHealth?.upload_enabled && backendHealth?.mode !== "demo";
  const filteredPlayers = useMemo(
    () =>
      [...players]
        .filter((p) => safeText(p.attacker_name, "Unknown player").toLowerCase().includes(deferredQuery.toLowerCase()) || safeText(p.steamid).includes(deferredQuery))
        .sort((a, b) => safeNumber(b.interpretation?.review_priority ?? b.risk ?? b.proba_cheater_infer, 0) - safeNumber(a.interpretation?.review_priority ?? a.risk ?? a.proba_cheater_infer, 0)),
    [players, deferredQuery]
  );
  const selectedPlayer = useMemo(() => players.find((p) => p.steamid === selectedSteamid) || filteredPlayers[0] || null, [players, filteredPlayers, selectedSteamid]);
  const selectedRank = useMemo(() => {
    if (!selectedPlayer) return 1;
    const idx = filteredPlayers.findIndex((p) => p.steamid === selectedPlayer.steamid);
    return idx >= 0 ? idx + 1 : 1;
  }, [filteredPlayers, selectedPlayer]);
  const selectedPriority = useMemo(() => reviewPriority(selectedPlayer?.risk, selectedRank, filteredPlayers.length || players.length || 1), [selectedPlayer, selectedRank, filteredPlayers.length, players.length]);
  const rosterTitle = useMemo(() => displayDemoLabel(demoId, displayName || status.original_filename || file?.name || ""), [demoId, displayName, status.original_filename, file]);
  const sparkValues = useMemo(() => {
    const activeEvidence = evidenceTables["evidence_fast_rt.csv"];
    const evidenceValues = activeEvidence ? activeEvidence.rows.map((row) => Number(row.rt_ticks)).filter((value) => Number.isFinite(value)) : [];
    if (evidenceValues.length) return evidenceValues;
    const row = scoreTrace?.feature_row || {};
    const rtMedian = safeMaybeNumber(row.rt_median) ?? selectedPlayer?.features_summary.rt_median ?? 12;
    const rtP10 = safeMaybeNumber(row.rt_p10) ?? Math.max(1, rtMedian * 0.72);
    const rtMean = safeMaybeNumber(row.rt_mean) ?? Math.max(1, rtMedian * 0.94);
    const rtP90 = safeMaybeNumber(row.rt_p90) ?? Math.max(1.5, rtMedian * 1.18);
    const fast4 = selectedPlayer?.features_summary.long_range_fast_rt_rate_4 ?? 0;
    const prefire = selectedPlayer?.features_summary.prefire_rate ?? 0;
    const reactionFloor = Math.max(1, rtMedian * (1 - 0.34 * fast4));
    const prefireFloor = Math.max(1, rtMedian * (1 - 0.2 * prefire));
    return [rtP90, rtMean, rtMedian, reactionFloor, prefireFloor, rtP10];
  }, [evidenceTables, scoreTrace, selectedPlayer]);
  const featureCount = backendHealth?.model_info?.feature_count ?? 235;
  const productIdentity = backendHealth?.product_info?.identity || DEFAULT_PRODUCT_IDENTITY;
  const productTagline = backendHealth?.product_info?.tagline || DEFAULT_PRODUCT_TAGLINE;
  const productAnalystNote = backendHealth?.product_info?.analyst_note || "Designed to help analysts rank match-relative deviation, judge confidence, and decide the next neutral review step.";
  const selectedConfidenceLabel = confidenceBand(selectedPlayer?.confidence);
  const selectedUncertaintyLabel = uncertaintyNote(selectedPlayer?.confidence, selectedPlayer?.ci_low, selectedPlayer?.ci_high);
  const selectedAction = analystAction(selectedPriority, selectedPlayer?.confidence);
  const selectedInterpretation = useMemo(() => interpretationOrFallback(selectedPlayer, null), [selectedPlayer]);
  const reportConfidenceValue = report?.confidence.score ?? selectedPlayer?.confidence ?? null;
  const reportUncertaintyLabel = uncertaintyNote(reportConfidenceValue, report?.uncertainty_ci?.risk_p05 ?? selectedPlayer?.ci_low, report?.uncertainty_ci?.risk_p95 ?? selectedPlayer?.ci_high);
  const reportAction = analystAction(selectedPriority, reportConfidenceValue);
  const reportInterpretation = useMemo(() => interpretationOrFallback(selectedPlayer, report), [selectedPlayer, report]);
  const heroStats = useMemo(() => [
    { label: "Behavioral signals", value: `${featureCount}+`, note: "per-player indicators interpreted inside one match review" },
    { label: "Review lens", value: "Process + context", note: "timing, visibility, movement pressure, and encounter shape" },
    { label: "Analyst handoff", value: "Reports + traces", note: "fast reads, ranked rosters, and saved review artifacts" },
  ], [featureCount]);

  function applyReviewBundle(bundle: ReviewBundle) {
    const normalizedPlayers = bundle.players.map(normalizePlayer);
    const firstSteamid = normalizedPlayers[0]?.steamid || "";
    setActiveBundle(bundle);
    setDemoId(bundle.meta.demo_id);
    setDisplayName(bundle.meta.display_name);
    setPlayers(normalizedPlayers);
    setSelectedSteamid(firstSteamid);
    setScoreTrace(firstSteamid ? bundle.score_traces[firstSteamid] || null : null);
    setReport(firstSteamid ? bundle.reports[firstSteamid] || null : null);
    setEvidenceTables(firstSteamid ? bundle.evidence_tables[firstSteamid] || {} : {});
    setStatus({ demo_id: bundle.meta.demo_id, state: "done", logs_tail: "", error: "" });
    setReportTab("overview");
    setQuery("");
    setStage("results");
  }

  async function selectPlayer(steamid: string, sourcePlayers = players) {
    setSelectedSteamid(steamid);
    const player = sourcePlayers.find((p) => p.steamid === steamid);
    if (!player) return;
    if (activeBundle) {
      setScoreTrace(activeBundle.score_traces[steamid] || null);
      if (report?.player.attacker_steamid === steamid) {
        setReport(activeBundle.reports[steamid] || null);
        setEvidenceTables(activeBundle.evidence_tables[steamid] || {});
      }
      return;
    }
    try {
      setScoreTrace((await getPlayerScoreTrace(demoId, steamid)).trace);
    } catch {
      setScoreTrace(null);
    }
  }

  function loadSampleWalkthrough() {
    setError("");
    setBundleFile(null);
    void openBundledSampleReview().then(applyReviewBundle);
  }

  function resetReviewForNewDemo() {
    setActiveBundle(null);
    setDemoId("");
    setCaseLabel("");
    setDisplayName("");
    setPlayers([]);
    setSelectedSteamid("");
    setScoreTrace(null);
    setReport(null);
    setEvidenceTables({});
    setStatus({ demo_id: "", state: "queued", logs_tail: "", error: "" });
    setReportTab("overview");
    setQuery("");
  }

  function selectDemoFile(nextFile: File | null) {
    if (!nextFile) return;
    if (!nextFile.name.toLowerCase().endsWith(".dem")) {
      setError("Only Counter-Strike .dem files are accepted. Videos, screenshots, ZIP files, and scoreboards cannot be analyzed.");
      return;
    }
    const maxBytes = backendHealth?.max_upload_bytes;
    if (maxBytes && nextFile.size > maxBytes) {
      setError(`This demo is ${Math.round(nextFile.size / (1024 * 1024))} MB, above the ${Math.round(maxBytes / (1024 * 1024))} MB desktop beta limit.`);
      return;
    }
    resetReviewForNewDemo();
    setFile(nextFile);
    setDesktopDemoPath("");
    setError("");
  }

  async function refreshBackendReadiness() {
    const health = await getHealth();
    setBackendHealth(health);
    const ready = !!health.upload_enabled && health.mode !== "demo";
    setBackendAvailable(ready);
    if (ready) {
      setError("");
    }
    return { health, ready };
  }

  async function syncDesktopRuntimeStatus() {
    const status = await getDesktopServiceStatus();
    if (status) {
      setDesktopStatus(status);
      setApiBaseUrl(status.api_base_url);
      setApiAccessToken(status.api_key);
    }
    return status;
  }

  async function ensureDesktopUploadReady() {
    let status = desktopStatus;

    if (status?.is_desktop) {
      try {
        status = (await syncDesktopRuntimeStatus()) ?? status;
      } catch {
        // Fall through to the last known desktop state below.
      }
    }

    if (status?.healthy) {
      const { ready } = await refreshBackendReadiness();
      if (ready) return true;
    }

    if (!status?.is_desktop) {
      setError("Live uploads are not available in this shell.");
      return false;
    }

    if (!status.can_start) {
      setError("The desktop app could not find a local NullCS workspace to start the review engine.");
      return false;
    }

    setError("");
    setDesktopStarting(true);
    try {
      const started = await startDesktopService();
      if (started) {
        setDesktopStatus(started);
        setApiBaseUrl(started.api_base_url);
        setApiAccessToken(started.api_key);
        status = started;
      }

      const startedAt = Date.now();
      while (Date.now() - startedAt < 20000) {
        if (status?.healthy) {
          const { ready } = await refreshBackendReadiness();
          if (ready) {
            setError("");
            return true;
          }
        }

        await new Promise((resolve) => window.setTimeout(resolve, 900));
        status = (await syncDesktopRuntimeStatus()) ?? status;
        if (status?.error) {
          setError(status.error);
          return false;
        }
      }

      setError("The local review engine started, but the analysis API did not become upload-ready in time.");
      return false;
    } catch (err) {
      setError(userErrorMessage(err));
      return false;
    } finally {
      setDesktopStarting(false);
    }
  }

  function openBundlePicker() {
    setError("");
    bundleInputRef.current?.click();
  }

  async function openDemoPicker() {
    if (desktopStatus?.is_desktop) {
      const ready = await ensureDesktopUploadReady();
      if (!ready) return;
      const path = await pickDesktopDemoFile();
      if (!path) return;
      resetReviewForNewDemo();
      setDesktopDemoPath(path);
      setFile(null);
      setError("");
      return;
    }
    if (publicUploadAvailable) {
      setError("");
      demoInputRef.current?.click();
      return;
    }
    try {
      const ready = await ensureDesktopUploadReady();
      if (!ready) return;
      demoInputRef.current?.click();
    } catch (err) {
      setError(userErrorMessage(err));
    }
  }

  function handleDemoDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setError("");
    const files = Array.from(event.dataTransfer.files || []);
    const dropped = files.find((item) => item.name.toLowerCase().endsWith(".dem"));
    if (!dropped) {
      setError(files.length ? "Only Counter-Strike .dem files are accepted. Drop one demo file to start a review." : "Drop a .dem file to start a review.");
      return;
    }
    selectDemoFile(dropped);
  }

  async function connectLocalReviewEngine() {
    let serviceHealthy = false;
    try {
      setError("");
      setDesktopStarting(true);
        const status = await startDesktopService();
        if (status) {
          setDesktopStatus(status);
          setApiBaseUrl(status.api_base_url);
          setApiAccessToken(status.api_key);
          if (status.error) {
            setError(status.error);
          }
        if (status.healthy) {
          serviceHealthy = true;
          await refreshBackendReadiness();
          setDesktopStarting(false);
          return;
        }
      }
      setBackendAvailable(false);
    } catch (err) {
      setError(userErrorMessage(err));
      setBackendAvailable(false);
    } finally {
      if (serviceHealthy) {
        setDesktopStarting(false);
      }
    }
  }

  async function importReviewBundle() {
    try {
      if (!bundleFile) return;
      setError("");
      applyReviewBundle(await openImportedReviewBundle(bundleFile));
    } catch (err) {
      setError(userErrorMessage(err));
    }
  }

  async function onUploadAndRun() {
    try {
      if (!file && !desktopDemoPath) return;
      if (!publicUploadAvailable) throw new Error("Live uploads are disabled on this deployment.");
      setError("");
      setActiveBundle(null);
      setPlayers([]);
      setSelectedSteamid("");
      setScoreTrace(null);
      setReport(null);
      setEvidenceTables({});
      let nextDemoId = "";
      let originalFilename = "";
      const requestedDemoId = caseLabel.trim() || undefined;
      if (desktopStatus?.is_desktop && desktopDemoPath) {
        if (!desktopDemoPath.toLowerCase().endsWith(".dem")) throw new Error("Only .dem files are accepted.");
        const queued = await queueLocalDemoPath(desktopDemoPath, requestedDemoId);
        nextDemoId = queued.demo_id;
        originalFilename = queued.original_filename || desktopDemoPath.split(/[\\/]/).pop() || "Selected Demo";
      } else {
        if (!file) throw new Error("Select a .dem file first.");
        if (!file.name.toLowerCase().endsWith(".dem")) throw new Error("Only .dem files are accepted.");
        const uploaded = await uploadDemo(file, requestedDemoId);
        nextDemoId = uploaded.demo_id;
        originalFilename = uploaded.original_filename || file.name;
        await runDemo(nextDemoId);
      }
      setDemoId(nextDemoId);
      setCaseLabel("");
      setDisplayName(originalFilename);
      setStatus({ demo_id: nextDemoId, state: "queued", logs_tail: "", error: "", original_filename: originalFilename, stage_index: 0, stage: "Uploading", steps: PIPELINE_STEPS });
      setStage("processing");
    } catch (err) {
      setError(userErrorMessage(err));
    }
  }

  async function openReport(steamid: string) {
    try {
      setSelectedSteamid(steamid);
      setError("");
      if (activeBundle) {
        setReport(activeBundle.reports[steamid] || null);
        setEvidenceTables(activeBundle.evidence_tables[steamid] || {});
        setStage("report");
        return;
      }
      await explainPlayer(demoId, steamid);
      const nextReport = await getExplainReport(demoId, steamid, "infer", 0);
      const tables = await Promise.all(nextReport.evidence_files.map(async (name) => [name, await getEvidenceTable(demoId, steamid, name, 300)] as const));
      setReport(nextReport);
      setEvidenceTables(Object.fromEntries(tables));
      setStage("report");
    } catch (err) {
      setError(userErrorMessage(err));
    }
  }

  async function openPlayerProfile(url: string) {
    try {
      if (isDesktopShell()) {
        const opened = await openExternalUrl(url);
        if (!opened) setError("Could not open the profile in your default browser.");
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(userErrorMessage(err));
    }
  }

  const renderInterpretationDeck = (
    interpretation: InterpretationModel | null,
    overallRisk: number | null | undefined,
    supportValue: number | null | undefined,
    uncertaintyLabel: string
  ) => {
    if (!interpretation) return null;
    const topComparisons = interpretation.review_lens.comparisons.slice(0, 2);
    const topLimitations = interpretation.limitations.slice(0, 2);
    const totalPlayers = filteredPlayers.length || players.length || 1;
    const rankValue = findDisplayStat(interpretation.match_profile.stats, "rank") || `#${selectedRank}/${totalPlayers}`;
    const primarySignal = primarySignalLabel(interpretation);
    const overallTone = signalTone(overallRisk);
    const triage = triageLabel(overallRisk, selectedRank, totalPlayers, interpretation.context_fit, supportValue, interpretation.global_process_anomaly);
    const nextStep = topComparisons[0] || interpretation.review_lens.title;
    const traceMetrics = traceFocusMetrics(scoreTrace).slice(0, 6);
    const sourceRow = scoreTrace?.feature_row || selectedPlayer?.features_summary || {};
    const focusMetricKeys = [
      "rt_median",
      "prefire_rate",
      "thrusmoke_kill_rate",
      "headshot_rate",
      "enc_acquire_shot_lag_p90",
      "enc_aim_dwell_mean",
    ];
    const focusMetrics = focusMetricKeys
      .map((key) => ({
        key,
        label: FEATURE_COPY[key]?.label || cap(key),
        value: safeMaybeNumber((sourceRow as Record<string, unknown>)[key]),
        summary: FEATURE_COPY[key]?.summary || "Match-facing feature carried into the player view for quick analyst comparison.",
      }))
      .filter((metric) => metric.value !== null);
    return (
      <>
        <div className="analysis-score-strip">
          <ScorePill label="Signal" value={overallRisk} tone={overallTone} hint="How much this player stands out relative to the current match." />
          <ScorePill label="Support" value={supportValue} tone={supportTone(supportValue)} hint="How well the current match contains enough evidence to trust the read." />
        </div>
        <div className="analysis-system-grid analysis-system-grid-glance">
          <article className="glass-card analysis-card profile-card">
            <div className="section-heading compact"><div><span className="eyebrow">Immediate read</span><h3>{triage}</h3></div></div>
            <p className="analysis-copy">{primarySummaryLine(overallRisk, interpretation.global_process_anomaly, interpretation.context_fit, selectedRank, totalPlayers, supportValue)}</p>
            <div className="stat-chip-row">
              <StatChip label="Lobby rank" value={rankValue} tone="cool" />
              <StatChip label="Primary signal" value={primarySignal} tone="neutral" />
              <StatChip label="Support" value={supportLabel(supportValue)} tone="neutral" />
            </div>
          </article>
          <article className="glass-card analysis-card">
            <div className="section-heading compact"><div><span className="eyebrow">Why It Was Raised</span><h3>{interpretation.archetype.summary}</h3></div></div>
            <div className="stat-chip-row compact-stat-chip-row">
              <StatChip label="Driver" value={primarySignal} tone="neutral" />
              <StatChip label="Breadth" value={breadthLabel(interpretation.signal_stability)} tone="neutral" />
              <StatChip label="Support" value={supportLabel(supportValue)} tone="neutral" />
            </div>
            <div className="bullet-stack compact-bullets">
              {topLimitations.map((item) => <span key={item.label}>{item.label}: {item.summary}</span>)}
            </div>
          </article>
          <article className="glass-card analysis-card review-lens-card">
            <div className="section-heading compact"><div><span className="eyebrow">Next Step</span><h3>{nextStep}</h3></div></div>
            <div className="bullet-stack compact-bullets">
              {topComparisons.map((item) => <span key={item}>{item}</span>)}
            </div>
            <p className="analysis-copy compact-copy">{interpretation.review_lens.summary}</p>
            <div className="remaining-signal-row">
              <span className="eyebrow">Model note</span>
              <strong>{uncertaintyLabel}</strong>
            </div>
          </article>
        </div>
        <article className="glass-card overview-console-shell">
          <div className="overview-console-head">
            <div>
              <span className="eyebrow">Analyst console</span>
              <h3>Interactive player overviews</h3>
              <p className="muted small">Switch views to inspect lobby position, match-relative decomposition, and hidden process metrics that do not show up in a normal POV watch.</p>
            </div>
            <div className="nav-stack player-viz-tabs">
              {([
                { key: "signal", label: "Signal map" },
                { key: "match", label: "Match lens" },
                { key: "process", label: "Fight signals" },
              ] as Array<{ key: PlayerVizTab; label: string }>).map((tab) => (
                <button key={tab.key} className={playerVizTab === tab.key ? "stack-tab active" : "stack-tab"} onClick={() => setPlayerVizTab(tab.key)}>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <AnimatePresence mode="wait">
            {playerVizTab === "signal" ? (
              <motion.div
                key={`signal-${selectedPlayer?.steamid || "empty"}`}
                className="overview-console-grid overview-console-grid-signal"
                initial={{ opacity: 0, y: 14, filter: "blur(8px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -12, filter: "blur(8px)" }}
                transition={{ duration: 0.42 }}
              >
                <article className="glass-card console-panel">
                  <div className="section-heading compact">
                    <div>
                      <span className="eyebrow">Lobby position</span>
                      <h3>Signal space</h3>
                      <p className="muted small">Plots every player by process separation and how little normal context explains their shape.</p>
                    </div>
                  </div>
                  <LobbySignalScatter players={filteredPlayers.length ? filteredPlayers : players} selectedSteamid={selectedPlayer?.steamid || ""} />
                </article>
                <article className="glass-card console-panel">
                  <div className="section-heading compact">
                    <div>
                      <span className="eyebrow">Evidence decomposition</span>
                      <h3>Component mix</h3>
                      <p className="muted small">Shows which evidence families are actually carrying this player upward inside the match.</p>
                    </div>
                  </div>
                  <SignalMixChart components={interpretation.signal_components} />
                </article>
              </motion.div>
            ) : null}
            {playerVizTab === "match" ? (
              <motion.div
                key={`match-${selectedPlayer?.steamid || "empty"}`}
                className="overview-console-grid overview-console-grid-match"
                initial={{ opacity: 0, y: 14, filter: "blur(8px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -12, filter: "blur(8px)" }}
                transition={{ duration: 0.42 }}
              >
                <MetricBarMatrix title="Relative markers" subtitle="Match-relative spread" items={interpretation.match_profile.relative_markers} />
                <MetricBarMatrix title="Durability" subtitle="How broad the signal stays" items={interpretation.durability.metrics} />
              </motion.div>
            ) : null}
            {playerVizTab === "process" ? (
              <motion.div
                key={`process-${selectedPlayer?.steamid || "empty"}`}
                className="overview-console-grid overview-console-grid-process"
                initial={{ opacity: 0, y: 14, filter: "blur(8px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -12, filter: "blur(8px)" }}
                transition={{ duration: 0.42 }}
              >
                <article className="glass-card console-panel process-line-panel">
                  <div className="section-heading compact">
                    <div>
                      <span className="eyebrow">Reaction / evidence trace</span>
                      <h3>Process curve</h3>
                      <p className="muted small">Animated left-to-right so switching players makes the sequence read like a fresh trace rather than a static image.</p>
                    </div>
                  </div>
                  <EvidenceChart values={sparkValues} />
                </article>
                {scoreTrace ? <MetricBarMatrix title="Fight-window signals" subtitle="Advanced review markers" items={traceMetrics.map((metric) => ({ key: metric.key, label: metric.label, value: metric.value, summary: metric.hint }))} /> : null}
                <MetricBarMatrix title="Player context" subtitle="Benchmarked review markers" items={focusMetrics} />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </article>
      </>
    );
  };

  const banner = desktopStatus?.is_desktop
    ? desktopStarting
      ? { cls: "banner-info", title: "Starting local review engine", body: "Launching the local NullCS analysis service for desktop demo review." }
      : desktopStatus.healthy
        ? null
        : {
            cls: "banner-warn",
            title: "Local review engine offline",
            body:
              desktopStatus.can_start
                ? "The desktop shell found your local NullCS workspace, but the analysis service is not running yet."
                : "This desktop build can load sample sessions and review bundles, but it did not find a local NullCS workspace to start the review engine.",
          }
    : backendAvailable === false ? { cls: "banner-warn", title: "Local engine unavailable", body: "The desktop shell is open, but the local analysis service is not connected. You can still open the bundled sample review or import a local review bundle." }
      : backendHealth?.mode === "demo" ? { cls: "banner-info", title: "Sample-first mode", body: "Bundled sessions and local review bundles are available. Live inference stays disabled in this build." }
      : backendHealth?.auth_required && !backendHealth?.upload_enabled ? { cls: "banner-warn", title: "Private analysis service", body: "A protected local analysis service is available, but this interface remains focused on review workflows." }
      : null;
  const reportSteamid = report?.player.attacker_steamid || selectedPlayer?.steamid || selectedSteamid;

  return (
    <div className={`app-shell${launchSequenceVisible ? " launch-active" : ""}${launchRevealActive ? " launch-revealing" : ""}`}>
      <audio ref={ambientAudioRef} src="/AmbientBGMusic.mp3" preload="auto" loop />
      <DesktopLaunchSequence
        active={launchSequenceVisible}
        reducedMotion={reducedMotion}
        onAmbientCue={() => {
          const audio = ambientAudioRef.current;
          if (!audio || !musicEnabled) return;
          audio.volume = 0.34;
          void audio.play().catch(() => {});
        }}
        onComplete={() => {
          const audio = ambientAudioRef.current;
          if (audio && audio.paused && musicEnabled) {
            audio.volume = 0.34;
            void audio.play().catch(() => {});
          }
          setLaunchSequenceVisible(false);
          setLaunchRevealActive(true);
          setLaunchRevealNonce((value) => value + 1);
          if (launchRevealTimerRef.current !== null) {
            window.clearTimeout(launchRevealTimerRef.current);
          }
          launchRevealTimerRef.current = window.setTimeout(() => {
            setLaunchRevealActive(false);
            launchRevealTimerRef.current = null;
          }, reducedMotion ? 220 : 860);
        }}
      />
      {launchRevealActive ? <div className="launch-reveal-veil" aria-hidden /> : null}
      <GuideOverlay
        open={guideOpen}
        doNotShowAgain={guideDismissed}
        onToggleDoNotShowAgain={setGuideDismissed}
        onClose={() => setGuideOpen(false)}
      />
      <div className="app-frame">
        {stage !== "home" ? (
          <header className="topbar shell-card">
            <button className="brand-mark-button" onClick={() => setStage("home")} aria-label="Go to home">
              <img className="brand-mark" src="/nullcs-logo-cropped.png" alt="NullCS" />
            </button>
            <div className="topbar-actions">
              <nav className="nav-tabs">
                <button className="nav-tab" onClick={() => setStage("home")}>Intake</button>
                <button className={stage === "results" ? "nav-tab active" : "nav-tab"} onClick={() => players.length && setStage("results")} disabled={!players.length}>Players</button>
                <button className={stage === "report" ? "nav-tab active" : "nav-tab"} onClick={() => report && setStage("report")} disabled={!report}>Report</button>
                <button className={stage === "about" ? "nav-tab active" : "nav-tab"} onClick={() => setStage("about")}>Guide</button>
              </nav>
              <label className="toggle-chip"><input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} /><span>Reduced motion</span></label>
            </div>
          </header>
        ) : null}
        {banner ? (
          <section className={`shell-card banner ${banner.cls}`}>
            <div>
              <div className="eyebrow">{banner.title}</div>
              <p>{banner.body}</p>
              </div>
            <div className="button-row">
              {desktopStatus?.is_desktop && !desktopStatus.healthy && desktopStatus.can_start ? (
                <button className="button button-primary" onClick={() => void connectLocalReviewEngine()} disabled={desktopStarting}>
                  {desktopStarting ? "Starting engine" : "Start local engine"}
                </button>
              ) : null}
              <button className="button button-secondary" onClick={loadSampleWalkthrough}>Open sample</button>
            </div>
          </section>
        ) : null}
        <AnimatePresence initial={false}>
          {stage === "home" ? (
            <motion.section key={`home-${launchRevealNonce}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.28 }} className="tool-stage">
              <header className="tool-topbar shell-card">
                <button className="brand-mark-button" onClick={() => setStage("home")} aria-label="Go to intake">
                  <img className="brand-mark" src="/nullcs-logo-cropped.png" alt="NullCS" />
                </button>
                <nav className="nav-tabs">
                  <button className="nav-tab active" onClick={() => setStage("home")}>Intake</button>
                  <button className="nav-tab" onClick={() => players.length && setStage("results")} disabled={!players.length}>Players</button>
                  <button className="nav-tab" onClick={() => report && setStage("report")} disabled={!report}>Report</button>
                  <button className="nav-tab" onClick={() => setStage("about")}>Guide</button>
                </nav>
                <div className="topbar-actions">
                  <label className="toggle-chip"><input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} /><span>Reduced motion</span></label>
                </div>
              </header>
              <section className="tool-grid">
                <article className="upload-shell shell-card tool-intake-card">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">Demo intake</span>
                      <h2>Drop a `.dem` file. Run local analysis.</h2>
                      <p className="muted small">
                        {publicUploadAvailable
                          ? "The local engine is ready. Choose one Counter-Strike .dem file or drop it below."
                          : desktopStarting
                            ? "Starting the local engine. The run button unlocks when the API is ready."
                            : "The desktop shell will start the local engine before analysis."}
                      </p>
                    </div>
                    <span className="muted small">
                      {publicUploadAvailable && backendHealth?.max_upload_bytes
                        ? `${Math.round(backendHealth.max_upload_bytes / (1024 * 1024))} MB limit`
                        : desktopStatus?.healthy
                          ? "Engine online"
                          : desktopStatus?.is_desktop
                            ? "Local engine"
                            : "Review mode"}
                    </span>
                  </div>
                  <input className="field" placeholder="Optional case label" value={caseLabel} onChange={(e) => setCaseLabel(e.target.value)} disabled={!publicUploadAvailable && !activeBundle} />
                  <input ref={demoInputRef} type="file" accept=".dem" className="hidden-file-input" onChange={(e) => selectDemoFile(e.target.files?.[0] || null)} />
                  <button
                    type="button"
                    className="upload-zone upload-zone-button tool-drop-zone"
                    onClick={openDemoPicker}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={handleDemoDrop}
                  >
                    <span className="upload-kicker">Counter-Strike demo input</span>
                    <span className="upload-title">{desktopDemoPath ? desktopDemoPath.split(/[\\/]/).pop() : file ? file.name : "Drop .dem file here"}</span>
                    <span className="muted small">{file || desktopDemoPath ? "Ready to run. The app will keep this session state through refresh." : "Only .dem files are accepted. Click to browse or drag one into this panel."}</span>
                  </button>
                  <div className="button-row hero-intake-actions">
                    {desktopStatus?.is_desktop && !publicUploadAvailable && desktopStatus.can_start ? (
                      <button className="button button-secondary" onClick={() => void connectLocalReviewEngine()} disabled={desktopStarting}>
                        {desktopStarting ? "Starting engine" : "Start local engine"}
                      </button>
                    ) : null}
                    <button className="button button-secondary" onClick={openDemoPicker}>{desktopDemoPath || file ? "Change file" : "Choose file"}</button>
                    <button className="button button-primary" onClick={onUploadAndRun} disabled={(!file && !desktopDemoPath) || !publicUploadAvailable}>Run analysis</button>
                  </div>
                </article>
                <aside className="shell-card tool-guide-card">
                  <div className="section-heading compact">
                    <div>
                      <span className="eyebrow">Readout guide</span>
                      <h3>How to interpret results</h3>
                    </div>
                  </div>
                  <div className="tool-guide-list">
                    <div><strong>Signal</strong><p>How far a player stands out inside this match. It is review priority, not a verdict.</p></div>
                    <div><strong>Support</strong><p>How much usable evidence the match contains for that player.</p></div>
                    <div><strong>Process metrics</strong><p>Neural encounter outputs summarize aim, mouse, view-angle, visibility, and shot timing behavior.</p></div>
                    <div><strong>Colors</strong><p>They mark review severity against benchmarks. Strong legitimate players can still look unusual in isolated moments.</p></div>
                  </div>
                  <div className="button-row">
                    <button className="button button-secondary" onClick={loadSampleWalkthrough}>Open sample</button>
                    <button className="button button-secondary" onClick={() => setStage("about")}>Full guide</button>
                  </div>
                </aside>
              </section>
              {players.length ? (
                <section className="shell-card resume-card">
                  <div>
                    <span className="eyebrow">Session restored</span>
                    <h3>{rosterTitle || "Previous analysis"}</h3>
                    <p className="muted small">Your last ranked roster is still loaded locally.</p>
                  </div>
                  <div className="button-row">
                    <button className="button button-primary" onClick={() => setStage("results")}>Open players</button>
                    {report ? <button className="button button-secondary" onClick={() => setStage("report")}>Open report</button> : null}
                  </div>
                </section>
              ) : null}
            </motion.section>
          ) : null}
          {stage === "about" ? (
            <motion.section
              key="about"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.28 }}
              className="page-grid guide-stage"
            >
              <section className="guide-grid">
                <article className="shell-card guide-panel guide-panel-large guide-hero-panel">
                  <div className="guide-hero-copy">
                    <span className="eyebrow">Tool guide</span>
                    <h2>Review one Counter-Strike demo at a time.</h2>
                    <p>NullCS accepts `.dem` files only. Load a demo, run analysis, inspect the ranked lobby, then use the player report to decide what deserves manual follow-up.</p>
                  </div>
                  <div className="button-row">
                    <button className="button button-primary" onClick={() => setStage("home")}>Back to intake</button>
                    {players.length ? <button className="button button-secondary" onClick={() => setStage("results")}>Open players</button> : null}
                  </div>
                </article>
                <article className="shell-card guide-panel">
                  <span className="eyebrow">Input</span>
                  <h3>Start with a `.dem` file</h3>
                  <div className="tool-guide-list">
                    <div><strong>Accepted file</strong><p>Use a Counter-Strike demo file ending in `.dem`. Videos, clips, screenshots, archives, and scoreboard images are not valid inputs.</p></div>
                    <div><strong>One match</strong><p>Each run analyzes one match and ranks players inside that lobby only.</p></div>
                    <div><strong>Local workflow</strong><p>Choose or drop the file on Intake, run analysis, then open Players or Report when processing finishes.</p></div>
                  </div>
                </article>
                <article className="shell-card guide-panel">
                  <span className="eyebrow">Review flow</span>
                  <h3>How to use the results</h3>
                  <div className="tool-guide-list">
                    <div><strong>Signal</strong><p>Use signal as review priority. Higher signal means the player stands out more inside this match.</p></div>
                    <div><strong>Support</strong><p>Support tells you how much usable evidence exists. Thin support should make the read more cautious.</p></div>
                    <div><strong>Report</strong><p>Use the report to inspect why the player was raised, what weakens the case, and what to check next.</p></div>
                  </div>
                </article>
                <article className="shell-card guide-panel">
                  <span className="eyebrow">Severity</span>
                  <h3>What Review means</h3>
                  <p>A Review label means signals are starting to align with irregular play patterns and the player should be looked into more closely. It does not automatically settle the case.</p>
                  <p>For edge cases, compare the report with the actual demo, round context, POV, teammate information, opponent behavior, and ideally other matches from the same player.</p>
                </article>
                <article className="shell-card guide-panel guide-panel-wide">
                  <span className="eyebrow">Uncertainty</span>
                  <h3>Why one demo should not be treated as the whole case</h3>
                  <p>Counter-Strike has legitimate outlier moments: strong aim, lucky timing, unusual utility, opponent mistakes, smurfing, role differences, and small-sample noise can all produce elevated signals in one match.</p>
                  <p>NullCS is strongest as a triage tool: it tells you who deserves attention first, then helps you collect evidence. A single demo can justify deeper review, but repeated patterns across rounds and matches carry much more weight than one isolated read.</p>
                </article>
                <article className="shell-card guide-panel guide-panel-wide">
                  <span className="eyebrow">Model stack</span>
                  <h3>What the neural layer adds</h3>
                  <p>The encounter model summarizes short fight windows using aim error, mouse delta, command/view-angle movement, visibility changes, movement state, shots, and damage timing. XGBoost uses those summaries with the broader player-level features to rank the lobby.</p>
                </article>
              </section>
            </motion.section>
          ) : null}
          {stage === "results" ? (
            <motion.section key="results" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }} className="page-grid results-grid">
              <aside className="leaderboard-panel shell-card">
                <div className="section-heading compact">
                  <div><span className="eyebrow">Match roster</span><h3 title={demoId || "No demo selected"}>{rosterTitle || "No demo selected"}</h3><p className="muted small mono">{demoId || ""}</p></div>
                  <input className="field compact" placeholder="Search player or SteamID" value={query} onChange={(e) => setQuery(e.target.value)} />
                </div>
                <SignalLegend />
                <div className="leaderboard-list">
                  {filteredPlayers.map((player, index) => {
                    const playerSignal = player.risk ?? player.proba_cheater_infer;
                    const playerTone = signalTone(playerSignal);
                    const playerTriage = triageLabel(
                      playerSignal,
                      index + 1,
                      filteredPlayers.length || players.length || 1,
                      player.interpretation?.context_fit,
                      player.confidence,
                      player.interpretation?.global_process_anomaly
                    );
                    return (
                      <button key={player.steamid} className={player.steamid === selectedSteamid ? "player-row active" : "player-row"} onClick={() => void selectPlayer(player.steamid)}>
                        <div className="player-main">
                          <span className="player-rank">#{index + 1}</span>
                          <strong className="player-name">{player.attacker_name || "Unknown player"}</strong>
                          <span className="muted small">{playerTriage}</span>
                          <span className="muted small mono">{shortId(player.steamid, 8, 6)}</span>
                        </div>
                        <div className="player-risk-block">
                          <span className={`risk-dot tone-${playerTone}`} />
                          <strong>{scoreDisplay(playerSignal)}</strong>
                          <span className="muted small">signal</span>
                        </div>
                      </button>
                    );
                  })}
                  {!filteredPlayers.length ? (
                    <div className="empty-state">
                      <span className="eyebrow">{players.length ? "No matching players" : "No roster loaded"}</span>
                      <p>{players.length ? "Clear the search field or try a SteamID fragment." : "Load a .dem file from Intake or open the bundled sample to inspect a finished review."}</p>
                    </div>
                  ) : null}
                </div>
              </aside>
              <div className="results-main">
                <section className="overview-panel shell-card results-overview-panel">
                  <div className="section-heading compact results-identity-head">
                    <div>
                      <span className="eyebrow">Player overview</span>
                      <AnimatePresence mode="wait">
                        <motion.div key={selectedPlayer?.steamid || "empty"} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                          <h3>{selectedPlayer?.attacker_name || "Select a player"}</h3>
                          <p className="muted small mono">{selectedPlayer?.steamid || selectedSteamid || SAMPLE_STEAMID}</p>
                          {selectedInterpretation ? <div className="overview-badges"><span className={`severity-chip tone-${signalTone(selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer)}`}>{triageLabel(selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer, selectedRank, filteredPlayers.length || players.length || 1, selectedInterpretation.context_fit, selectedPlayer?.confidence, selectedInterpretation.global_process_anomaly)}</span><span className="overview-rank">Rank #{selectedRank} of {filteredPlayers.length || players.length || 1}</span></div> : null}
                        </motion.div>
                      </AnimatePresence>
                    </div>
                    {selectedPlayer ? (
                      <div className="button-row">
                        <button className="button button-secondary" onClick={() => void openPlayerProfile(steamCommunityUrl(selectedPlayer.steamid))} disabled={!validSteamId(selectedPlayer.steamid)}>Steam</button>
                        <button className="button button-secondary" onClick={() => void openPlayerProfile(csStatsUrl(selectedPlayer.steamid))} disabled={!validSteamId(selectedPlayer.steamid)}>CSStats</button>
                        <button className="button button-primary" onClick={() => void openReport(selectedPlayer.steamid)}>Open report</button>
                      </div>
                    ) : null}
                  </div>
                  <div className="overview-disclaimer">Signal is match-relative. Use it to decide who to look at first, not as a verdict.</div>
                  {activeBundle?.meta ? (
                    <div className="overview-disclaimer">
                      <strong>{activeBundle.meta.display_name}</strong>
                      {activeBundle.meta.summary ? ` ${activeBundle.meta.summary}` : ""}
                      {activeBundle.meta.benchmark_snapshot
                        ? ` Benchmark snapshot: suspicious top-1 ${(activeBundle.meta.benchmark_snapshot.cheater_top1_hit_rate ?? 0) * 100}% | top-3 ${(activeBundle.meta.benchmark_snapshot.cheater_top3_hit_rate ?? 0) * 100}% | held-out legit median top-1 ${num(activeBundle.meta.benchmark_snapshot.legit_median_top1_score ?? null, 4)}.`
                        : ""}
                    </div>
                  ) : null}
                  {renderInterpretationDeck(selectedInterpretation, selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer, selectedPlayer?.confidence, selectedUncertaintyLabel)}
                </section>
              </div>
            </motion.section>
          ) : null}
          {stage === "report" ? (
            <motion.section key="report" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }} className="page-grid report-grid">
              <section className="report-header shell-card">
                <div>
                  <span className="eyebrow">Player report</span>
                  <h2>{report?.player.attacker_name || selectedPlayer?.attacker_name || "Unknown player"}</h2>
                  <p className="muted small mono">{report?.player.attacker_steamid || selectedSteamid || SAMPLE_STEAMID}</p>
                </div>
                <div className="button-row">
                  <button className="button button-secondary" onClick={() => void openPlayerProfile(steamCommunityUrl(reportSteamid))} disabled={!validSteamId(reportSteamid)}>Steam</button>
                  <button className="button button-secondary" onClick={() => void openPlayerProfile(csStatsUrl(reportSteamid))} disabled={!validSteamId(reportSteamid)}>CSStats</button>
                  <button className="button button-secondary" onClick={() => setStage("results")}>Back to players</button>
                </div>
              </section>
              <aside className="report-sidebar shell-card">
                <div className="nav-stack">
                  {(["overview", "reasons"] as ReportTab[]).map((tab) => <button key={tab} className={reportTab === tab ? "stack-tab active" : "stack-tab"} onClick={() => setReportTab(tab)}>{cap(tab)}</button>)}
                </div>
                {reportInterpretation ? <div className="sidebar-summary glass-card sidebar-interpretation"><span className="eyebrow">Quick read</span><h3>{triageLabel(report?.risk.calibrated_probability ?? report?.risk.score, selectedRank, filteredPlayers.length || players.length || 1, reportInterpretation.context_fit, reportConfidenceValue, reportInterpretation.global_process_anomaly)}</h3><p>{primarySummaryLine(report?.risk.calibrated_probability ?? report?.risk.score, reportInterpretation.global_process_anomaly, reportInterpretation.context_fit, selectedRank, filteredPlayers.length || players.length || 1, reportConfidenceValue)}</p><div className="sidebar-stat-list"><div><span>Overall signal</span><strong>{scoreDisplay(report?.risk.calibrated_probability ?? report?.risk.score)}</strong></div><div><span>Aim / process</span><strong>{scoreDisplay(reportInterpretation.global_process_anomaly)}</strong></div><div><span>Context</span><strong>{contextLabel(reportInterpretation.context_fit)}</strong></div></div></div> : null}
              </aside>
              <div className="report-body shell-card">
                <div className="overview-disclaimer">Use this page as a quick review handoff: why they were raised, what weakens it, and what to check next.</div>
                {reportTab === "overview" ? (
                  renderInterpretationDeck(reportInterpretation, report?.risk.calibrated_probability ?? report?.risk.score, reportConfidenceValue, reportUncertaintyLabel)
                ) : null}
                {reportTab === "reasons" ? (
                  <div className="reason-list">
                    {(report?.reasons || []).map((reason, index) => {
                      const tone: Tone = String(reason.severity).toLowerCase() === "high" ? "critical" : String(reason.severity).toLowerCase() === "medium" ? "warning" : String(reason.severity).toLowerCase() === "low" ? "good" : "neutral";
                      return (
                        <article key={`${reason.title}-${index}`} className={`reason-card glass-card tone-${tone}`}>
                          <div className="reason-head">
                            <div><span className="eyebrow">Interpretive signal {String(index + 1).padStart(2, "0")}</span><h3>{reason.title}</h3></div>
                            <span className={`severity-chip tone-${tone}`}>{reason.severity}</span>
                          </div>
                          <p>{reason.summary}</p>
                          <p className="muted">{reason.why_it_matters}</p>
                          {reason.confidence_note ? <p className="muted small">Support note: {reason.confidence_note}</p> : null}
                          {reason.evidence_file ? <span className="muted small mono">Evidence: {reason.evidence_file}</span> : null}
                        </article>
                      );
                    })}
                    {!(report?.reasons || []).length ? (
                      <div className="empty-state">
                        <span className="eyebrow">No reason cards available</span>
                        <p>The report opened, but this build did not return reason cards for the selected player. Use the overview read and rerun analysis if this looks unexpected.</p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {reportTab === "trace" ? (
                  <div className="trace-layout">
                    <article className="glass-card">
                      <div className="section-heading compact"><div><span className="eyebrow">Diagnostics</span><h3>Runtime execution</h3><p className="muted small">Developer-only diagnostics for validating local model behavior.</p></div></div>
                      <div className="trace-grid">
                        <MetricCard label="Base signal" raw={scoreTrace?.raw_proba ?? null} display={pct(scoreTrace?.raw_proba)} hint="developer diagnostic" tone={metricTone("risk", scoreTrace?.raw_proba ?? null)} />
                        <MetricCard label="Served signal" raw={scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null} display={pct(scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null)} hint="developer diagnostic" tone={metricTone("risk", scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null)} />
                        <article className="metric-card tone-neutral"><div className="metric-meta"><span className="eyebrow">Model version</span></div><strong className="metric-value meta-value">{scoreTrace?.model_version || "--"}</strong><span className="metric-hint">runtime artifact</span></article>
                        <article className="metric-card tone-neutral"><div className="metric-meta"><span className="eyebrow">Feature list</span></div><strong className="metric-value meta-value">{scoreTrace?.feature_list_version || "--"}</strong><span className="metric-hint">model input schema</span></article>
                      </div>
                    </article>
                    <article className="glass-card">
                      <div className="section-heading compact"><div><span className="eyebrow">Diagnostics</span><h3>Process support</h3><p className="muted small">Developer-only view of the strongest fight-window markers.</p></div></div>
                      <div className="feature-grid">
                        {traceFocusMetrics(scoreTrace).map((metric) => (
                          <div key={metric.key} className={`feature-chip tone-${metricTone(metric.toneKey || metric.key, metric.value)}`}>
                            <span>{metric.label}</span>
                            <strong>{typeof metric.value === "number" ? num(metric.value, /(rate|score|precision)/i.test(metric.key) ? 3 : 2) : "--"}</strong>
                            <em>{metric.hint}</em>
                          </div>
                        ))}
                      </div>
                    </article>
                    <article className="glass-card">
                      <div className="section-heading compact"><div><span className="eyebrow">Artifacts kept</span><h3>Analyst handoff</h3></div></div>
                      <div className="bullet-stack">
                        <span>Interpretation deck remains the primary read for the player.</span>
                        <span>Runtime trace is preserved to validate why the model supported or discounted the case.</span>
                        <span>Raw evidence files still exist on disk, but they are no longer the main report surface.</span>
                      </div>
                    </article>
                  </div>
                ) : null}
              </div>
            </motion.section>
          ) : null}
        </AnimatePresence>
        {error ? <div className="shell-card banner banner-error">{error}</div> : null}
      </div>
      {stage === "processing" ? <ProcessingOverlay reducedMotion={reducedMotion} title="Processing Demo" subtitle={status.stage || "Uploading"} logs={status.logs_tail} steps={PIPELINE_STEPS} activeStep={status.stage_index ?? 0} /> : null}
    </div>
  );
}
export default App;

