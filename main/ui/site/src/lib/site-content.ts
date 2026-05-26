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
  { href: "/#pipeline", label: "Pipeline" },
  { href: "/#proof", label: "Benchmarks" },
  { href: "/about", label: "About" },
] as const;

export const heroMetrics = [
  { label: "Input", value: "CS2 demo files parsed into event and encounter data" },
  { label: "Modeling", value: "281,792 encounter rows feed temporal and player-level signals" },
  { label: "Output", value: "Ranked review signals with reasons, not verdicts" },
] as const;

export const benchmarkStats = [
  { label: "Suspicious median top-ranked signal", value: "0.030" },
  { label: "Normal legit median top-ranked signal", value: "0.0031" },
  { label: "Pro stress-test median top-ranked signal", value: "0.0034" },
  { label: "Suspicious top-3 retrieval", value: "0.875" },
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
    title: "Structure the demo",
    body: "Raw .dem files become event, engagement, and encounter data that can be compared across matches.",
    icon: Binary,
  },
  {
    label: "Step 02",
    title: "Measure behavior",
    body: "Timing, visibility, aim process, mouse movement, and control-path features are built around each engagement.",
    icon: Activity,
  },
  {
    label: "Step 03",
    title: "Rank for review",
    body: "The model surfaces players and moments that stand out inside the match, then exports evidence for inspection.",
    icon: ChartColumnBig,
  },
] as const;

export const reviewPrinciples = [
  {
    title: "Not A Verdict",
    body: "Scores are review signals, not enforcement decisions.",
  },
  {
    title: "Hard Cases",
    body: "The system is designed around subtle behavior, not only obvious clips.",
  },
  {
    title: "Quiet Baselines",
    body: "Legit and pro slices are tracked so the model does not become noisy.",
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
  "Public benchmark plots show where suspicious slices separate from legit and pro baselines.",
  "Explainability artifacts keep the review focused on what raised the signal.",
  "Research is ongoing, so the site presents evidence and limits instead of a solved-problem claim.",
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
    "Behavioral review research for Counter-Strike 2 demos, built around structured analysis, explainable signals, and ML-driven triage.",
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
    eyebrow: "Control path",
    title: "Usercmd-derived mouse and crosshair behavior diverge across suspicious, normal, and pro benchmark slices",
    body: "These panels come from mouse-delta and crosshair-process aggregates built out of encounter windows. They show why control-path telemetry matters: suspicious slices are not just louder in score space, they behave differently in input and aim process too.",
    image: "/assets/proof-pack/control_path_bucket_boxplots.png",
  },
  {
    eyebrow: "Control features",
    title: "Input-stability, mouse-delta, and angular-jerk features carry real separating power on their own",
    body: "This is not a one-metric story. Usercmd-derived mouse behavior, quiet-after-acquire behavior, and angular-jerk features all show measurable lift by themselves before they are folded into the full ranking model.",
    image: "/assets/proof-pack/control_path_feature_auc.png",
  },
  {
    eyebrow: "Training scale",
    title: "The current stack is trained on roughly one thousand matches, which expands into hundreds of thousands of modeled encounters",
    body: "The data scale matters because a single CS2 match is not one row. It becomes many encounter windows, control-path sequences, player aggregates, and benchmark slices. That is what allows the model to study hard cases instead of just memorizing clips.",
    image: "/assets/proof-pack/training_data_scale.png",
  },
] as const;

export const proofExample = {
  eyebrow: "Granular example",
  title: "Control-path features help inspect whether a player is efficient in a way that deserves review, not just loud.",
  body: "This benchmark example is built from encounter-level mouse and crosshair-process aggregates. Normal players tend to be coarser and noisier, pros tend to be more efficient, and suspicious slices can start looking efficient in a different way: less corrective burst, less manual oversteer, and cleaner settling than expected for the difficulty of the encounter. That is the kind of control-path evidence NullCS is trying to surface.",
  caption:
    "The key point is not that one bar settles a case. It is that NullCS can inspect the process behind the aim, not just the outcome.",
  image: "/assets/proof-pack/top1_control_band_comparison.png",
} as const;
