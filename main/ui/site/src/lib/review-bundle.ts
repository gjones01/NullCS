import "server-only";

import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

export type ReviewReason = {
  title: string;
  severity: string;
};

export type ReviewPlayer = {
  steamid: string;
  attacker_name: string;
  proba_cheater_infer: number;
  risk: number;
  confidence: number | null;
  ci_low: number | null;
  ci_high: number | null;
  risk_band: string;
  features_summary: Record<string, number | null>;
  top_reasons: ReviewReason[];
  interpretation?: Record<string, unknown> | null;
};

export type ScoreTrace = {
  steamid: string;
  attacker_name: string;
  raw_proba: number | null;
  calibrated_proba: number | null;
  risk_display_value: number | null;
  confidence_value: number | null;
  gating_rules?: Record<string, unknown>;
  evidence_counts?: Record<string, unknown>;
  high_tag_flags?: Record<string, unknown>;
  why_risk_low_despite_high_tags?: string | null;
  feature_row?: Record<string, number | null>;
};

export type PlayerReport = {
  mode: string;
  demo_id: string;
  player: { attacker_name: string; attacker_steamid: string };
  risk: Record<string, unknown>;
  confidence: Record<string, unknown>;
  uncertainty_ci: unknown;
  reasons: unknown;
  signals: unknown;
  evidence_files: string[];
  interpretation?: unknown;
};

export type EvidenceTable = {
  demo_id: string;
  steamid: string;
  filename: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
};

export type ReviewBundle = {
  meta: {
    schema_version: string;
    app_name: string;
    source: string;
    demo_id: string;
    display_name: string;
    created_at: string;
    summary: string;
    benchmark_snapshot?: Record<string, number> | null;
  };
  players: ReviewPlayer[];
  score_traces: Record<string, ScoreTrace>;
  reports: Record<string, PlayerReport>;
  evidence_tables: Record<string, Record<string, EvidenceTable>>;
};

export type RecentBundle = {
  demoId: string;
  displayName: string;
  createdAt: string;
  summary: string;
  playerCount: number;
};

const siteRoot = process.cwd();
const mainRoot = path.resolve(siteRoot, "../..");
const repoRoot = path.resolve(mainRoot, "..");
const processedRoot = path.join(mainRoot, "data", "processed");
const reviewBundlesRoot = path.join(processedRoot, "review_bundles");
const webUploadsRoot = path.join(processedRoot, "web_uploads");
const pythonBin = process.env.NULLCS_PYTHON_BIN || "python";

function sanitizeDemoToken(value: string): string {
  return value.replace(/[^a-zA-Z0-9]+/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
}

export function makeWebDemoId(inputPath: string): string {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  const base = sanitizeDemoToken(path.parse(inputPath).name).slice(0, 24) || "demo";
  const suffix = randomBytes(4).toString("hex");
  return `WEB_${stamp}_${base}_${suffix}`;
}

export async function saveUploadedDemo(file: File): Promise<string> {
  const originalName = String(file.name || "").trim();
  if (!originalName) {
    throw new Error("Uploaded file is missing a filename.");
  }
  if (!originalName.toLowerCase().endsWith(".dem")) {
    throw new Error("Upload must be a .dem file.");
  }

  await fs.mkdir(webUploadsRoot, { recursive: true });
  const stem = sanitizeDemoToken(path.parse(originalName).name).slice(0, 32) || "demo";
  const suffix = randomBytes(4).toString("hex");
  const target = path.join(webUploadsRoot, `${stem}_${suffix}.dem`);
  const bytes = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(target, bytes);
  return target;
}

function bundlePathForDemo(demoId: string): string {
  return path.join(reviewBundlesRoot, `${demoId}_infer.json`);
}

async function runPythonScript(scriptPath: string, args: string[]) {
  const child = spawn(pythonBin, [scriptPath, ...args], {
    cwd: repoRoot,
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });

  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  const exitCode = await new Promise<number>((resolve, reject) => {
    child.on("error", reject);
    child.on("close", resolve);
  });

  if (exitCode !== 0) {
    throw new Error(
      `Python script failed (${path.basename(scriptPath)} exit=${exitCode})\n${stderr || stdout || "No output"}`
    );
  }

  return { stdout, stderr };
}

export async function runInferenceAndExportBundle(input: {
  demPath: string;
  demoId?: string;
}) {
  const demPath = input.demPath.trim();
  if (!demPath) {
    throw new Error("Demo path is required.");
  }
  if (!demPath.toLowerCase().endsWith(".dem")) {
    throw new Error("Demo path must point to a .dem file.");
  }

  const demoId = input.demoId?.trim() || makeWebDemoId(demPath);
  const inferScript = path.join(mainRoot, "scripts", "run_infer_pipeline.py");
  const exportScript = path.join(mainRoot, "scripts", "export_review_bundle.py");
  const inferArgs = [
    "--dem_path",
    demPath,
    "--demo_id",
    demoId,
    "--out_dir",
    processedRoot,
  ];

  const infer = await runPythonScript(inferScript, inferArgs);
  const bundleOut = bundlePathForDemo(demoId);
  const review = await runPythonScript(exportScript, [
    "--demo",
    demoId,
    "--mode",
    "infer",
    "--output",
    bundleOut,
  ]);

  return {
    demoId,
    bundlePath: bundleOut,
    inferStdout: infer.stdout,
    exportStdout: review.stdout,
  };
}

export async function readReviewBundle(demoId: string): Promise<ReviewBundle | null> {
  const target = bundlePathForDemo(demoId);
  try {
    const raw = await fs.readFile(target, "utf-8");
    return JSON.parse(raw) as ReviewBundle;
  } catch {
    return null;
  }
}

export async function waitForReviewBundle(
  demoId: string,
  options?: { timeoutMs?: number; intervalMs?: number }
): Promise<ReviewBundle | null> {
  const timeoutMs = options?.timeoutMs ?? 8000;
  const intervalMs = options?.intervalMs ?? 250;
  const started = Date.now();

  while (Date.now() - started <= timeoutMs) {
    const bundle = await readReviewBundle(demoId);
    if (bundle) {
      return bundle;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  return null;
}

export async function listRecentBundles(limit = 6): Promise<RecentBundle[]> {
  try {
    const entries = await fs.readdir(reviewBundlesRoot, { withFileTypes: true });
    const files = entries.filter((entry) => entry.isFile() && entry.name.endsWith("_infer.json"));
    const stats = await Promise.all(
      files.map(async (entry) => {
        const full = path.join(reviewBundlesRoot, entry.name);
        const stat = await fs.stat(full);
        return { full, stat };
      })
    );
    const sorted = stats.sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs).slice(0, limit);
    const bundles = await Promise.all(
      sorted.map(async ({ full }) => {
        const raw = JSON.parse(await fs.readFile(full, "utf-8")) as ReviewBundle;
        return {
          demoId: raw.meta.demo_id,
          displayName: raw.meta.display_name,
          createdAt: raw.meta.created_at,
          summary: raw.meta.summary,
          playerCount: raw.players.length,
        } satisfies RecentBundle;
      })
    );
    return bundles;
  } catch {
    return [];
  }
}
