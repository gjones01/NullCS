import type { EvidenceTable, ExplainReport, PlayerRow, ScoreTrace } from "./lib/api";
import { SAMPLE_DEMO_ID, SAMPLE_EVIDENCE, SAMPLE_EXPLAIN_REPORT, SAMPLE_PLAYERS, SAMPLE_SCORE_TRACE, SAMPLE_STEAMID } from "./mockData";

export type ReviewBundleMeta = {
  schema_version: string;
  app_name: string;
  source: "sample" | "import" | "local-export";
  demo_id: string;
  display_name: string;
  created_at: string;
  summary?: string;
  benchmark_snapshot?: {
    cheater_top1_hit_rate?: number;
    cheater_top3_hit_rate?: number;
    legit_median_top1_score?: number;
    pro_median_top1_score?: number;
  };
};

export type ReviewBundle = {
  meta: ReviewBundleMeta;
  players: PlayerRow[];
  score_traces: Record<string, ScoreTrace>;
  reports: Record<string, ExplainReport>;
  evidence_tables: Record<string, Record<string, EvidenceTable>>;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toStringOrThrow(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Invalid review bundle: missing ${field}.`);
  }
  return value;
}

function toPlayers(value: unknown): PlayerRow[] {
  if (!Array.isArray(value)) throw new Error("Invalid review bundle: players must be an array.");
  return value as PlayerRow[];
}

function toTraceMap(value: unknown): Record<string, ScoreTrace> {
  if (!isObject(value)) throw new Error("Invalid review bundle: score_traces must be an object.");
  return value as Record<string, ScoreTrace>;
}

function toReportMap(value: unknown): Record<string, ExplainReport> {
  if (!isObject(value)) throw new Error("Invalid review bundle: reports must be an object.");
  return value as Record<string, ExplainReport>;
}

function toEvidenceMap(value: unknown): Record<string, Record<string, EvidenceTable>> {
  if (!isObject(value)) throw new Error("Invalid review bundle: evidence_tables must be an object.");
  return value as Record<string, Record<string, EvidenceTable>>;
}

export function buildSampleReviewBundle(): ReviewBundle {
  return {
    meta: {
      schema_version: "nullcs.review-bundle.v1",
      app_name: "NullCS",
      source: "sample",
      demo_id: SAMPLE_DEMO_ID,
      display_name: "Sample Match Review",
      created_at: "2026-03-30T00:00:00Z",
      summary: "Bundled desktop walkthrough showing a ranked match review, player report, score trace, and evidence tables.",
      benchmark_snapshot: {
        cheater_top1_hit_rate: 0.7,
        cheater_top3_hit_rate: 0.9,
        legit_median_top1_score: 0.0073,
        pro_median_top1_score: 0.0073,
      },
    },
    players: SAMPLE_PLAYERS,
    score_traces: {
      [SAMPLE_STEAMID]: SAMPLE_SCORE_TRACE,
    },
    reports: {
      [SAMPLE_STEAMID]: SAMPLE_EXPLAIN_REPORT,
    },
    evidence_tables: {
      [SAMPLE_STEAMID]: SAMPLE_EVIDENCE,
    },
  };
}

export async function loadReviewBundleFromFile(file: File): Promise<ReviewBundle> {
  const text = await file.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("Review bundle is not valid JSON.");
  }
  return parseReviewBundle(parsed);
}

export function parseReviewBundle(value: unknown): ReviewBundle {
  if (!isObject(value)) throw new Error("Invalid review bundle.");
  const metaValue = value.meta;
  if (!isObject(metaValue)) throw new Error("Invalid review bundle: missing meta.");
  const bundle: ReviewBundle = {
    meta: {
      schema_version: toStringOrThrow(metaValue.schema_version, "meta.schema_version"),
      app_name: toStringOrThrow(metaValue.app_name, "meta.app_name"),
      source: (typeof metaValue.source === "string" ? metaValue.source : "import") as ReviewBundleMeta["source"],
      demo_id: toStringOrThrow(metaValue.demo_id, "meta.demo_id"),
      display_name: toStringOrThrow(metaValue.display_name, "meta.display_name"),
      created_at: toStringOrThrow(metaValue.created_at, "meta.created_at"),
      summary: typeof metaValue.summary === "string" ? metaValue.summary : undefined,
      benchmark_snapshot: isObject(metaValue.benchmark_snapshot)
        ? {
            cheater_top1_hit_rate:
              typeof metaValue.benchmark_snapshot.cheater_top1_hit_rate === "number" ? metaValue.benchmark_snapshot.cheater_top1_hit_rate : undefined,
            cheater_top3_hit_rate:
              typeof metaValue.benchmark_snapshot.cheater_top3_hit_rate === "number" ? metaValue.benchmark_snapshot.cheater_top3_hit_rate : undefined,
            legit_median_top1_score:
              typeof metaValue.benchmark_snapshot.legit_median_top1_score === "number" ? metaValue.benchmark_snapshot.legit_median_top1_score : undefined,
            pro_median_top1_score:
              typeof metaValue.benchmark_snapshot.pro_median_top1_score === "number" ? metaValue.benchmark_snapshot.pro_median_top1_score : undefined,
          }
        : undefined,
    },
    players: toPlayers(value.players),
    score_traces: toTraceMap(value.score_traces),
    reports: toReportMap(value.reports),
    evidence_tables: toEvidenceMap(value.evidence_tables),
  };
  return bundle;
}
