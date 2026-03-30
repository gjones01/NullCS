import { AnimatePresence, motion } from "framer-motion";
import { Suspense, lazy, startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  type DemoStatus,
  type EvidenceTable,
  type ExplainReport,
  type HealthResponse,
  type InterpretationModel,
  type PlayerRow,
  type ScoreTrace,
  explainPlayer,
  getEvidenceTable,
  getExplainReport,
  getHealth,
  getPlayerScoreTrace,
  getPlayers,
  getStatus,
  runDemo,
  uploadDemo,
} from "./lib/api";
import { APP_CONFIG } from "./config";
import { SAMPLE_DEMO_ID, SAMPLE_EVIDENCE, SAMPLE_EXPLAIN_REPORT, SAMPLE_PLAYERS, SAMPLE_SCORE_TRACE, SAMPLE_STEAMID } from "./mockData";
import { AntigravityField } from "./components/AntigravityField";
import { MetallicLogo } from "./components/MetallicLogo";
import { ProcessingOverlay } from "./components/ProcessingOverlay";

type Stage = "home" | "about" | "processing" | "results" | "report";
type ReportTab = "overview" | "reasons" | "trace";
type Tone = "critical" | "warning" | "elevated" | "good" | "cool" | "neutral";
type ReviewPriority = "highest" | "priority" | "review" | "monitor";
type AnalystAction = "escalate_context" | "review_sequence" | "hold_for_context" | "close_low_priority";

const PIPELINE_STEPS = ["Uploading", "Parsing", "Feature Build", "Model", "Explanation"];
const POINTS = [
  { id: "n1", x: 9, y: 18, size: 2.5, value: 54 }, { id: "n2", x: 18, y: 34, size: 2, value: 68 }, { id: "n3", x: 29, y: 24, size: 2.2, value: 31 },
  { id: "n4", x: 40, y: 44, size: 1.8, value: 82 }, { id: "n5", x: 54, y: 20, size: 2.8, value: 49 }, { id: "n6", x: 63, y: 38, size: 1.8, value: 63 },
  { id: "n7", x: 73, y: 28, size: 2.1, value: 27 }, { id: "n8", x: 83, y: 42, size: 2.4, value: 77 }, { id: "n9", x: 91, y: 26, size: 2.1, value: 14 },
  { id: "n10", x: 15, y: 72, size: 2.2, value: 21 }, { id: "n11", x: 30, y: 64, size: 1.9, value: 96 }, { id: "n12", x: 48, y: 78, size: 2.7, value: 35 },
  { id: "n13", x: 66, y: 70, size: 2.2, value: 72 }, { id: "n14", x: 84, y: 76, size: 2.6, value: 91 },
] as const;
const LINKS = [["n1","n2"],["n2","n3"],["n3","n5"],["n5","n7"],["n7","n9"],["n2","n10"],["n10","n11"],["n11","n12"],["n12","n13"],["n13","n14"],["n4","n6"],["n6","n8"],["n5","n6"],["n7","n8"]] as const;

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
const steamCommunityUrl = (steamid: string) => `https://steamcommunity.com/profiles/${steamid}`;
const csStatsUrl = (steamid: string) => `https://csstats.gg/player/${steamid}`;
const METRIC_INFO: Record<string, string> = {
  "Review Lane": "A neutral workflow label based on how unusual this player looks relative to others in the same match. It is not a cheating verdict.",
  "Evidence Confidence": "How stable and well-supported the current behavior signal is. High confidence means the score has enough supporting evidence, not that the player is confirmed cheating.",
  "Lobby Rank": "Where the player sits relative to others in this specific match by behavioral deviation. Rank is match-relative only.",
  "Reaction Window": "Median visibility-to-shot timing across tracked kill events. Lower values can be unusual, but context matters.",
  "Shot Discipline": "Share of kills where the shot timing suggests prefire-like behavior before or immediately as visibility begins.",
  "Accuracy Concentration": "Headshot share within the playerâ€™s tracked kill sample. Strong aim alone can be legitimate, especially for top players.",
  "Occlusion Anomaly": "Share of smoke-occluded kills. Elevated values can merit context review, but are not decisive on their own.",
};
const DEFAULT_PRODUCT_IDENTITY = "Single-match behavioral review workspace";
const DEFAULT_PRODUCT_TAGLINE = "Match-relative behavioral review with explainable evidence and neutral analysis.";
const CryoScene = lazy(() => import("./components/CryoScene").then((mod) => ({ default: mod.CryoScene })));
const detectLowPowerDefault = () => {
  const nav = navigator as Navigator & { deviceMemory?: number };
  return (navigator.hardwareConcurrency || 8) <= 4 || (nav.deviceMemory || 8) <= 4;
};

