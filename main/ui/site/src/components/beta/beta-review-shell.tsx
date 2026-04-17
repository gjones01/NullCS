"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  Braces,
  ChevronRight,
  ClipboardList,
  Eye,
  Gauge,
  ShieldAlert,
  Sigma,
} from "lucide-react";
import { RiskBadge } from "@/components/beta/risk-badge";
import { type ReviewBundle } from "@/lib/review-bundle";
import { cn } from "@/lib/utils";

type BetaReviewShellProps = {
  bundle: ReviewBundle;
};

function formatPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

function formatNum(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "n/a";
  return value.toFixed(Math.abs(value) >= 10 ? 1 : 3);
}

function primitiveRows(value: unknown): Array<[string, string]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value as Record<string, unknown>).map(([key, item]) => [
    key.replace(/_/g, " "),
    typeof item === "number" ? formatNum(item) : String(item),
  ]);
}

export function BetaReviewShell({ bundle }: BetaReviewShellProps) {
  const [selectedSteamId, setSelectedSteamId] = useState(bundle.players[0]?.steamid ?? "");
  const selected = useMemo(
    () => bundle.players.find((player) => player.steamid === selectedSteamId) ?? bundle.players[0],
    [bundle.players, selectedSteamId]
  );

  if (!selected) {
    return null;
  }

  const trace = bundle.score_traces[selected.steamid];
  const report = bundle.reports[selected.steamid];
  const evidenceTables = bundle.evidence_tables[selected.steamid] || {};

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <aside className="rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
        <div className="border-b border-white/8 px-6 py-5">
          <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Ranked players</div>
          <h2 className="mt-2 font-display text-2xl tracking-[-0.04em] text-white">{bundle.meta.display_name}</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-400">{bundle.meta.summary}</p>
        </div>
        <div className="space-y-2 p-4">
          {bundle.players.map((player, index) => (
            <button
              key={player.steamid}
              type="button"
              onClick={() => setSelectedSteamId(player.steamid)}
              className={cn(
                "w-full rounded-[1.4rem] border px-4 py-4 text-left transition-colors",
                selected.steamid === player.steamid
                  ? "border-white/15 bg-white/[0.05]"
                  : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[0.7rem] uppercase tracking-[0.22em] text-zinc-500">Rank #{index + 1}</div>
                  <div className="mt-2 font-display text-xl tracking-[-0.03em] text-white">{player.attacker_name}</div>
                  <div className="mt-1 text-xs text-zinc-500">{player.steamid}</div>
                </div>
                <ChevronRight className="mt-1 h-4 w-4 text-zinc-500" />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <RiskBadge band={player.risk_band} />
                <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-zinc-300">
                  Risk {formatPct(player.risk)}
                </div>
                <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-zinc-400">
                  Confidence {formatPct(player.confidence)}
                </div>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <section className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[1.6rem] border border-white/10 bg-[#090b12] p-5">
            <div className="flex items-center gap-2 text-zinc-400">
              <ShieldAlert className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Risk</span>
            </div>
            <div className="mt-3 font-display text-4xl tracking-[-0.05em] text-white">{formatPct(selected.risk)}</div>
            <div className="mt-2">
              <RiskBadge band={selected.risk_band} />
            </div>
          </div>
          <div className="rounded-[1.6rem] border border-white/10 bg-[#090b12] p-5">
            <div className="flex items-center gap-2 text-zinc-400">
              <Gauge className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Confidence</span>
            </div>
            <div className="mt-3 font-display text-4xl tracking-[-0.05em] text-white">{formatPct(selected.confidence)}</div>
            <p className="mt-2 text-sm text-zinc-500">Display confidence from the current inference scoring stack.</p>
          </div>
          <div className="rounded-[1.6rem] border border-white/10 bg-[#090b12] p-5">
            <div className="flex items-center gap-2 text-zinc-400">
              <Sigma className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Raw / Calibrated</span>
            </div>
            <div className="mt-3 text-sm leading-7 text-zinc-300">
              <div>Raw {formatPct(trace?.raw_proba ?? selected.proba_cheater_infer)}</div>
              <div>Calibrated {formatPct(trace?.calibrated_proba ?? null)}</div>
            </div>
          </div>
          <div className="rounded-[1.6rem] border border-white/10 bg-[#090b12] p-5">
            <div className="flex items-center gap-2 text-zinc-400">
              <Eye className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Top reasons</span>
            </div>
            <div className="mt-3 space-y-2">
              {selected.top_reasons.slice(0, 3).map((reason) => (
                <div key={`${selected.steamid}-${reason.title}`} className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-zinc-300">
                  {reason.title}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <article className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Player detail</div>
            <h3 className="mt-3 font-display text-4xl tracking-[-0.05em] text-white">{selected.attacker_name}</h3>
            <div className="mt-2 text-sm text-zinc-500">{selected.steamid}</div>

            <div className="mt-6 grid gap-3 md:grid-cols-2">
              {Object.entries(selected.features_summary).map(([key, value]) => (
                <div key={key} className="rounded-[1.2rem] border border-white/8 bg-white/[0.02] px-4 py-3">
                  <div className="text-[0.7rem] uppercase tracking-[0.2em] text-zinc-500">{key.replace(/_/g, " ")}</div>
                  <div className="mt-2 text-base text-zinc-200">{formatNum(value)}</div>
                </div>
              ))}
            </div>

            {report?.interpretation ? (
              <div className="mt-6 rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5">
                <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Interpretation</div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {primitiveRows(report.interpretation).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-white/8 bg-[#0b1018] px-4 py-3">
                      <div className="text-[0.72rem] uppercase tracking-[0.2em] text-zinc-500">{key}</div>
                      <div className="mt-2 text-sm leading-6 text-zinc-200">{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </article>

          <div className="space-y-6">
            <article className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
              <div className="flex items-center gap-2 text-zinc-400">
                <ClipboardList className="h-4 w-4" />
                <span className="text-[0.72rem] uppercase tracking-[0.22em]">Gating and evidence</span>
              </div>
              <div className="mt-4 grid gap-3">
                {primitiveRows(trace?.gating_rules).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-300">
                    <span className="text-zinc-500">{key}: </span>
                    {value}
                  </div>
                ))}
                {primitiveRows(trace?.evidence_counts).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-300">
                    <span className="text-zinc-500">{key}: </span>
                    {value}
                  </div>
                ))}
              </div>
            </article>

            <article className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
              <div className="flex items-center gap-2 text-zinc-400">
                <Activity className="h-4 w-4" />
                <span className="text-[0.72rem] uppercase tracking-[0.22em]">Reasons and signals</span>
              </div>
              <div className="mt-4 space-y-4">
                {Array.isArray(report?.reasons) ? (
                  <div className="space-y-2">
                    {(report?.reasons as unknown[]).map((item, index) => (
                      <div key={`${selected.steamid}-reason-${index}`} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-300">
                        {typeof item === "string" ? item : JSON.stringify(item)}
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="space-y-2">
                  {primitiveRows(report?.signals).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-300">
                      <span className="text-zinc-500">{key}: </span>
                      {value}
                    </div>
                  ))}
                </div>
              </div>
            </article>
          </div>
        </div>

        <article className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
          <div className="flex items-center gap-2 text-zinc-400">
            <Braces className="h-4 w-4" />
            <span className="text-[0.72rem] uppercase tracking-[0.22em]">Evidence tables</span>
          </div>
          <div className="mt-4 space-y-6">
            {Object.values(evidenceTables).length ? (
              Object.values(evidenceTables).map((table) => (
                <div key={table.filename} className="overflow-hidden rounded-[1.5rem] border border-white/8">
                  <div className="border-b border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-200">{table.filename}</div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-[#0b1018] text-zinc-500">
                        <tr>
                          {table.columns.map((column) => (
                            <th key={column} className="px-4 py-3 font-medium whitespace-nowrap">
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {table.rows.map((row, index) => (
                          <tr key={`${table.filename}-${index}`} className="border-t border-white/6 text-zinc-300">
                            {table.columns.map((column) => (
                              <td key={`${table.filename}-${index}-${column}`} className="px-4 py-3 whitespace-nowrap">
                                {String(row[column] ?? "")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-zinc-400">
                No evidence tables were exported for this player.
              </div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}

