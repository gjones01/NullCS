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
  process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/gjones01/NullCS";

export const navItems = [
  { href: "/", label: "Overview" },
  { href: "/#pipeline", label: "Pipeline" },
  { href: "/#proof", label: "Benchmarks" },
  { href: "/about", label: "About" },
] as const;

export const heroMetrics = [
  { label: "Dataset", value: "894 demos and 281,792 encounter windows in the current public benchmark" },
  { label: "Features", value: "35 temporal CNN channels plus 449 player-demo ranking features" },
  { label: "Output", value: "Ranked review signals with reasons, not verdicts or ban decisions" },
] as const;

export const benchmarkStats = [
  { label: "Player-level ROC-AUC", value: "0.956" },
  { label: "Player-level PR-AUC", value: "0.796" },
  { label: "Suspicious player top-1", value: "92.8%" },
  { label: "Suspicious player top-3", value: "97.3%" },
] as const;

export const featureCards = [
  {
    title: "Demo input",
    body: "Counter-Strike 2 demos are parsed into event, engagement, and encounter structure instead of being judged from clip-level moments or surface stats.",
    icon: Binary,
  },
  {
    title: "Behavior signals",
    body: "The current stack builds hundreds of player-level signals plus deeper encounter timing channels from usercmd-style mouse deltas, view-angle response, aim collapse, angular jerk, and recoil-settling behavior.",
    icon: Radar,
  },
  {
    title: "Match-relative ranking",
    body: "Models rank players inside a demo so standouts can be surfaced in context instead of pretending one metric can settle the case alone.",
    icon: ShieldCheck,
  },
  {
    title: "Evidence output",
    body: "Scores are paired with reasons and benchmark context so the output can support review, especially when strong legitimate play and irregular patterns start to overlap.",
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
    title: "Control-path telemetry",
    body: "The stack can follow usercmd-derived mouse behavior, how those inputs translate into view-angle movement, crosshair acceleration, aim collapse, and post-acquire settling.",
    icon: Activity,
  },
  {
    title: "Analyst-readable output",
    body: "The goal is a useful review surface: ranked players, evidence, and context that stays interpretable under scrutiny.",
    icon: BookOpenText,
  },
] as const;

export const pipelineSteps = [
  {
    label: "Step 01",
    title: "Parse tick-level telemetry",
    body: "Raw .dem files become event tables, player state, visibility markers, shots, damage, kills, and round context.",
    icon: Binary,
  },
  {
    label: "Step 02",
    title: "Build encounter windows",
    body: "Each engagement is represented as a 32-tick temporal sequence with aim, mouse, visibility, movement, shot, and damage channels.",
    icon: Activity,
  },
  {
    label: "Step 03",
    title: "Rank players for review",
    body: "CNN encounter scores and 449 player-demo features feed a grouped XGBoost model that ranks players inside the match.",
    icon: ChartColumnBig,
  },
] as const;

export const actualFindings = [
  {
    title: "Aim Correction",
    body: "Positive rows show cleaner pre-shot stabilization in several aim-process summaries, including lower pre-shot aim-error variance.",
  },
  {
    title: "Visibility Timing",
    body: "Prefire-like rifle timing and long-range fast-reaction rates separate a subset of suspicious rows from the negative baseline.",
  },
  {
    title: "Encounter Clusters",
    body: "51.5% of positive encounter windows score at or above 0.75, compared with 3.6% of negative windows.",
  },
] as const;

export const workflowSteps = [
  {
    step: "01",
    title: "Parse and structure",
    body: "Raw demos are turned into event, engagement, and encounter data. A single match expands into hundreds of encounter windows and thousands of tick-aligned measurements before ranking begins.",
    icon: GitBranch,
  },
  {
    step: "02",
    title: "Build hundreds of behavior signals",
    body: "The current stack uses 449 player-level engineered features, plus encounter timing and control-path channels built from mouse delta, aim process, visibility transitions, and crosshair movement.",
    icon: Bot,
  },
  {
    step: "03",
    title: "Rank and document",
    body: "Models rank standouts inside a match and export evidence meant to support careful review, especially when the case is not obvious.",
    icon: ArrowUpRight,
  },
] as const;

