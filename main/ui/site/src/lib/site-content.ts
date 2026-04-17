import {
  Activity,
  ArrowUpRight,
  Binary,
  BookOpenText,
  Bot,
  ChartColumnBig,
  Crosshair,
  GitBranch,
  Radar,
  ShieldCheck,
} from "lucide-react";

export const githubUrl =
  process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/gjones01/NullCS.ai";

export const navItems = [
  { href: "/", label: "Overview" },
  { href: "/#capabilities", label: "Capabilities" },
  { href: "/#proof", label: "Proof" },
  { href: "/#workflow", label: "Workflow" },
  { href: "/beta", label: "Beta" },
  { href: "/client", label: "Client" },
  { href: "/about", label: "About" },
] as const;

export const heroMetrics = [
  { label: "Engineered Features", value: "449 player-level signals in the current CS2 stack" },
  { label: "Benchmark Shape", value: "Quiet on legit and pro slices, louder on suspicious demos" },
  { label: "Review Output", value: "Explainable, match-relative triage instead of verdict language" },
] as const;

export const benchmarkStats = [
  { label: "Suspicious median top-ranked signal", value: "0.748" },
  { label: "Normal legit median top-ranked signal", value: "0.0073" },
  { label: "Pro stress-test median top-ranked signal", value: "0.0073" },
  { label: "Suspicious top-3 retrieval", value: "0.90" },
] as const;

export const featureCards = [
  {
    title: "Structured demo analysis",
    body: "NullCS works from parsed Counter-Strike 2 demo structure instead of surface-level highlight stats or clip-driven heuristics.",
    icon: Binary,
  },
  {
    title: "Subtle behavior review",
    body: "The hard problem is not catching obvious spinbot footage. The harder problem is separating strong legitimate play from lower-visibility assist behavior and info abuse.",
    icon: Radar,
  },
  {
    title: "Explainable outputs",
    body: "Signals are paired with reasons, supporting slices, and evidence views designed for analyst review rather than one-click certainty.",
    icon: ShieldCheck,
  },
  {
    title: "False-positive pressure matters",
    body: "One of the central goals is staying restrained on high-ELO and pro-level legitimate play, because an overconfident model is not useful review software.",
    icon: ChartColumnBig,
  },
] as const;

export const capabilityBands = [
  {
    title: "Encounter timing review",
    body: "Tracks visibility-to-shot windows, pressure moments, and response patterns across kill events.",
    icon: Crosshair,
  },
  {
    title: "Match-relative scoring",
    body: "Ranks players within a demo so suspicious standouts can be surfaced for deeper review.",
    icon: Activity,
  },
  {
    title: "Evidence-oriented reporting",
    body: "Designed to support judgment, not replace it, with explainability kept central to the workflow.",
    icon: BookOpenText,
  },
] as const;

export const workflowSteps = [
  {
    step: "01",
    title: "Parse and structure",
    body: "Raw demos are transformed into event, engagement, and encounter data that can be analyzed consistently across players and rounds.",
    icon: GitBranch,
  },
  {
    step: "02",
    title: "Build hundreds of behavior signals",
    body: "The current public stack uses 449 player-level engineered features, with encounter-level timing and process channels feeding deeper model paths.",
    icon: Bot,
  },
  {
    step: "03",
    title: "Score and explain",
    body: "Models rank standouts inside a match and export evidence meant to support careful review, not universal cheat claims.",
    icon: ArrowUpRight,
  },
] as const;

export const credibilityNotes = [
  "Current public-safe benchmark shape: suspicious demos rise clearly while held-out legit and pro slices stay compressed near zero",
  "The project is strongest when it reduces false positives on strong legitimate play instead of simply getting louder everywhere",
  "NullCS does not claim to detect every cheat type or replace human judgment",
] as const;

