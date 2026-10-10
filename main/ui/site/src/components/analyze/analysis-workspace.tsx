"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, FileUp, Loader2, ShieldCheck } from "lucide-react";
import type { AnalysisResult, AnalysisStatus, EvidenceTable, Explanation } from "@/lib/analysis-types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/analysis${path}`, { ...init, cache: "no-store" });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error?.message || "The analysis service could not complete this request.");
  return data as T;
}
const percent = (value: number | null) => value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
const panel = "rounded-2xl border border-white/10 bg-[#0b1018]/90 p-5 sm:p-7";
const action = "inline-flex items-center justify-center gap-2 rounded-lg metallic-button bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45";

export function AnalysisWorkspace({ jobId }: { jobId?: string }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [limit, setLimit] = useState<number | null>(null);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selected, setSelected] = useState("");
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [evidence, setEvidence] = useState<EvidenceTable | null>(null);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [explainError, setExplainError] = useState("");
  const upload = useRef<XMLHttpRequest | null>(null);
  const evidenceRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    if (jobId) return;
    const controller = new AbortController();
    api<{ max_upload_bytes: number }>("/capabilities", { signal: controller.signal }).then((data) => setLimit(data.max_upload_bytes)).catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => { controller.abort(); upload.current?.abort(); };
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const next = await api<AnalysisStatus>(`/${jobId}/status`, { signal: controller.signal });
        if (disposed) return;
        setStatus(next); setError("");
        if (next.state === "results_ready") {
          const payload = await api<AnalysisResult>(`/${jobId}/results`, { signal: controller.signal });
          if (!disposed) { setResult(payload); setSelected((old) => old || payload.players[0]?.steamid || ""); }
          return;
        }
        if (next.state === "failed") return;
      } catch (e) { if (!disposed) setError(e instanceof Error ? e.message : "Unable to refresh status."); }
      if (!disposed) timer = setTimeout(poll, 4000);
    }
    void poll();
    return () => { disposed = true; controller.abort(); clearTimeout(timer); };
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !selected) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    evidenceRequest.current?.abort();
    setExplanation(null); setEvidence(null); setEvidenceBusy(false); setExplainError("");
    async function poll() {
      try {
        const next = await api<Explanation>(`/${jobId}/players/${selected}/explanation`, { signal: controller.signal });
        if (disposed) return;
        setExplanation(next);
        if (next.status.state === "queued" || next.status.state === "running") timer = setTimeout(poll, 4000);
      } catch (e) { if (!disposed) setExplainError(e instanceof Error ? e.message : "Explanation unavailable."); }
    }
    void poll();
    return () => { disposed = true; controller.abort(); evidenceRequest.current?.abort(); clearTimeout(timer); };
  }, [jobId, selected, busy]);

  function choose(next: File | null) {
    setError("");
    if (next && (!next.name.toLowerCase().endsWith(".dem") || (limit !== null && next.size > limit))) {
      setError("Choose a .dem file within the upload limit."); setFile(null); return;
    }
    setFile(next);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(""); setUploadPercent(0);
    try {
      const ticket = await api<{ job_id: string; upload_url: string; upload_token: string }>("", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: file.name, size: file.size }),
      });
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest(); upload.current = xhr;
        xhr.open("PUT", ticket.upload_url);
        xhr.setRequestHeader("Authorization", `Bearer ${ticket.upload_token}`);
        xhr.setRequestHeader("Content-Type", "application/octet-stream");
        xhr.upload.onprogress = (e) => { if (e.lengthComputable) setUploadPercent(Math.round(e.loaded / e.total * 100)); };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve();
          else { let message = "Upload failed. Please select the demo again."; try { message = JSON.parse(xhr.responseText).error?.message || message; } catch {} reject(new Error(message)); }
        };
        xhr.onerror = () => reject(new Error("Could not reach the upload worker. Check your connection and try again."));
        xhr.onabort = () => reject(new Error("Upload cancelled."));
        xhr.send(file);
      });
      router.push(`/analyze/${ticket.job_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed."); }
    finally { setBusy(false); setUploadPercent(null); }
  }

  async function explain() {
    setBusy(true); setExplainError("");
    try { await api(`/${jobId}/players/${selected}/explain`, { method: "POST" }); }
    catch (e) { setExplainError(e instanceof Error ? e.message : "Could not start explanation."); }
    finally { setBusy(false); }
  }
  async function loadEvidence(filename: string) {
    evidenceRequest.current?.abort();
    const controller = new AbortController();
    evidenceRequest.current = controller;
    setEvidenceBusy(true); setExplainError("");
    try {
      const table = await api<EvidenceTable>(`/${jobId}/players/${selected}/evidence/${encodeURIComponent(filename)}`, { signal: controller.signal });
      if (!controller.signal.aborted) setEvidence(table);
    }
    catch (e) { if (!controller.signal.aborted) setExplainError(e instanceof Error ? e.message : "Evidence unavailable."); }
    finally { if (!controller.signal.aborted) setEvidenceBusy(false); }
  }
  const player = result?.players.find((p) => p.steamid === selected);

  return <div className="mx-auto max-w-7xl px-5 pb-24 pt-16 sm:px-8">
    <div className="mb-9 max-w-3xl">
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-primary">NullCS / Demo analysis</p>
      <h1 className="text-3xl font-bold sm:text-5xl">A closer look at the match.</h1>
      <p className="mt-5 leading-relaxed text-muted-foreground">Real model-derived behavioral signals, ranked for analyst review. A score is not a cheating verdict or a basis for an automatic ban.</p>
      <p role="note" className="mt-5 rounded-lg border border-primary/25 bg-primary/5 px-4 py-3 text-sm leading-relaxed text-muted-foreground"><span className="mr-2 font-semibold text-primary">Beta</span>Analysis will keep improving as models are refined and retrained on newer data.</p>
    </div>
    {error && <div role="alert" className="mb-6 rounded-xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div>}
    {!jobId ? <form onSubmit={submit} className={`${panel} max-w-3xl`}>
      <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!busy) choose(e.dataTransfer.files[0] || null); }} className="rounded-xl border border-dashed border-primary/40 bg-primary/5 p-8 text-center">
        <FileUp className="mx-auto mb-4 h-9 w-9 text-primary" aria-hidden="true" />
        <label htmlFor="demo-file" className="block text-lg font-semibold">Select or drop a CS2 demo</label>
        <p className="mb-5 mt-2 text-sm text-muted-foreground">{limit ? `.dem files up to ${(limit / 1024 ** 3).toFixed(1)} GiB` : "Checking analysis availability…"}</p>
        <input id="demo-file" type="file" accept=".dem" disabled={busy || !limit} onChange={(e) => choose(e.target.files?.[0] || null)} className="max-w-full text-sm file:mr-4 file:rounded-md file:border-0 file:bg-white/10 file:px-4 file:py-2 file:text-white" />
        {file && <p className="mt-4 break-all text-sm">{file.name} · {(file.size / 1024 ** 2).toFixed(1)} MiB</p>}
      </div>
      <p className="my-5 flex items-start gap-2 text-sm leading-relaxed text-muted-foreground"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />Only upload demos you are authorized to submit. Results are private to this browser session. Clearing cookies removes your access. Uploaded demos and results are retained by the service until its operator removes them.</p>
      <button className={action} disabled={!file || !limit || busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUpRight className="h-4 w-4" />}{busy ? `Uploading${uploadPercent !== null ? ` · ${uploadPercent}%` : ""}` : "Upload and analyze"}</button>
      {busy && <button type="button" onClick={() => upload.current?.abort()} className="ml-4 text-sm underline">Cancel upload</button>}
    </form> : <>
      <div className={`${panel} mb-6`} aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div><p className="text-xs uppercase tracking-widest text-muted-foreground">Analysis status</p><h2 className="mt-2 text-xl font-semibold">{status?.stage_label || "Loading analysis…"}</h2><p className="mt-1 break-all text-sm text-muted-foreground">{status?.filename}</p></div>
          <Link href="/analyze" className="text-sm text-primary underline underline-offset-4">Analyze another demo</Link>
        </div>
        {status?.error && <p role="alert" className="mt-4 text-rose-200">{status.error.message}</p>}
        {status && !["results_ready", "failed"].includes(status.state) && <p className="mt-4 text-sm text-muted-foreground">This stage reflects worker activity. Processing time depends on the replay and available resources; there is no estimated completion percentage.</p>}
        {status?.runtime_seconds !== null && status?.runtime_seconds !== undefined && <p className="mt-3 text-sm text-muted-foreground">Inference runtime: {status.runtime_seconds.toFixed(1)} seconds on this worker.</p>}
      </div>
      {result && <>
        <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3"><h2 className="text-2xl font-semibold">Players ranked for review</h2><p className="text-sm text-muted-foreground">{result.demo.map_name} · {result.players.length} eligible players</p></div>
        {result.warnings.map((warning) => <p key={warning.code} className="mb-3 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm leading-relaxed text-muted-foreground">{warning.message}</p>)}
        <p className="mb-5 mt-5 text-sm text-muted-foreground">Ordered by the pipeline’s review score. Model score is the raw output; calibration is shown only when available. Review score includes the existing evidence adjustments.</p>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          <div className={`${panel} overflow-x-auto`}>
            <table className="w-full text-left text-sm"><thead><tr className="border-b border-white/10 text-xs text-muted-foreground"><th className="pb-3 pr-3">Rank / player</th><th className="pb-3 pr-3">Review</th><th className="pb-3 pr-3">Model</th><th className="pb-3">Calibrated</th></tr></thead>
              <tbody>{result.players.map((p) => <tr key={p.steamid} className={`border-b border-white/5 ${p.steamid === selected ? "bg-primary/10" : ""}`}><td className="py-4 pr-3"><button aria-pressed={p.steamid === selected} onClick={() => setSelected(p.steamid)} className="text-left font-medium hover:text-primary"><span className="mr-2 text-primary">#{p.rank}</span>{p.attacker_name || p.steamid}</button></td><td className="pr-3">{percent(p.risk)}</td><td className="pr-3">{percent(p.model_score)}</td><td>{percent(p.calibrated_probability)}</td></tr>)}</tbody>
            </table>
          </div>
          {player && <div className={panel}>
            <p className="text-xs uppercase tracking-widest text-primary">Player review</p><h3 className="mt-2 break-words text-xl font-semibold">{player.attacker_name || player.steamid}</h3><p className="mt-1 text-xs text-muted-foreground">Steam ID {player.steamid}</p>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{player.interpretation?.behavior_profile?.summary}</p>
            <p className="mt-3 text-sm">Evidence confidence: {percent(player.confidence)}</p>
            <ul className="my-5 space-y-2 text-sm">{player.top_reasons.map((reason) => <li key={reason.title} className="border-l-2 border-primary/50 pl-3">{reason.title}</li>)}</ul>
            <div className="border-t border-white/10 pt-5"><h4 className="font-semibold">Explanation &amp; evidence</h4>
              <p className="mb-4 mt-2 text-sm text-muted-foreground">{explanation?.status.state === "ready" ? "Generated from this player’s stored match evidence." : "Scoring is complete. Explanations are generated separately when requested."}</p>
              {explainError && <p role="alert" className="mb-3 text-sm text-rose-200">{explainError}</p>}
              {explanation?.status.error && <p role="alert" className="mb-3 text-sm text-rose-200">{explanation.status.error}</p>}
              {explanation?.status.state !== "ready" && <button className={action} disabled={busy || ["queued", "running"].includes(explanation?.status.state || "")} onClick={explain}>{["queued", "running"].includes(explanation?.status.state || "") ? `Explanation ${explanation?.status.state}` : explanation?.status.state === "failed" ? "Retry explanation" : "Generate explanation"}</button>}
              {explanation?.report?.reasons?.map((reason, i) => <div key={i} className="mt-4 text-sm"><p className="font-medium">{reason.title || reason.reason}</p><p className="mt-1 leading-relaxed text-muted-foreground">{reason.summary}</p></div>)}
              <div className="mt-5 flex flex-wrap gap-2">{explanation?.report?.evidence_files?.map((name) => <button key={name} disabled={evidenceBusy} onClick={() => loadEvidence(name)} className="rounded-lg border border-white/15 px-3 py-2 text-xs hover:border-primary">{name.replace("evidence_", "").replace(".csv", "").replaceAll("_", " ")}</button>)}</div>
              {explanation?.status.state === "ready" && !explanation.report?.evidence_files?.length && <p className="mt-4 text-sm text-muted-foreground">No evidence tables were produced for this player.</p>}
            </div>
          </div>}
        </div>
        {evidence && <div className={`${panel} mt-6 overflow-x-auto`}><h3 className="mb-4 font-semibold">{evidence.filename}</h3><table className="text-left text-xs"><thead><tr>{evidence.columns.map((column) => <th key={column} className="whitespace-nowrap border-b border-white/15 p-2">{column}</th>)}</tr></thead><tbody>{evidence.rows.map((row, i) => <tr key={i}>{evidence.columns.map((column) => <td key={column} className="max-w-xs truncate border-b border-white/5 p-2">{row[column] === null ? "—" : String(row[column])}</td>)}</tr>)}</tbody></table>{evidence.truncated && <p className="mt-3 text-xs text-muted-foreground">Showing the first 2,000 rows.</p>}</div>}
        <details className="mt-7 text-xs text-muted-foreground"><summary className="cursor-pointer">Model and parser provenance</summary><dl className="mt-3 space-y-2 break-all"><div>Model: {result.model.artifact_name}</div><div>SHA-256: {result.model.sha256}</div><div>Feature contract: {result.model.feature_list_sha256}</div><div>Parser: {result.demo.parser_provenance.demoparser2_version || "Unavailable"} · CS2 patch: {result.demo.parser_provenance.patch_version || "Unavailable"}</div></dl></details>
      </>}
    </>}
  </div>;
}
