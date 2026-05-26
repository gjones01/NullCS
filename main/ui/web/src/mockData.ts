import type { EvidenceTable, ExplainReport, InterpretationModel, PlayerRow, Reason, ScoreTrace } from "./lib/api";

export const SAMPLE_DEMO_ID = "DEMO_SAMPLE";
export const SAMPLE_STEAMID = "76561190000000001";

const SAMPLE_INTERPRETATION: InterpretationModel = {
  archetype: {
    label: "Info-leaning anomaly",
    summary: "Deviation is driven more by timing and low-visibility sequences than by raw aim alone.",
  },
  behavior_profile: {
    headline: "Stands out mostly through first-contact timing and occlusion-heavy fights.",
    summary: "The player separates from this lobby through early-shot timing, selective low-visibility kills, and a concentrated set of standout engagements rather than broad mechanical dominance.",
  },
  match_profile: {
    summary: "Ranked #1 of 10 in this lobby. The standout shape comes from actual per-match event structure rather than a generic leaderboard score.",
    stats: [
      { key: "rank", label: "Lobby standing", value: 0.1, display_value: "#1/10", summary: "Match-relative position only." },
      { key: "lobby_percentile", label: "Lobby percentile", value: 1, display_value: "100.0%", summary: "Closer to the top of this match-relative review order." },
      { key: "kills", label: "Kills in sample", value: 14, display_value: "14", summary: "Kill rows available for this player in the sample." },
      { key: "encounters", label: "Encounters in sample", value: 31, display_value: "31", summary: "Encounter rows available for context checks." },
      { key: "rounds", label: "Rounds with kills", value: 8, display_value: "8", summary: "How many rounds contribute to the player profile." },
      { key: "rt_support", label: "RT-supported kills", value: 11, display_value: "11", summary: "Events with usable visibility-to-shot timing support." },
    ],
    relative_markers: [
      { key: "prefire_pct", label: "Prefire percentile", value: 0.95, display_value: "95.0%", summary: "Relative to this lobby's prefire distribution." },
      { key: "rt_median_pct", label: "Timing percentile", value: 0.89, display_value: "89.0%", summary: "Relative timing position inside this match." },
      { key: "thrusmoke_pct", label: "Occlusion percentile", value: 0.63, display_value: "63.0%", summary: "Relative low-visibility separation." },
      { key: "headshot_pct", label: "Mechanical percentile", value: 0.88, display_value: "88.0%", summary: "Relative conversion proxy inside the lobby." },
      { key: "round_concentration_pct", label: "Round concentration", value: 0.74, display_value: "74.0%", summary: "Higher means the signal clusters in fewer rounds." },
      { key: "weapon_specialization_pct", label: "Weapon specialization", value: 0.57, display_value: "57.0%", summary: "Higher means a narrower weapon-shaped anomaly." },
    ],
  },
  evidence_basis: {
    summary: "Built from 14 kills, 11 RT-supported kills, and 31 encounters in this match.",
    stats: [
      { key: "kills", label: "Kill rows", value: 14, display_value: "14", summary: "Kill rows carried into the aggregate." },
      { key: "rt_n", label: "RT-supported kills", value: 11, display_value: "11", summary: "Events with usable timing support." },
      { key: "enc_n", label: "Encounter rows", value: 31, display_value: "31", summary: "Encounter-level rows used for context checks." },
      { key: "confidence", label: "Support level", value: 0.63, display_value: "63.0%", summary: "Evidence stability after sample-size effects." },
    ],
  },
  behavioral_deviation: 0.78,
  context_fit: 0.44,
  signal_stability: 0.56,
  review_priority: 0.71,
  support_level: 0.63,
  signal_components: [
    { key: "mechanics", label: "Mechanics", share: 0.19, summary: "Mechanical separation is present but not the main driver." },
    { key: "information_timing", label: "Information / timing", share: 0.33, summary: "First-contact timing and prefire shape the profile." },
    { key: "occlusion", label: "Occlusion", share: 0.24, summary: "Low-visibility kills contribute meaningfully." },
    { key: "decision_discipline", label: "Decision discipline", share: 0.12, summary: "The pattern includes selective engagements rather than constant volume." },
    { key: "concentration", label: "Stability / concentration", share: 0.12, summary: "Signal exists, but it is not evenly distributed across the match." },
  ],
  context_adjustment: {
    summary: "Some of the standout profile can be explained by strong shot conversion, but context does not fully dissolve the timing and occlusion shape.",
    remaining_signal: "mixed",
    normal_explanations: [
      { key: "skill_gap", label: "Skill gap explanation", status: "partial", weight: 0.58, summary: "Mechanical edge explains part of the separation, but not the full timing pattern." },
      { key: "opponent_pool", label: "Weak opponent pool", status: "partial", weight: 0.49, summary: "The lobby baseline looks soft enough to inflate some standout moments." },
      { key: "sample_size", label: "Sample size limitation", status: "high", weight: 0.72, summary: "The event sample is serviceable but still match-bounded." },
      { key: "map_familiarity", label: "Map familiarity", status: "limited", weight: 0.26, summary: "Map context may help with comfort, but it does not obviously explain the full shape." },
    ],
  },
  durability: {
    summary: "The signal is real enough to review, but it is concentrated rather than uniform.",
    metrics: [
      { key: "rounds", label: "Across rounds", value: 0.42, summary: "Concentrated in a narrower set of rounds than a stable carry profile." },
      { key: "halves", label: "Across halves", value: 0.54, summary: "Visible in both halves, though not equally." },
      { key: "weapons", label: "Across weapons", value: 0.39, summary: "More rifle-shaped than weapon-agnostic." },
      { key: "visibility", label: "Across visibility states", value: 0.67, summary: "Most distinct in low-visibility or compromised sightlines." },
      { key: "engagements", label: "Across engagement types", value: 0.48, summary: "Persists in first-contact fights more than in broad duel volume." },
    ],
  },
  review_lens: {
    title: "Compare low-visibility first-contact fights",
    summary: "Best follow-up is to isolate rounds where timing and partial occlusion overlap, then compare the POV sequence instead of reviewing only the final kill outcome.",
    comparisons: [
      "Compare POV in low-visibility engagements",
      "Review timing around first-contact fights",
      "Cross-check off-angle prefires with opponent POV",
    ],
  },
  limitations: [
    { label: "Match-only sample", severity: "high", summary: "This interpretation is bounded to one match and does not express longitudinal behavior." },
    { label: "Concentrated signal", severity: "medium", summary: "The standout pattern clusters in a smaller set of rounds." },
    { label: "Lobby calibration", severity: "medium", summary: "A weaker or chaotic lobby can exaggerate match-relative separation." },
  ],
  model_notes: [
    "Context fit and durability are currently heuristic-derived from available per-match features.",
    "Backend placeholders should be replaced by round-aware and opponent-aware modeling later.",
  ],
};

