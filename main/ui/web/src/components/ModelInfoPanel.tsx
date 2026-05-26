import type { ModelInfo } from "../lib/api";

function countLine(label: string, value: string) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/25 p-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <div className="mt-1 text-sm text-slate-100">{value}</div>
    </div>
  );
}

export function ModelInfoPanel({ info }: { info: ModelInfo | undefined }) {
  if (!info) return null;

  const classBalance = info.class_balance || {};
  const sourceStats = info.source_stats || {};
  const sourceLines = Object.entries(sourceStats)
    .map(([name, payload]) => {
      const rows = payload.train_player_rows_after_n_players_filter ?? 0;
      const pos = payload.train_pos_after_n_players_filter ?? 0;
      const neg = payload.train_neg_after_n_players_filter ?? 0;
      return `${name}: ${rows} rows (${pos} pos / ${neg} neg)`;
    })
    .join(" | ");

  return (
    <section className="glass-panel p-4">
      <h2 className="mb-3 text-sm uppercase tracking-[0.16em] text-slate-300">Model Info</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {countLine("Model", info.artifact_name || "unknown")}
        {countLine("Training Mode", info.training_mode || "unknown")}
        {countLine("Trained At", info.training_timestamp || "unknown")}
        {countLine("Feature Count", String(info.feature_count ?? "unknown"))}
        {countLine("Class Balance", `${classBalance.positive ?? "?"} pos / ${classBalance.negative ?? "?"} neg`)}
        {countLine("Sources", sourceLines || "No source stats found")}
      </div>
    </section>
  );
}