export const credibilityNotes = [
  "Grouped evaluation uses demo_id splits so one match does not leak across train and validation folds.",
  "The model still produces false positives, especially in headshot-heavy high-support matches.",
  "Scores are review priority, not enforcement probability.",
] as const;

export const aboutPrinciples = [
  {
    title: "Behavior first",
    body: "NullCS studies how players behave inside real encounters. The emphasis is on measurable structure around timing, visibility, movement pressure, and shot process.",
  },
  {
    title: "Hard cases over easy clips",
    body: "Obvious abuse is usually the easy case. The more important challenge is lower-visibility irregular behavior that can sit close to strong legitimate play on first glance.",
  },
  {
    title: "Explainability matters",
    body: "Outputs are meant to stay understandable enough that a reviewer can inspect the signal instead of trusting a black box, and the project does not present itself as universal detection.",
  },
] as const;

export const footerLinks = [
  { href: githubUrl, label: "GitHub" },
  { href: "/about", label: "About" },
] as const;

export const siteMetadata = {
  title: "NullCS",
  description:
    "Behavioral anomaly research for Counter-Strike 2 demos, built around tick-level telemetry, encounter windows, and ranked review signals.",
};

export const screenshotSlots = [
  {
    eyebrow: "Research Artifact",
    title: "Review-oriented output surface",
    body: "Interface captures are treated as supporting artifacts for inspecting rankings, evidence, and benchmark context.",
    image: "/assets/UIPopUp.PNG",
  },
  {
    eyebrow: "Research Surface",
    title: "Benchmark-ready layout",
    body: "These panels can carry benchmark plots, model outputs, and deeper behavioral visualizations without redesigning the page.",
    image: "/assets/aboutpagebg.png",
  },
] as const;

export const proofCards = [
  {
    eyebrow: "Benchmark slices",
    title: "Grouped player-level evaluation reaches ROC-AUC 0.956 and PR-AUC 0.796",
    body: "The current CS2CD player-level readout covers 860 demos after filtering, with 992 positive and 5,894 negative player-demo rows.",
    image: "/assets/proof-pack/benchmark_top1_distribution.png",
  },
  {
    eyebrow: "Per-demo surface",
    title: "The labeled suspicious player ranks top-1 in 92.8% of suspicious demos",
    body: "Top-3 retrieval is 97.3% across 293 demos with a suspicious player label, which is the core review-triage metric.",
    image: "/assets/proof-pack/benchmark_top1_vs_top3_scatter.png",
  },
  {
    eyebrow: "Control path",
    title: "Encounter-model scores separate positive windows from negative windows",
    body: "Median CNN score is 0.769 for positive windows and 0.188 for negative windows. The model is seeing repeatable encounter-level structure.",
    image: "/assets/proof-pack/control_path_bucket_boxplots.png",
  },
  {
    eyebrow: "Control features",
    title: "Fast rifle timing, prefire-like rates, and headshot concentration are visible but insufficient alone",
    body: "Feature separation is strongest when timing, aim process, input stability, visibility, and encounter-model summaries are combined.",
    image: "/assets/proof-pack/control_path_feature_auc.png",
  },
  {
    eyebrow: "Training scale",
    title: "A single match expands into many encounter windows and player-level aggregates",
    body: "The benchmark contains 281,792 encounter windows and 6,886 evaluated player-demo rows after filtering.",
    image: "/assets/proof-pack/training_data_scale.png",
  },
] as const;

export const proofExample = {
  eyebrow: "Granular example",
  title: "Some signals are lower-noise process measurements, not dramatic snaps.",
  body: "Positive rows show lower medians on several stabilization features, including pre-shot aim-error variance and early snap-jerk summaries. That does not prove a cheat type. It tells a reviewer where the engagement process looks unusually clean for the surrounding context.",
  caption:
    "The useful output is an inspectable reason to review the demo, not a final label.",
  image: "/assets/proof-pack/top1_control_band_comparison.png",
} as const;