export const aboutPrinciples = [
  {
    title: "Behavior first",
    body: "NullCS studies how players behave inside real encounters. The emphasis is on measurable structure around timing, visibility, movement pressure, and shot process.",
  },
  {
    title: "Hard cases over easy clips",
    body: "Blatant aimbot or spinbot footage is usually the easy case. The more important challenge is lower-visibility aim assist, recoil assist, and information advantage that does not scream on first glance.",
  },
  {
    title: "Explainability matters",
    body: "Outputs are meant to stay understandable enough that a reviewer can inspect the signal instead of trusting a black box, and the project does not present itself as universal cheat detection.",
  },
] as const;

export const footerLinks = [
  { href: githubUrl, label: "GitHub" },
  { href: "/beta", label: "Beta" },
  { href: "/client", label: "Client" },
  { href: "/about", label: "About" },
] as const;

export const siteMetadata = {
  title: "NullCS",
  description:
    "Behavioral review research for Counter-Strike 2 demos, built around structured analysis, explainable signals, and ML-driven triage.",
};

export const screenshotSlots = [
  {
    eyebrow: "Interface Preview",
    title: "Desktop review surface",
    body: "The homepage reserves space for real client previews, benchmark panels, and evidence views instead of decorative filler.",
    image: "/assets/UIPopUp.PNG",
  },
  {
    eyebrow: "Research Surface",
    title: "Proof-ready layout",
    body: "These panels can carry benchmark plots, model outputs, and deeper behavioral visualizations without redesigning the page.",
    image: "/assets/aboutpagebg.png",
  },
] as const;

export const proofCards = [
  {
    eyebrow: "Benchmark slices",
    title: "Top-ranked demo signal separates suspicious slices from legit and pro holdouts",
    body: "Each box summarizes the distribution of the highest-ranked player signal per demo within a benchmark slice. The important result is not just that suspicious demos shift upward, but that the legit and pro stress-test slices remain compressed near zero instead of inflating under skill. For a review model, that is the core credibility condition: separation without broad false-positive drift.",
    image: "/assets/proof-pack/benchmark_top1_distribution.png",
  },
  {
    eyebrow: "Per-demo surface",
    title: "Top-1 and top-3 demo aggregates separate suspicious lobbies from quiet baselines",
    body: "The x-axis is the strongest player score in a demo and the y-axis is the mean of the top three player scores. Suspicious demos move up and to the right, while normal legit and pro demos remain clustered near the origin. That matters because it shows the signal is not carried only by a single outlier row; the upper part of the lobby is coherently louder in suspicious matches.",
    image: "/assets/proof-pack/benchmark_top1_vs_top3_scatter.png",
  },
  {
    eyebrow: "Behavior space",
    title: "OOF behavior-space separation is meaningful without pretending the classes are trivially separable",
    body: "This out-of-fold scatter combines two behavior channels: encounter-model score on the x-axis and process abnormality on the y-axis. Most of the class separation is being carried by the x-axis, while the y-axis adds secondary structure rather than a perfectly clean split. For experienced ML readers, that is a healthier sign than a suspiciously perfect 2D separation: the model is finding signal, but the problem still looks like a hard behavioral classification problem.",
    image: "/assets/proof-pack/oof_behavior_scatter.png",
  },
  {
    eyebrow: "Threshold policy",
    title: "Threshold choice trades false-positive restraint against suspicious-case coverage",
    body: "This plot shows the expected precision-recall tradeoff as the decision threshold becomes stricter. Raising the threshold improves precision, which is important when strong legit or pro players must stay unflagged, but it reduces recall and therefore lowers coverage of suspicious cases. The significance is operational: NullCS is better thought of as a tunable review-prioritization system than a fixed binary detector.",
    image: "/assets/proof-pack/threshold_tradeoff.png",
  },
] as const;

export const clientRoadmap = [
  "Local demo review workflow",
  "Evidence browsing and ranked player inspection",
  "Future download delivery once the review client is ready",
] as const;