export const SAMPLE_PLAYERS: PlayerRow[] = [
  {
    steamid: SAMPLE_STEAMID,
    attacker_name: "SamplePlayerOne",
    proba_cheater_infer: 0.81,
    risk: 0.76,
    confidence: 0.63,
    risk_band: "review",
    features_summary: {
      rt_median: 5.4,
      prefire_rate: 0.41,
      thrusmoke_kill_rate: 0.09,
      headshot_rate: 0.58,
      long_range_fast_rt_rate_4: 0.37,
    },
    top_reasons: [
      { title: "Repeated low reaction-time kills", severity: "high" },
      { title: "High prefire rate", severity: "medium" },
    ],
    interpretation: SAMPLE_INTERPRETATION,
  },
  {
    steamid: "76561190000000002",
    attacker_name: "LobbyBaseline",
    proba_cheater_infer: 0.22,
    risk: 0.18,
    confidence: 0.71,
    risk_band: "low",
    features_summary: {
      rt_median: 12.1,
      prefire_rate: 0.08,
      thrusmoke_kill_rate: 0.01,
      headshot_rate: 0.34,
      long_range_fast_rt_rate_4: 0.04,
    },
    top_reasons: [{ title: "Within normal lobby spread", severity: "context" }],
    interpretation: {
      ...SAMPLE_INTERPRETATION,
      archetype: {
        label: "Context-consistent baseline",
        summary: "Performance sits within normal lobby spread after context.",
      },
      behavior_profile: {
        headline: "Broadly consistent with ordinary match variance.",
        summary: "The player does not separate through any persistent abnormal component in this sample.",
      },
      behavioral_deviation: 0.22,
      context_fit: 0.82,
      signal_stability: 0.34,
      review_priority: 0.18,
      support_level: 0.71,
      signal_components: [
        { key: "mechanics", label: "Mechanics", share: 0.28, summary: "Most of the profile is conventional mechanical output." },
        { key: "information_timing", label: "Information / timing", share: 0.16, summary: "Timing does not separate meaningfully." },
        { key: "occlusion", label: "Occlusion", share: 0.08, summary: "Minimal low-visibility contribution." },
        { key: "decision_discipline", label: "Decision discipline", share: 0.22, summary: "Engagement choices look ordinary for the lobby." },
        { key: "concentration", label: "Stability / concentration", share: 0.26, summary: "No concentrated anomaly is evident." },
      ],
      context_adjustment: {
        summary: "Most apparent deviation dissolves under ordinary performance variance and lobby context.",
        remaining_signal: "limited",
        normal_explanations: [
          { key: "skill_gap", label: "Skill gap explanation", status: "strong", weight: 0.82, summary: "Normal match skill spread explains the visible edge." },
          { key: "opponent_pool", label: "Weak opponent pool", status: "partial", weight: 0.44, summary: "Lobby softness explains some isolated success." },
          { key: "sample_size", label: "Sample size limitation", status: "medium", weight: 0.41, summary: "Nothing here is broad enough to outweigh match variance." },
          { key: "map_familiarity", label: "Map familiarity", status: "plausible", weight: 0.38, summary: "Routine map comfort can account for some sequencing." },
        ],
      },
      durability: {
        summary: "No durable anomaly survives the pressure test.",
        metrics: [
          { key: "rounds", label: "Across rounds", value: 0.18, summary: "Spread is weak and inconsistent." },
          { key: "halves", label: "Across halves", value: 0.22, summary: "No meaningful half-to-half persistence." },
          { key: "weapons", label: "Across weapons", value: 0.26, summary: "Weapon mix looks normal." },
          { key: "visibility", label: "Across visibility states", value: 0.14, summary: "No selective low-visibility shape." },
          { key: "engagements", label: "Across engagement types", value: 0.2, summary: "Engagement mix stays ordinary." },
        ],
      },
      review_lens: {
        title: "Keep as baseline comparison",
        summary: "Use this player as a contextual baseline for how ordinary match variance presents in the same lobby.",
        comparisons: ["Compare standout rounds against this baseline profile"],
      },
      limitations: [
        { label: "Low review value", severity: "low", summary: "The current sample does not justify deeper analyst time." },
      ],
      model_notes: SAMPLE_INTERPRETATION.model_notes,
    },
  },
];