const ABOUT_PILLARS = [
  {
    title: "Built for review, not verdicts",
    body: "NullCS is designed to help an analyst decide who deserves a closer look inside one match. It does not claim certainty and it does not replace human judgment.",
  },
  {
    title: "Focused on behavioral shape",
    body: "Instead of relying on one headline stat, the system looks at timing, sequence, visibility pressure, and how stable a player stays when ordinary play should become messy.",
  },
  {
    title: "Made to stay explainable",
    body: "Every surfaced player is paired with a plain-language read, context checks, and review prompts so the result is understandable rather than opaque.",
  },
] as const;

const ABOUT_STEPS = [
  "Load one demo and score the whole lobby.",
  "Raise the strongest standouts relative to that match.",
  "Show why the signal was raised and what weakens it.",
  "Leave the final judgment to the person reviewing the case.",
] as const;

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
  const k = key.toLowerCase();
  if (k.includes("confidence")) return value >= 0.82 ? "cool" : value >= 0.58 ? "neutral" : value >= 0.38 ? "elevated" : "warning";
  if (k.includes("percentile") || k.endsWith(" pct") || k.endsWith("_pct")) return value >= 0.96 ? "critical" : value >= 0.88 ? "warning" : value >= 0.72 ? "elevated" : "good";
  if (k.includes("risk") || k.includes("prob")) return value >= 0.55 ? "critical" : value >= 0.3 ? "warning" : value >= 0.14 ? "elevated" : "good";
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
  const k = key.toLowerCase();
  if (/(confidence|risk|rate|share|percentile|prob)/i.test(k)) return clamp01(value);
  if (k.includes("rt_median")) return clamp01(1 - Math.min(value, 24) / 24);
  if (k.includes("distance")) return clamp01(Math.min(value, 1500) / 1500);
  return clamp01(Math.min(Math.abs(value), 1));
}

function formatSignalValue(key: string, value: number | null) {
  if (value === null || !Number.isFinite(value)) return "--";
  return isRateMetric(key) ? pct(value) : num(value, key.toLowerCase().includes("rt") ? 1 : 2);
}

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
  return `${Math.round(clamp01(value ?? 0) * 100)}`;
}

function triageLabel(
  value: number | null | undefined,
  rank?: number,
  total?: number,
  contextFit?: number | null | undefined,
  support?: number | null | undefined,
  process?: number | null | undefined
) {
  const safe = clamp01(value ?? 0);
  const safeRank = rank ?? 999;
  const safeTotal = Math.max(total ?? 1, 1);
  const topSlice = safeRank / safeTotal;
  const weakContext = clamp01(contextFit ?? 1) < 0.4;
  const strongSupport = clamp01(support ?? 0) >= 0.75;
  const strongProcess = clamp01(process ?? 0) >= 0.35;

  if (safe >= 0.4) return "Strong review";
  if (safe >= 0.2) return "Needs review";
  if ((safeRank === 1 || topSlice <= 0.2) && weakContext && strongSupport && strongProcess) return "Needs review";
  if (safe >= 0.1) return "Light watch";
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
  const risk = clamp01(overallRisk ?? 0);
  const processScore = clamp01(process ?? 0);
  const context = clamp01(contextFit ?? 0);
  const safeRank = rank ?? 999;
  const safeTotal = Math.max(total ?? 1, 1);
  const topSlice = safeRank / safeTotal;
  const stable = clamp01(support ?? 0) >= 0.75;
  if (risk < 0.1 && processScore < 0.25) return "This player sits inside the typical range we have seen on held-out legit matches.";
  if (risk >= 0.7 && context < 0.35) return "This player stands out strongly and the match context does not explain much of it.";
  if (processScore >= 0.55 && context < 0.35) return "The main concern is unusually strong process signal that normal context does not explain well.";
  if ((safeRank === 1 || topSlice <= 0.2) && context < 0.35 && stable) return "This player is one of the strongest standouts in the match, but the absolute model score is still moderate rather than decisive.";
  if (context >= 0.6) return "There is some signal here, but ordinary match context explains a meaningful share of it.";
  return "This player stands out enough to review, but the case is not clean-cut from the model alone.";
}

