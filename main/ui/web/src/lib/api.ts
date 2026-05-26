import { getApiAccessToken, getApiBaseUrl } from "../runtimeConfig";

function apiUrl(path: string): string {
  const apiBase = getApiBaseUrl().replace(/\/+$/, "");
  return `${apiBase}${path.startsWith("/") ? path : `/${path}`}`;
}

function apiHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers || undefined);
  const accessToken = getApiAccessToken();
  if (accessToken) {
    headers.set("X-NULLCS-KEY", accessToken);
  }
  return headers;
}

export type PlayerRow = {
  steamid: string;
  attacker_name: string;
  proba_cheater_infer: number;
  risk?: number;
  confidence?: number;
  ci_low?: number | null;
  ci_high?: number | null;
  risk_band?: string;
  top_reasons?: Array<{ title: string; severity: string }>;
  features_summary: Record<string, number | null>;
  interpretation?: InterpretationModel;
};

export type SignalComponent = {
  key: string;
  label: string;
  share: number;
  summary: string;
};

export type ContextFactor = {
  key: string;
  label: string;
  status: string;
  weight: number;
  summary: string;
};

export type InterpretationMetric = {
  key: string;
  label: string;
  value: number | null;
  display_value?: string;
  summary: string;
};

export type InterpretationSection = {
  summary: string;
  stats: InterpretationMetric[];
};

export type MatchProfileSection = InterpretationSection & {
  relative_markers: InterpretationMetric[];
};

export type LimitationItem = {
  label: string;
  severity: string;
  summary: string;
};

export type ReviewLens = {
  title: string;
  summary: string;
  comparisons: string[];
};

export type InterpretationModel = {
  archetype: {
    label: string;
    summary: string;
  };
  behavior_profile: {
    headline: string;
    summary: string;
  };
  match_profile: MatchProfileSection;
  evidence_basis: InterpretationSection;
  behavioral_deviation: number;
  global_process_anomaly?: number;
  context_fit: number;
  signal_stability: number;
  review_priority: number;
  support_level: number;
  signal_components: SignalComponent[];
  context_adjustment: {
    summary: string;
    remaining_signal: string;
    normal_explanations: ContextFactor[];
  };
  durability: {
    summary: string;
    metrics: InterpretationMetric[];
  };
  review_lens: ReviewLens;
  limitations: LimitationItem[];
  model_notes?: string[];
};

export type ScoreTrace = {
  steamid: string;
  attacker_name: string;
  raw_proba: number;
  calibrated_proba?: number | null;
  risk_display_value: number;
  confidence_value: number;
  ci_p05?: number | null;
  ci_p95?: number | null;
  gating_rules?: Record<string, unknown>;
  evidence_counts?: Record<string, unknown>;
  high_tag_flags?: Record<string, boolean>;
  why_risk_low_despite_high_tags?: string | null;
  feature_row?: Record<string, number | null>;
  model_version?: string;
  model_sha256?: string;
  feature_list_version?: string;
  feature_vector_hash?: string;
};

export type DemoStatus = {
  demo_id: string;
  state: string;
  logs_tail: string;
  error: string;
  original_filename?: string;
  stage_index?: number;
  stage?: string;
  steps?: string[];
};

export type Reason = {
  reason: string;
  severity: "low" | "medium" | "high" | "context" | string;
  summary: string;
  why_it_matters: string;
};

export type ExplainReport = {
  mode: string;
  demo_id: string;
  player: {
    attacker_name: string;
    attacker_steamid: string;
  };
  risk: {
    score: number;
    band: string;
    raw_probability?: number | null;
    calibrated_probability?: number | null;
  };
  confidence: {
    score: number;
    rt_reason_confidence: string;
  };
  uncertainty_ci?: {
    risk_p05?: number;
    risk_p50?: number;
    risk_p95?: number;
    ci_width?: number;
    n_boot?: number;
  } | null;
  reasons: Array<{
    title: string;
    severity: string;
    summary: string;
    why_it_matters: string;
    evidence_file?: string;
    confidence_note?: string;
  }>;
  signals?: {
    raw_values?: Record<string, number | null>;
    lobby_percentiles?: Record<string, number | null>;
    top_contributing_signals?: Array<{ title?: string; severity?: string }>;
  };
  evidence_files: string[];
  interpretation?: InterpretationModel;
};