export const SAMPLE_REASONS: Reason[] = [
  {
    reason: "fast_rt_cluster",
    severity: "high",
    summary: "Several kills land with unusually short visibility-to-shot timing.",
    why_it_matters: "Consistent fast reaction windows can justify deeper review when they cluster across rounds.",
  },
  {
    reason: "prefire_density",
    severity: "medium",
    summary: "The sample player shows more prefire kills than the rest of the lobby.",
    why_it_matters: "Prefire-heavy kills can be legitimate, but elevated rates raise review priority when combined with other signals.",
  },
];

export const SAMPLE_EVIDENCE: Record<string, EvidenceTable> = {
  "evidence_fast_rt.csv": {
    demo_id: SAMPLE_DEMO_ID,
    steamid: SAMPLE_STEAMID,
    filename: "evidence_fast_rt.csv",
    columns: ["round_num", "kill_tick", "rt_ticks", "weapon", "distance"],
    row_count: 4,
    rows: [
      { round_num: 3, kill_tick: 18231, rt_ticks: 4, weapon: "ak47", distance: 812.4 },
      { round_num: 6, kill_tick: 44611, rt_ticks: 5, weapon: "m4a1_silencer", distance: 654.2 },
      { round_num: 9, kill_tick: 60218, rt_ticks: 3, weapon: "ak47", distance: 900.7 },
      { round_num: 13, kill_tick: 76044, rt_ticks: 4, weapon: "ak47", distance: 1031.5 },
    ],
  },
  "evidence_prefire.csv": {
    demo_id: SAMPLE_DEMO_ID,
    steamid: SAMPLE_STEAMID,
    filename: "evidence_prefire.csv",
    columns: ["round_num", "kill_tick", "visible_ticks_before_shot", "weapon", "headshot"],
    row_count: 2,
    rows: [
      { round_num: 5, kill_tick: 33810, visible_ticks_before_shot: 0, weapon: "ak47", headshot: true },
      { round_num: 11, kill_tick: 71044, visible_ticks_before_shot: 0, weapon: "galilar", headshot: false },
    ],
  },
};