function traceFocusMetrics(scoreTrace: ScoreTrace | null) {
  const row = scoreTrace?.feature_row || {};
  const candidates: Array<{ label: string; key: string; value: number | null; hint: string; toneKey?: string }> = [
    { label: "Aim-process score", key: "aim_process_global_score", value: safeMaybeNumber(row.aim_process_global_score), hint: "combined process abnormality from encounter dynamics", toneKey: "risk" },
    { label: "Input burst score", key: "enc_input_burst_score", value: safeMaybeNumber(row.enc_input_burst_score), hint: "how strong the pre-shot mouse burst pattern is", toneKey: "risk" },
    { label: "Input stability score", key: "enc_input_stability_score", value: safeMaybeNumber(row.enc_input_stability_score), hint: "how unusually quiet and stable corrections stay after acquire", toneKey: "risk" },
    { label: "Precision under difficulty", key: "enc_precision_under_difficulty", value: safeMaybeNumber(row.enc_precision_under_difficulty), hint: "clean aim retention in harder fights", toneKey: "risk" },
    { label: "Process abnormality", key: "enc_process_abnormality", value: safeMaybeNumber(row.enc_process_abnormality), hint: "combined contradiction signal from acquire, low-vis, and shot timing", toneKey: "risk" },
    { label: "Mouse burst max", key: "enc_mouse_burst_mean", value: safeMaybeNumber(row.enc_mouse_burst_mean), hint: "mean pre-shot input burst across encounters" },
    { label: "Mouse quiet rate", key: "enc_mouse_quiet_mean", value: safeMaybeNumber(row.enc_mouse_quiet_mean), hint: "share of low-input ticks after acquire", toneKey: "confidence" },
    { label: "Shot-before-acquire", key: "enc_shot_before_acquire_rate", value: safeMaybeNumber(row.enc_shot_before_acquire_rate), hint: "how often shots arrive before aim acquire", toneKey: "risk" },
    { label: "Low-vis precision", key: "enc_low_vis_precision_retention", value: safeMaybeNumber(row.enc_low_vis_precision_retention), hint: "kill-end retention in lower-visibility fights", toneKey: "risk" },
    { label: "Median RT", key: "rt_median", value: safeMaybeNumber(row.rt_median), hint: "median visibility-to-shot timing in ticks" },
    { label: "Prefire rate", key: "prefire_rate", value: safeMaybeNumber(row.prefire_rate), hint: "share of kill events that look prefire-like", toneKey: "risk" },
    { label: "Headshot rate", key: "headshot_rate", value: safeMaybeNumber(row.headshot_rate), hint: "mechanical conversion share in the sample", toneKey: "risk" },
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
    { range: "0-9", label: "Typical", tone: "good" },
    { range: "10-19", label: "Watch", tone: "elevated" },
    { range: "20-39", label: "Review", tone: "warning" },
    { range: "40+", label: "Strong", tone: "critical" },
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

function StatChip({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className={`stat-chip tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function App() {
  const [stage, setStage] = useState<Stage>("home");
  const [demoId, setDemoId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<DemoStatus>({ demo_id: "", state: "queued", logs_tail: "", error: "" });
  const [players, setPlayers] = useState<PlayerRow[]>([]);
  const [selectedSteamid, setSelectedSteamid] = useState("");
  const [scoreTrace, setScoreTrace] = useState<ScoreTrace | null>(null);
  const [report, setReport] = useState<ExplainReport | null>(null);
  const [evidenceTables, setEvidenceTables] = useState<Record<string, EvidenceTable>>({});
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [reportTab, setReportTab] = useState<ReportTab>("overview");
  const [error, setError] = useState("");
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [reducedMotion, setReducedMotion] = useState(() => {
    const stored = window.localStorage.getItem("nullcs_reduced_motion");
    if (stored === "1") return true;
    if (stored === "0") return false;
    return detectLowPowerDefault();
  });

  useEffect(() => {
    void (async () => {
      try {
        setBackendHealth(await getHealth());
        setBackendAvailable(true);
      } catch {
        setBackendAvailable(false);
      }
    })();
  }, []);

  useEffect(() => {
    window.localStorage.setItem("nullcs_reduced_motion", reducedMotion ? "1" : "0");
    document.documentElement.dataset.motion = reducedMotion ? "reduced" : "full";
  }, [reducedMotion]);

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
        if (next.state === "error") setError(next.error || "Analysis failed.");
      } catch (err) {
        const message = String(err);
        if (/429|rate limit/i.test(message)) return;
        setError(message);
      }
    }, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [stage, demoId]);

  const publicUploadAvailable = backendAvailable === true && !!backendHealth?.upload_enabled && !backendHealth?.auth_required && backendHealth?.mode !== "demo";
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
  const signalEntries = useMemo(() => {
    if (report?.signals?.lobby_percentiles && typeof report.signals.lobby_percentiles === "object") {
      return Object.entries(report.signals.lobby_percentiles).slice(0, 6);
    }
    return selectedPlayer && selectedPlayer.features_summary && typeof selectedPlayer.features_summary === "object"
      ? Object.entries(selectedPlayer.features_summary).slice(0, 6)
      : [];
  }, [report, selectedPlayer]);
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
    { label: "Detection lens", value: "Process + context", note: "timing, visibility, movement pressure, and encounter shape" },
    { label: "Analyst handoff", value: "Reports + traces", note: "fast reads, ranked rosters, and saved review artifacts" },
  ], [featureCount]);

  async function selectPlayer(steamid: string, sourcePlayers = players) {
    setSelectedSteamid(steamid);
    const player = sourcePlayers.find((p) => p.steamid === steamid);
    if (!player) return;
    if (demoId === SAMPLE_DEMO_ID) {
      setScoreTrace({ ...SAMPLE_SCORE_TRACE, steamid, attacker_name: player.attacker_name });
      return;
    }
    try {
      setScoreTrace((await getPlayerScoreTrace(demoId, steamid)).trace);
    } catch (err) {
      setError(String(err));
      setScoreTrace(null);
    }
  }

  function loadSampleWalkthrough() {
    setError("");
    setDemoId(SAMPLE_DEMO_ID);
    setDisplayName("Sample Demo");
    setPlayers(SAMPLE_PLAYERS.map(normalizePlayer));
    setSelectedSteamid(SAMPLE_STEAMID);
    setScoreTrace(SAMPLE_SCORE_TRACE);
    setReport(null);
    setEvidenceTables({});
    setReportTab("overview");
    setStage("results");
  }

  async function onUploadAndRun() {
    try {
      if (!file) return;
      if (!publicUploadAvailable) throw new Error("Live uploads are disabled on this deployment.");
      if (!file.name.toLowerCase().endsWith(".dem")) throw new Error("Only .dem files are accepted.");
      setError("");
      const uploaded = await uploadDemo(file, demoId || undefined);
      setDemoId(uploaded.demo_id);
      setDisplayName(uploaded.original_filename || file.name);
      setStatus({ demo_id: uploaded.demo_id, state: "queued", logs_tail: "", error: "", original_filename: uploaded.original_filename || file.name, stage_index: 0, stage: "Uploading", steps: PIPELINE_STEPS });
      await runDemo(uploaded.demo_id);
      setStage("processing");
    } catch (err) {
      setError(String(err));
    }
  }

  async function openReport(steamid: string) {
    try {
      setSelectedSteamid(steamid);
      setError("");
      if (demoId === SAMPLE_DEMO_ID) {
        setReport(SAMPLE_EXPLAIN_REPORT);
        setEvidenceTables(SAMPLE_EVIDENCE);
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
      setError(String(err));
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
    const overallTone = intensityTone(overallRisk);
    const processTone = intensityTone(interpretation.global_process_anomaly);
    const explanationToneValue = invertedTone(interpretation.context_fit);
    const triage = triageLabel(overallRisk, selectedRank, totalPlayers, interpretation.context_fit, supportValue, interpretation.global_process_anomaly);
    const nextStep = topComparisons[0] || interpretation.review_lens.title;
    return (
      <>
        <div className="analysis-score-strip">
          <ScorePill label="Match anomaly" value={overallRisk} tone={overallTone} hint={triage} />
          <ScorePill label="Aim / process" value={interpretation.global_process_anomaly} tone={processTone} hint={scoreBucket(interpretation.global_process_anomaly, 0.75, 0.4)} />
          <ScorePill label="Context explanation" value={1 - clamp01(interpretation.context_fit)} tone={explanationToneValue} hint={contextLabel(interpretation.context_fit)} />
          <ScorePill label="Support" value={supportValue} tone={intensityTone(supportValue)} hint={supportLabel(supportValue)} />
        </div>
        <div className="analysis-system-grid analysis-system-grid-glance">
          <article className="glass-card analysis-card profile-card">
            <div className="section-heading compact"><div><span className="eyebrow">Immediate read</span><h3>{triage}</h3></div></div>
            <p className="analysis-copy">{primarySummaryLine(overallRisk, interpretation.global_process_anomaly, interpretation.context_fit, selectedRank, totalPlayers, supportValue)}</p>
            <div className="stat-chip-row">
              <StatChip label="Lobby rank" value={rankValue} tone="cool" />
              <StatChip label="Primary signal" value={primarySignal} tone={processTone} />
              <StatChip label="Context" value={contextLabel(interpretation.context_fit)} tone={explanationToneValue} />
            </div>
          </article>
          <article className="glass-card analysis-card">
            <div className="section-heading compact"><div><span className="eyebrow">Why It Was Raised</span><h3>{interpretation.archetype.summary}</h3></div></div>
            <div className="stat-chip-row compact-stat-chip-row">
              <StatChip label="Driver" value={primarySignal} tone={processTone} />
              <StatChip label="Breadth" value={breadthLabel(interpretation.signal_stability)} tone={intensityTone(interpretation.signal_stability)} />
              <StatChip label="Support" value={supportLabel(supportValue)} tone={intensityTone(supportValue)} />
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
      </>
    );
  };

  const banner = backendAvailable === false ? { cls: "banner-warn", title: "Backend unavailable", body: "API not detected. You can still review the sample analysis." }
    : backendHealth?.mode === "demo" ? { cls: "banner-info", title: "Public demo mode", body: "Uploads and live inference are disabled here. Use the sample walkthrough or run the backend locally." }
    : backendHealth?.auth_required && !backendHealth?.upload_enabled ? { cls: "banner-warn", title: "Protected backend", body: "This backend is configured for private use with an API key." }
    : null;

  return (
    <div className="app-shell">
      <ConstellationBackground reducedMotion={reducedMotion} />
      <div className="ambient-grid" aria-hidden />
      <div className="ambient-glow ambient-glow-left" aria-hidden />
      <div className="ambient-glow ambient-glow-right" aria-hidden />
      <div className="ambient-vignette" aria-hidden />
      <div className="app-frame">
        {stage !== "home" ? (
          <header className="topbar shell-card">
            <button className="brand-mark-button" onClick={() => setStage("home")} aria-label="Go to home">
              <img className="brand-mark" src="/nullcs-logo-cropped.png" alt="NullCS" />
            </button>
            <div className="topbar-actions">
              <nav className="nav-tabs">
                <button className="nav-tab" onClick={() => setStage("home")}>Home</button>
                <button className={stage === "results" ? "nav-tab active" : "nav-tab"} onClick={() => players.length && setStage("results")} disabled={!players.length}>Players</button>
                <button className={stage === "report" ? "nav-tab active" : "nav-tab"} onClick={() => report && setStage("report")} disabled={!report}>Report</button>
                <button className={stage === "about" ? "nav-tab active" : "nav-tab"} onClick={() => setStage("about")}>About</button>
              </nav>
              <label className="toggle-chip"><input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} /><span>Reduced motion</span></label>
            </div>
          </header>
        ) : null}
        {banner ? <section className={`shell-card banner ${banner.cls}`}><div><div className="eyebrow">{banner.title}</div><p>{banner.body}</p></div><button className="button button-secondary" onClick={loadSampleWalkthrough}>Open sample</button></section> : null}
        <AnimatePresence mode="wait">
          {stage === "home" ? (
            <motion.section key="home" initial={{ opacity: 0, y: 20, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -18, filter: "blur(8px)" }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} className="page-grid home-stage">
              <article className="immersive-hero shell-card">
                <div className="hero-bg-stack" aria-hidden>
                  <div className="hero-bg hero-bg-base" />
                  <div className="hero-bg hero-bg-image" />
                  <div className="hero-bg hero-bg-grid" />
                  <div className="hero-bg hero-bg-vignette" />
                  <div className="hero-bg hero-bg-glow" />
                </div>
                <Suspense fallback={<div className="cryo-scene cryo-scene-fallback" aria-hidden />}><CryoScene reducedMotion={reducedMotion} /></Suspense>
                <AntigravityField reducedMotion={reducedMotion} />
                <div className="hero-overlay-grid">
                  <motion.div className="hero-homebar shell-card" initial={{ opacity: 0, y: -18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55 }}>
                    <button className="brand-mark-button brand-mark-button-hero" onClick={() => setStage("home")} aria-label="Go to home">
                      <img className="brand-mark" src="/nullcs-logo-cropped.png" alt="NullCS" />
                    </button>
                    <div className="topbar-actions">
                      <nav className="nav-tabs">
                        <button className="nav-tab active" onClick={() => setStage("home")}>Home</button>
                        <button className="nav-tab" onClick={() => players.length && setStage("results")} disabled={!players.length}>Players</button>
                        <button className="nav-tab" onClick={() => report && setStage("report")} disabled={!report}>Report</button>
                        <button className="nav-tab" onClick={() => setStage("about")}>About</button>
                      </nav>
                      <label className="toggle-chip"><input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} /><span>Reduced motion</span></label>
                    </div>
                  </motion.div>
                  <div className="hero-center-copy">
                    <motion.span className="hero-tag" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08 }}>Research preview</motion.span>
                    <MetallicLogo reducedMotion={reducedMotion} />
                    <motion.p className="hero-summary" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.28 }}>Match-relative behavioral review with explainable evidence and neutral analysis.</motion.p>
                    <motion.p className="hero-launch-note" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.34 }}>Public website launch planned for summer 2026. Full analysis remains local or private during the research phase.</motion.p>
                    <motion.div className="button-row hero-action-row" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.4 }}>
                      <button className="button button-primary" onClick={() => document.getElementById("demo-intake")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" })}>Enter review intake</button>
                      <button className="button button-secondary" onClick={loadSampleWalkthrough}>View sample</button>
                    </motion.div>
                    <div className="hero-stat-rail">
                      {heroStats.map((stat, index) => (
                        <motion.article key={stat.label} className="hero-rail-card glass-card glare-panel" initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.42, delay: 0.5 + index * 0.08 }}>
                          <span className="eyebrow">{stat.label}</span>
                          <strong>{stat.value}</strong>
                          <p>{stat.note}</p>
                        </motion.article>
                      ))}
                    </div>
                  </div>
                </div>
                <button className="scroll-cue" onClick={() => document.getElementById("demo-intake")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" })}>
                  Scroll to intake
                </button>
              </article>
              <section className="home-lower-grid" id="demo-intake">
                <article className="upload-shell shell-card intake-card">
                  <div className="section-heading"><div><span className="eyebrow">Demo intake</span><h3>Launch a fresh review</h3><p className="muted small">Upload one demo, score the full lobby, and open player-level review artifacts.</p></div><span className="muted small">{backendHealth?.max_upload_bytes ? `${Math.round(backendHealth.max_upload_bytes / (1024 * 1024))} MB limit` : "No configured limit"}</span></div>
                  <input className="field" placeholder="Optional case label" value={demoId} onChange={(e) => setDemoId(e.target.value)} disabled={!publicUploadAvailable} />
                  <label className="upload-zone upload-zone-ice">
                    <input type="file" accept=".dem" onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={!publicUploadAvailable} />
                    <span className="upload-title">{file ? file.name : "Drop a demo here or click to browse"}</span>
                    <span className="muted small">This run preserves evidence files, score traces, and explainable report outputs for analyst review.</span>
                  </label>
                  <div className="button-row">
                    <button className="button button-primary" onClick={onUploadAndRun} disabled={!file || !publicUploadAvailable}>Run pipeline</button>
                    <button className="button button-secondary" onClick={loadSampleWalkthrough}>Sample walkthrough</button>
                  </div>
                </article>
                <article className="shell-card home-story-card">
                  <div className="section-heading"><div><span className="eyebrow">About</span><h3>Built for single-match behavioral review</h3></div></div>
                  <div className="story-grid">
                    <div className="about-card glass-card glare-panel"><strong>Match-relative triage</strong><p>Players are surfaced relative to the lobby they were in, not as a standalone cheating verdict.</p></div>
                    <div className="about-card glass-card glare-panel"><strong>Explainable outputs</strong><p>Evidence tables, score traces, and player reports stay available after the first pass.</p></div>
                    <div className="about-card glass-card glare-panel"><strong>Analyst-facing workflow</strong><p>The UI is designed for review, context gathering, and neutral next-step guidance.</p></div>
                  </div>
                  <div className="button-row">
                    <button className="button button-secondary" onClick={() => setStage("about")}>Open about page</button>
                  </div>
                </article>
              </section>
            </motion.section>
          ) : null}
          {stage === "about" ? (
            <motion.section
              key="about"
              initial={{ opacity: 0, y: 20, filter: "blur(6px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -18, filter: "blur(8px)" }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="page-grid about-page-stage"
            >
              <article className="about-hero shell-card">
                <div className="about-hero-bg" aria-hidden />
                <div className="about-hero-vignette" aria-hidden />
                <div className="about-hero-grid">
                  <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
                    <span className="hero-tag">About NullCS</span>
                  </motion.div>
                  <motion.div className="about-copy-block" initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, delay: 0.08 }}>
                    <h2>Neutral single-match analysis for behavioral review.</h2>
                    <p>
                      NullCS is a match-relative review workspace built to help surface the players who stand out the most inside one demo. It focuses on behavioral shape and context, then presents the result in a way that stays readable for a human reviewer.
                    </p>
                    <p>
                      The goal is simple: reduce noise, point attention in the right direction, and make follow-up review faster. The goal is not to hide behind a black box or pretend a single score can replace judgment.
                    </p>
                    <p>
                      The public-facing site is planned as a summer 2026 research preview. It is meant to communicate the workflow and findings responsibly without exposing private data, local artifacts, or sensitive implementation details.
                    </p>
                  </motion.div>
                  <div className="about-pillar-grid">
                    {ABOUT_PILLARS.map((pillar, index) => (
                      <motion.article
                        key={pillar.title}
                        className="about-pillar glass-card glare-panel"
                        initial={{ opacity: 0, y: 24 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.45, delay: 0.16 + index * 0.08 }}
                      >
                        <span className="eyebrow">Principle {String(index + 1).padStart(2, "0")}</span>
                        <h3>{pillar.title}</h3>
                        <p>{pillar.body}</p>
                      </motion.article>
                    ))}
                  </div>
                </div>
              </article>
              <section className="about-content-grid">
                <motion.article className="shell-card about-panel about-panel-large" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.22 }}>
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">What It Does</span>
                      <h3>Keeps the workflow understandable</h3>
                    </div>
                  </div>
                  <div className="about-prose">
                    <p>
                      NullCS does not rely on one headline stat. It reads a wide stack of behavioral signals from the same match, including timing, visibility pressure, movement state, encounter structure, mechanical stability, and how clean a player stays when ordinary play should start to break down.
                    </p>
                    <p>
                      The system has been shaped against demos spanning wide skill levels, including strong legitimate players, pro-level gameplay, and many known cheater matches. It is a research project built around a simple idea: even modern cheats still disturb play in ways that can be broken down into fine-grained signals and separated from strong legitimate performance. The goal is not to collapse all of that into a magic verdict. The goal is to surface the strongest standouts, preserve useful evidence, and make the first review pass much more focused.
                    </p>
                  </div>
                </motion.article>
                <motion.article className="shell-card about-panel" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.28 }}>
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">How Review Flows</span>
                      <h3>From one demo to a clearer next step</h3>
                    </div>
                  </div>
                  <div className="about-step-list">
                    {ABOUT_STEPS.map((step, index) => (
                      <div key={step} className="about-step-row">
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <p>{step}</p>
                      </div>
                    ))}
                  </div>
                </motion.article>
                <motion.article className="shell-card about-panel" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.34 }}>
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">Why It Exists</span>
                      <h3>Built to cut through noisy lobbies</h3>
                    </div>
                  </div>
                  <div className="about-prose">
                    <p>
                      Competitive demos are noisy. Some strong players look extreme in one match, some suspicious players hide in ordinary scorelines, and context can make quick judgments misleading. NullCS explores a different angle from broad platform-side enforcement systems by concentrating on explainable, match-level behavioral separation.
                    </p>
                    <p>
                      The project exists to test whether those patterns can still be measured in enough detail to separate suspicious play from strong or unusual legitimate play. In practice, that means helping answer three practical questions: who looks ordinary, who deserves a second look, and what kind of follow-up review is most useful next.
                    </p>
                  </div>
                </motion.article>
              </section>
            </motion.section>
          ) : null}
          {stage === "results" ? (
            <motion.section key="results" initial={{ opacity: 0, y: 20, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -18, filter: "blur(8px)" }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} className="page-grid results-grid">
              <aside className="leaderboard-panel shell-card">
                <div className="section-heading compact">
                  <div><span className="eyebrow">Match roster</span><h3 title={demoId || "No demo selected"}>{rosterTitle || "No demo selected"}</h3><p className="muted small mono">{demoId || ""}</p></div>
                  <input className="field compact" placeholder="Search player or SteamID" value={query} onChange={(e) => setQuery(e.target.value)} />
                </div>
                <SignalLegend />
                <div className="leaderboard-list">
                  {filteredPlayers.map((player, index) => {
                    const playerSignal = player.risk ?? player.proba_cheater_infer;
                    const playerTone = intensityTone(playerSignal);
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
                          <p className="muted small mono">{selectedPlayer?.steamid || SAMPLE_STEAMID}</p>
                          {selectedInterpretation ? <div className="overview-badges"><span className={`severity-chip tone-${intensityTone(selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer)}`}>{triageLabel(selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer, selectedRank, filteredPlayers.length || players.length || 1, selectedInterpretation.context_fit, selectedPlayer?.confidence, selectedInterpretation.global_process_anomaly)}</span><span className="overview-rank">Rank #{selectedRank} of {filteredPlayers.length || players.length || 1}</span></div> : null}
                        </motion.div>
                      </AnimatePresence>
                    </div>
                    {selectedPlayer ? (
                      <div className="button-row">
                        <a className="button button-secondary" href={steamCommunityUrl(selectedPlayer.steamid)} target="_blank" rel="noreferrer">Steam</a>
                        <a className="button button-secondary" href={csStatsUrl(selectedPlayer.steamid)} target="_blank" rel="noreferrer">CSStats</a>
                        <button className="button button-primary" onClick={() => void openReport(selectedPlayer.steamid)}>Open report</button>
                      </div>
                    ) : null}
                  </div>
                  <div className="overview-disclaimer">Signal is match-relative. Use it to decide who to look at first, not as a verdict.</div>
                  {renderInterpretationDeck(selectedInterpretation, selectedPlayer?.risk ?? selectedPlayer?.proba_cheater_infer, selectedPlayer?.confidence, selectedUncertaintyLabel)}
                </section>
              </div>
            </motion.section>
          ) : null}
          {stage === "report" ? (
            <motion.section key="report" initial={{ opacity: 0, y: 20, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -18, filter: "blur(8px)" }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} className="page-grid report-grid">
              <section className="report-header shell-card">
                <div>
                  <span className="eyebrow">Player report</span>
                  <h2>{report?.player.attacker_name || selectedPlayer?.attacker_name || "Unknown player"}</h2>
                  <p className="muted small mono">{report?.player.attacker_steamid || selectedSteamid || SAMPLE_STEAMID}</p>
                </div>
                <div className="button-row"><button className="button button-secondary" onClick={() => setStage("results")}>Back to players</button></div>
              </section>
              <aside className="report-sidebar shell-card">
                <div className="nav-stack">
                  {(["overview", "reasons", "trace"] as ReportTab[]).map((tab) => <button key={tab} className={reportTab === tab ? "stack-tab active" : "stack-tab"} onClick={() => setReportTab(tab)}>{cap(tab)}</button>)}
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
                  </div>
                ) : null}
                {reportTab === "trace" ? (
                  <div className="trace-layout">
                    <article className="glass-card">
                      <div className="section-heading compact"><div><span className="eyebrow">Model support</span><h3>Runtime execution</h3><p className="muted small">These values stay secondary to the interpretation, but they show what the model actually saw.</p></div></div>
                      <div className="trace-grid">
                        <MetricCard label="Raw model output" raw={scoreTrace?.raw_proba ?? null} display={pct(scoreTrace?.raw_proba)} hint="before calibration" tone={metricTone("risk", scoreTrace?.raw_proba ?? null)} />
                        <MetricCard label="Served output" raw={scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null} display={pct(scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null)} hint="secondary support metric" tone={metricTone("risk", scoreTrace?.calibrated_proba ?? report?.risk.calibrated_probability ?? null)} />
                        <article className="metric-card tone-neutral"><div className="metric-meta"><span className="eyebrow">Model version</span></div><strong className="metric-value meta-value">{scoreTrace?.model_version || "--"}</strong><span className="metric-hint">runtime artifact</span></article>
                        <article className="metric-card tone-neutral"><div className="metric-meta"><span className="eyebrow">Feature list</span></div><strong className="metric-value meta-value">{scoreTrace?.feature_list_version || "--"}</strong><span className="metric-hint">model input schema</span></article>
                      </div>
                    </article>
                    <article className="glass-card">
                      <div className="section-heading compact"><div><span className="eyebrow">Model-facing features</span><h3>Process support</h3><p className="muted small">Focus on the process metrics that now matter most for player reporting.</p></div></div>
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
















