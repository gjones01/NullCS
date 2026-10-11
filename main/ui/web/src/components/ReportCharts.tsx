import { useState } from 'react';
import reference from '../lib/score-reference.json';
import { bandLabels, signalBand, scoreBin, type ReportPlayer } from '../lib/report-context';

export function ReportCharts({ players, modelHash }: { players: ReportPlayer[]; modelHash: string | null }) {
  const [selected, setSelected] = useState(players[0]?.steamid ?? '');
  const [metric, setMetric] = useState<'model_score' | 'review_score' | 'calibrated_probability'>('model_score');
  const [bin, setBin] = useState<number | null>(null);
  const player = players.find(p => p.steamid === selected) ?? players[0];
  const matching = modelHash === reference.model_sha256;
  const activeBin = bin ?? (player ? scoreBin(player.model_score) : null);
  const max = Math.max(...reference.negative_counts.map(n => n / reference.negative), ...reference.positive_counts.map(n => n / reference.positive));
  if (!player) return null;
  return <section className="report-charts" aria-label="Interactive score context">
    <div className="chart-heading"><div><h3>Compare this match</h3><p>Select a player to inspect their score against the research data.</p></div>
      <label>Score shown <select value={metric} onChange={e => setMetric(e.target.value as typeof metric)}><option value="model_score">Model score</option><option value="review_score">Review score</option><option value="calibrated_probability">Calibrated estimate</option></select></label></div>
    <div className="player-bars">{players.map(p => { const value = p[metric]; const valid = value !== null && Number.isFinite(value) && value >= 0 && value <= 1; const band = metric === 'model_score' ? signalBand(value, matching) : 'unavailable'; return <button key={p.steamid} aria-pressed={p.steamid === player.steamid} onClick={() => { setSelected(p.steamid); setBin(null); }} className={`player-bar band-${band}`}>
      <span className="bar-name">#{p.rank} {p.name}</span><span className="bar-track" aria-hidden="true"><span style={{ width: valid ? `${value! * 100}%` : '0%' }} /></span><span>{valid ? (value! * 100).toFixed(1) : 'Unavailable'}</span></button>; })}</div>
    <p className="chart-note">Scores shown on a 0–100 scale. Review score includes existing evidence adjustments; calibrated estimate uses the saved calibration. Colors apply only to the raw model score.</p>
    {matching ? <>
      <h3>Where does {player.name} sit?</h3>
      <p><span className={`signal-badge band-${signalBand(player.model_score, matching)}`}>{bandLabels[signalBand(player.model_score, matching)]}</span> Model score: {(player.model_score * 100).toFixed(1)} / 100</p>
      <p>Historical evaluation: {reference.rows.toLocaleString()} player-match records across {reference.demos} demos. Each match was held out from its player-model training fold. Bars show the percentage of each labeled group in a score range.</p>
      <p className="chart-note">Positive labels mark suspected cheating in the dataset; negative labels mark the comparison group. The white line marks this player's raw score.</p>
      <div className="distribution-key"><span>■ Negative label ({reference.negative.toLocaleString()})</span><span>▧ Positive label ({reference.positive.toLocaleString()})</span></div>
      <div className="distribution" role="group" aria-label="Historical raw model score distribution; select a five-point range">
        {reference.negative_counts.map((n, i) => <button key={i} aria-pressed={activeBin === i} aria-label={`Scores ${i * 5} to ${(i + 1) * 5}: ${n} negative labels, ${reference.positive_counts[i]} positive labels`} onClick={() => setBin(i)} onMouseEnter={() => setBin(i)} onFocus={() => setBin(i)}>
          <span className="negative-density" style={{ height: `${n / reference.negative / max * 100}%` }} /><span className="positive-density" style={{ height: `${reference.positive_counts[i] / reference.positive / max * 100}%` }} />
        </button>)}
        {scoreBin(player.model_score) !== null && <span className="score-marker" style={{ left: `${player.model_score * 100}%` }} aria-hidden="true" />}
      </div><div className="chart-axis"><span>0</span><span>Raw model score / 100</span><span>100</span></div>
      <p aria-live="polite" className="bin-detail">{activeBin !== null ? `Score range ${activeBin * 5}–${(activeBin + 1) * 5}: ${reference.negative_counts[activeBin]} negative-label records (${(reference.negative_counts[activeBin] / reference.negative * 100).toFixed(1)}% of that group), ${reference.positive_counts[activeBin]} positive-label records (${(reference.positive_counts[activeBin] / reference.positive * 100).toFixed(1)}%).` : 'No finite score to place on the chart.'}</p>
      <div className="band-guide"><p><b className="band-low">Green / Low</b> Below 20. Limited model signal in this match.</p><p><b className="band-elevated">Yellow / Elevated</b> 20 to below 50. Inspect the encounters and match context.</p><p><b className="band-strong">Red / Strong</b> 50 and above. Prioritize the replay; look for behavior that supports the signal.</p></div>
      <details><summary>Measured threshold tradeoffs and data provenance</summary><p>These are display bands using existing tested cutoffs, not new scoring rules. At the 50-point cutoff, 846 positive-label and 301 negative-label records were flagged; 146 positive-label records fell below it. Green also includes missed cases.</p>
      <div className="table-scroll"><table><caption>Historical raw-score evaluation. Dataset labels are the reference, not independent adjudication.</caption><thead><tr><th>Cutoff / 100</th><th>True positive</th><th>False positive</th><th>False negative</th><th>Precision</th><th>Recall</th></tr></thead><tbody>{reference.thresholds.map(t => <tr key={t.threshold}><td>{t.threshold * 100}</td><td>{t.tp}</td><td>{t.fp}</td><td>{t.fn}</td><td>{(100*t.tp/(t.tp+t.fp)).toFixed(1)}%</td><td>{(100*t.tp/(t.tp+t.fn)).toFixed(1)}%</td></tr>)}</tbody></table></div><p>{reference.note}</p><p className="reference-hash">OOF source SHA-256: {reference.source_sha256}</p></details>
    </> : <p>No matching evaluation reference is bundled for this model. Match scores are shown without benchmark colors or population comparisons.</p>}
  </section>;
}
