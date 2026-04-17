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
  { label: "Benchmark Shape", value: "Suspicious slices rise while legit and pro stress-test slices stay quiet" },
  { label: "Review Output", value: "Ranked players, evidence, and reasons for review instead of verdict language" },
] as const;

export const benchmarkStats = [
  { label: "Suspicious median top-ranked signal", value: "0.748" },
  { label: "Normal legit median top-ranked signal", value: "0.0073" },
  { label: "Pro stress-test median top-ranked signal", value: "0.0073" },
  { label: "Suspicious top-3 retrieval", value: "0.90" },
] as const;

export const featureCards = [
  {
    title: "Demo input",
    body: "Counter-Strike 2 demos are parsed into event, engagement, and encounter structure instead of being judged from clip-level moments or surface stats.",
    icon: Binary,
  },
  {
    title: "Behavior signals",
    body: "The current stack builds hundreds of player-level signals plus deeper encounter timing channels to study how suspicious behavior unfolds inside real rounds.",
    icon: Radar,
  },
  {
    title: "Match-relative ranking",
    body: "Models rank players inside a demo so standouts can be surfaced in context instead of pretending one metric can settle the case alone.",
    icon: ShieldCheck,
  },
  {
    title: "Evidence output",
    body: "Scores are paired with reasons and benchmark context so the output can support review, especially when strong legitimate play and subtle cheats start to overlap.",
    icon: ChartColumnBig,
  },
] as const;

export const capabilityBands = [
  {
    title: "Structured inputs",
    body: "Demos are normalized into comparable event and encounter data before any ranking is produced.",
    icon: Crosshair,
  },
  {
    title: "Behavior-first scoring",
    body: "The stack studies timing, aim process, visibility pressure, and context instead of leaning on one loud metric.",
    icon: Activity,
  },
  {
    title: "Analyst-readable output",
    body: "The goal is a useful review surface: ranked players, evidence, and context that stays interpretable under scrutiny.",
    icon: BookOpenText,
  },
] as const;

export const workflowSteps = [
  {
    step: "01",
    title: "Parse and structure",
    body: "Raw demos are turned into event, engagement, and encounter data that can be compared consistently across players and rounds.",
    icon: GitBranch,
  },
  {
    step: "02",
    title: "Build hundreds of behavior signals",
    body: "The current stack uses 449 player-level engineered features, plus encounter timing and control-path channels feeding deeper model paths.",
    icon: Bot,
  },
  {
    step: "03",
    title: "Score and explain",
    body: "Models rank standouts inside a match and export evidence meant to support careful review, especially when the case is not obvious.",
    icon: ArrowUpRight,
  },
] as const;

export const credibilityNotes = [
  "Some demo metrics can scream that something is wrong, but that does not automatically settle the case on its own.",
  "The real pressure test is whether suspicious slices rise without inflating strong legitimate and pro-level play at the same time.",
  "Research is still ongoing. The current result is serious progress, not a claim that the problem is solved.",
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
    body: "The strongest player signal in suspicious demos shifts upward, while held-out legit and pro slices stay compressed near zero. That is the core credibility test: separation without broad false-positive drift.",
    image: "/assets/proof-pack/benchmark_top1_distribution.png",
  },
  {
    eyebrow: "Per-demo surface",
    title: "Top-1 and top-3 demo aggregates separate suspicious lobbies from quiet baselines",
    body: "Suspicious demos move up and to the right, while legit and pro demos stay near the origin. That matters because the signal is not just one loud outlier; the top of the lobby is coherently louder.",
    image: "/assets/proof-pack/benchmark_top1_vs_top3_scatter.png",
  },
  {
    eyebrow: "Behavior space",
    title: "OOF behavior-space separation is meaningful without pretending the classes are trivially separable",
    body: "The encounter-model channel carries most of the separation while the second axis adds supporting structure. That is a healthier picture than a fake-clean split: there is real signal, but the problem still behaves like a hard classification problem.",
    image: "/assets/proof-pack/oof_behavior_scatter.png",
  },
  {
    eyebrow: "Threshold policy",
    title: "Threshold choice trades false-positive restraint against suspicious-case coverage",
    body: "A stricter threshold improves precision but reduces coverage. Operationally, this means NullCS behaves more like a tunable review-prioritization system than a fixed binary detector.",
    image: "/assets/proof-pack/threshold_tradeoff.png",
  },
] as const;

export const clientRoadmap = [
  "Local demo review workflow",
  "Evidence browsing and ranked player inspection",
  "Future download delivery once the review client is ready",
] as const;
