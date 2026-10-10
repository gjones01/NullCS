export type ExplanationStatus = { state: "unavailable" | "queued" | "running" | "ready" | "failed"; error: string | null };
export type AnalysisStatus = {
  job_id: string; state: string; stage: string; stage_label: string; filename: string;
  created_at: string; started_at: string | null; finished_at: string | null; runtime_seconds: number | null;
  events: { stage: string; at: string }[]; error: { code: string; message: string } | null;
};
export type AnalysisPlayer = {
  steamid: string; attacker_name: string; rank: number; model_score: number;
  calibrated_probability: number | null; risk: number; risk_band: string; confidence: number;
  features_summary: Record<string, number | null>;
  top_reasons: { title: string; severity: string }[];
  interpretation?: { behavior_profile?: { headline: string; summary: string }; limitations?: { label: string; summary: string }[] };
  explanation: ExplanationStatus;
};
export type AnalysisResult = {
  schema_version: string; job_id: string; ranking: string; status: AnalysisStatus;
  demo: { filename: string; size_bytes: number; map_name: string; parser_provenance: Record<string, string | null> };
  model: { artifact_name: string; sha256: string; feature_list_sha256: string; calibration_used: boolean };
  warnings: { code: string; message: string }[]; players: AnalysisPlayer[];
};
export type Explanation = {
  status: ExplanationStatus;
  report: { reasons: { title?: string; reason?: string; summary?: string; why_it_matters?: string }[]; evidence_files: string[] } | null;
};
export type EvidenceTable = { filename: string; columns: string[]; rows: Record<string, unknown>[]; truncated: boolean };