export type ModelInfo = {
  artifact_name?: string;
  artifact_path?: string;
  training_mode?: string;
  training_timestamp?: string;
  class_balance?: Record<string, number>;
  source_stats?: Record<string, { train_player_rows_after_n_players_filter?: number; train_pos_after_n_players_filter?: number; train_neg_after_n_players_filter?: number }>;
  feature_count?: number;
};

export type HealthResponse = {
  status: string;
  version: string;
  environment: string;
  mode: "local" | "demo" | "production" | string;
  auth_required: boolean;
  upload_enabled: boolean;
  max_upload_bytes: number | null;
  model_version: string;
  model_info?: ModelInfo;
  product_info?: {
    name?: string;
    identity?: string;
    tagline?: string;
    analyst_note?: string;
  };
};

export type ReportFiles = {
  demo_id: string;
  steamid: string;
  report_exists?: boolean;
  reasons_exists: boolean;
  top_row_exists: boolean;
  evidence_files: string[];
};

export type EvidenceTable = {
  demo_id: string;
  steamid: string;
  filename: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
};

async function parseError(response: Response): Promise<string> {
  const fallback = `Request failed with status ${response.status}`;
  try {
    const data = (await response.json()) as { error?: { message?: string } };
    return data.error?.message?.trim() || fallback;
  } catch {
    try {
      const text = await response.text();
      return text.trim() || fallback;
    } catch {
      return fallback;
    }
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, headers: apiHeaders(init) });
  } catch {
    throw new Error("Live analysis service is unavailable.");
  }
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<T>;
}

export async function getHealth() {
  return fetchJson<HealthResponse>("/health");
}

export async function uploadDemo(file: File, demoId?: string) {
  const fd = new FormData();
  fd.append("file", file);
  if (demoId) fd.append("demo_id", demoId);
  return fetchJson<{ demo_id: string; original_filename?: string }>("/upload-demo", { method: "POST", body: fd });
}


export async function queueLocalDemoPath(path: string, demoId?: string) {
  return fetchJson<{ demo_id: string; state: string; original_filename?: string }>("/demo/from-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, demo_id: demoId || undefined }),
  });
}
export async function runDemo(demoId: string) {
  return fetchJson<{ demo_id: string; state: string }>(`/demo/${demoId}/run`, { method: "POST" });
}

export async function getStatus(demoId: string) {
  return fetchJson<DemoStatus>(`/demo/${demoId}/status`);
}

export async function getPlayers(demoId: string): Promise<{ demo_id: string; players: PlayerRow[] }> {
  return fetchJson<{ demo_id: string; players: PlayerRow[] }>(`/demo/${demoId}/players`);
}

export async function getPlayerScoreTrace(demoId: string, steamid: string) {
  return fetchJson<{ demo_id: string; steamid: string; trace: ScoreTrace }>(`/demo/${demoId}/player/${steamid}/score-trace`);
}

export async function explainPlayer(demoId: string, steamid: string) {
  return fetchJson<{ demo_id: string; steamid: string; evidence_files: string[] }>(`/demo/${demoId}/player/${steamid}/explain`, {
    method: "POST",
  });
}

export async function getReportFiles(demoId: string, steamid: string) {
  return fetchJson<ReportFiles>(`/demo/${demoId}/player/${steamid}/report/files`);
}

export async function getReasons(demoId: string, steamid: string) {
  return fetchJson<{ demo_id: string; steamid: string; reasons: Reason[] }>(`/demo/${demoId}/player/${steamid}/report/reasons`);
}

export async function getEvidenceTable(demoId: string, steamid: string, filename: string, limit = 500) {
  const safeName = encodeURIComponent(filename);
  return fetchJson<EvidenceTable>(`/demo/${demoId}/player/${steamid}/report/evidence/${safeName}?limit=${limit}`);
}

export async function getExplainReport(demoId: string, steamid: string, mode = "infer", ci = 0) {
  const params = new URLSearchParams({
    demo_id: demoId,
    steamid,
    mode,
    ci: String(ci),
  });
  return fetchJson<ExplainReport>(`/explain?${params.toString()}`);
}