export const SAMPLE_SCORE_TRACE: ScoreTrace = {
  steamid: SAMPLE_STEAMID,
  attacker_name: "SamplePlayerOne",
  raw_proba: 0.81,
  calibrated_proba: 0.78,
  risk_display_value: 0.76,
  confidence_value: 0.63,
  gating_rules: {
    low_evidence_downweight_fired: false,
    n_kills_with_rt_thresholding_applied: true,
    n_kills_with_rt_value: 11,
  },
  evidence_counts: {
    rt_n: 11,
    hs_n: 14,
    prefire_n: 4,
    long_range_n: 5,
  },
  high_tag_flags: {
    prefire_pct: true,
    thrusmoke_pct: false,
    hs_pct: true,
    long_fast_rt_pct: true,
  },
  feature_row: {
    rt_median: 5.4,
    prefire_rate: 0.41,
    headshot_rate: 0.58,
    long_range_fast_rt_rate_4: 0.37,
    enc_aim_error_min_median: 1.9,
    enc_aim_acquire_median: 4.0,
    enc_ang_vel_median: 0.42,
  },
  model_version: "sample-build-001",
  feature_list_version: "sample-feats-001",
  feature_vector_hash: "abc123sample",
};

export const SAMPLE_EXPLAIN_REPORT: ExplainReport = {
  mode: "infer",
  demo_id: SAMPLE_DEMO_ID,
  player: {
    attacker_name: "SamplePlayerOne",
    attacker_steamid: SAMPLE_STEAMID,
  },
  risk: {
    score: 0.76,
    band: "review",
    raw_probability: 0.81,
    calibrated_probability: 0.78,
  },
  confidence: {
    score: 0.63,
    rt_reason_confidence: "normal",
  },
  uncertainty_ci: {
    risk_p05: 0.68,
    risk_p50: 0.76,
    risk_p95: 0.84,
    ci_width: 0.16,
    n_boot: 100,
  },
  reasons: [
    {
      title: "Reaction-time tail",
      severity: "high",
      summary: "median=5.4 ticks | p05=3.0 | %<=4=27.0% | %<=6=54.0%",
      why_it_matters: "Fast first-shot tails can indicate assistive aim in context.",
      evidence_file: "evidence_fast_rt.csv",
      confidence_note: "normal",
    },
    {
      title: "Prefire rate",
      severity: "medium",
      summary: "prefire_rate=41.0%",
      why_it_matters: "Repeated first shots before visibility can be suspicious with corroborating signals.",
      evidence_file: "evidence_prefire.csv",
      confidence_note: "normal",
    },
  ],
  signals: {
    raw_values: {
      prefire_rate: 0.41,
      headshot_rate: 0.58,
      thrusmoke_kill_rate: 0.09,
      rt_median: 5.4,
      long_range_fast_rt_rate_4: 0.37,
    },
    lobby_percentiles: {
      prefire_pct: 0.95,
      hs_pct: 0.88,
      thrusmoke_pct: 0.63,
      rt_median_pct: 0.11,
      long_fast_rt_pct: 0.92,
    },
    top_contributing_signals: [
      { title: "Fast reaction-time tail", severity: "high" },
      { title: "High prefire percentile", severity: "medium" },
      { title: "Long-range fast RT", severity: "medium" },
    ],
  },
  evidence_files: ["evidence_fast_rt.csv", "evidence_prefire.csv"],
  interpretation: SAMPLE_INTERPRETATION,
};
