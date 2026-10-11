import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { getCurrentWebview } from '@tauri-apps/api/webview';
import { isDesktopShell, startDesktopService, pickDesktopDemoFile } from './desktopBridge';
import { setApiAccessToken, setApiBaseUrl, getApiAccessToken, getApiBaseUrl } from './runtimeConfig';
import { getHealth, getStatus, queueLocalDemoPath, type DemoStatus } from './lib/api';
import { DesktopAtmosphere } from './components/DesktopAtmosphere';
import { ReportCharts } from './components/ReportCharts';
import reference from './lib/score-reference.json';
import { signalBand, bandLabels } from './lib/report-context';
import './desktop.css';

type Player = { rank: number; steamid: string; name: string; review_score: number; model_score: number; calibrated_probability: number | null; confidence: number | null };
type Result = { schema_version: string; job_id: string; filename: string; map_name: string; players: Player[]; warnings: string[]; model: { name: string; sha256: string; calibration_used: boolean }; parser_version: string };
type Update = { configured: boolean; version: string | null; notes: string | null };
const glossary = [
  ['Review score', 'The score used to order players, after calibration when available and adjustments for limited evidence.'],
  ['Rank', 'The order to review players in this match. Number 1 has the highest review score.'],
  ['Model score', 'The original model output. Higher scores indicate a closer match to patterns learned from positively labeled examples.'],
  ['Calibrated estimate', 'A model estimate adjusted using labeled data. It may not transfer reliably to your match. A dash means this model has no calibration.'],
  ['Evidence confidence', 'How much usable evidence supports the score. Sparse encounters can limit the assessment.'],
  ['Signal color', 'Green: below 20. Yellow: 20 to below 50. Red: 50 or above. These tested raw-score cutoffs help prioritize review; inspect the distribution to see their tradeoffs.'],
] as const;
const score = (value: number | null) => value === null || !Number.isFinite(value) ? '-' : (value * 100).toFixed(1);
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export default function DesktopApp() {
  const [engine, setEngine] = useState('Starting local engine');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [path, setPath] = useState('');
  const [job, setJob] = useState('');
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [sound, setSound] = useState(false);
  const [motion, setMotion] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [update, setUpdate] = useState<Update | null>(null);
  const [updateMessage, setUpdateMessage] = useState('');
  const [updating, setUpdating] = useState(false);
  const [checking, setChecking] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const readyRef = useRef(false), busyRef = useRef(false);
  const starting = useRef<Promise<void> | null>(null);
  const maxBytes = useRef(1024 ** 3);

  useEffect(() => {
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setMotion(!preference.matches);
    sync(); preference.addEventListener('change', sync);
    return () => preference.removeEventListener('change', sync);
  }, []);

  function chime() {
    if (!sound) return;
    const ctx = audio.current ?? (audio.current = new AudioContext());
    void ctx.resume();
    const oscillator = ctx.createOscillator(), gain = ctx.createGain();
    oscillator.type = 'sine'; oscillator.frequency.setValueAtTime(520, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(780, ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.025, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.22);
    oscillator.connect(gain); gain.connect(ctx.destination); oscillator.start(); oscillator.stop(ctx.currentTime + 0.23);
  }

  async function boot() {
    if (starting.current) return starting.current;
    starting.current = (async () => {
      setError(''); setReady(false); readyRef.current = false; setEngine('Checking local engine');
      if (!isDesktopShell()) { setEngine('Desktop preview'); setError('Open the installed NullCS application to analyze local demos.'); return; }
      const service = await startDesktopService();
      if (!service?.healthy) { setEngine('Engine unavailable'); setError(service?.error || 'The local engine could not start. Retry or reinstall the latest client.'); return; }
      setApiBaseUrl(service.api_base_url); setApiAccessToken(service.api_key);
      try {
        const health = await getHealth(); maxBytes.current = health.max_upload_bytes || 1024 ** 3;
        setReady(true); readyRef.current = true; setEngine('Local engine ready');
      } catch (e) { setError(message(e)); setEngine('Engine unavailable'); }
    })().finally(() => { starting.current = null; });
    return starting.current;
  }

  async function checkUpdate() {
    if (!isDesktopShell()) return;
    setChecking(true); setUpdateMessage('Checking for updates...');
    try {
      const next = await invoke<Update>('desktop_check_update'); setUpdate(next);
      setUpdateMessage(!next.configured ? 'Automatic updates are not configured in this beta. New installers are available through GitHub Releases.' : next.version ? `Version ${next.version} is available.` : 'You have the latest available release.');
    } catch { setUpdateMessage('Update check unavailable. Try again when online.'); }
    finally { setChecking(false); }
  }

  useEffect(() => { void boot(); void checkUpdate(); return () => { void audio.current?.close(); }; }, []);
  useEffect(() => {
    const timer = window.setInterval(() => { if (!document.hidden && !busyRef.current) void checkUpdate(); }, 6 * 60 * 60 * 1000);
    return () => clearInterval(timer);
  }, []);

  function choose(value: string) {
    if (busyRef.current) return;
    if (!value.toLowerCase().endsWith('.dem')) { setError('Choose a Counter-Strike 2 .dem file.'); return; }
    setPath(value); setError(''); setResult(null); setStatus(null);
  }
  useEffect(() => {
    if (!isDesktopShell()) return;
    let disposed = false; let unlisten: (() => void) | undefined;
    void getCurrentWebview().onDragDropEvent(event => {
      if (event.payload.type === 'over') setDragging(true);
      if (event.payload.type === 'leave') setDragging(false);
      if (event.payload.type === 'drop') {
        setDragging(false);
        if (event.payload.paths.length !== 1) { setError('Drop one demo at a time.'); return; }
        choose(event.payload.paths[0]);
      }
    }).then(stop => { if (disposed) stop(); else unlisten = stop; }).catch(() => { if (!disposed) setError('Drag and drop is unavailable. Use Choose demo.'); });
    return () => { disposed = true; unlisten?.(); };
  }, []);

  async function analyze() {
    if (!readyRef.current || busyRef.current || updating || !path) return;
    chime(); setJob(''); setStatus(null); busyRef.current = true; setBusy(true); setError(''); setResult(null);
    try { const queued = await queueLocalDemoPath(path); setJob(queued.demo_id); }
    catch (e) { setError(message(e)); busyRef.current = false; setBusy(false); }
  }
  useEffect(() => {
    if (!job || !busy) return;
    let disposed = false; let timer: number; let failures = 0;
    const poll = async () => {
      try {
        const next = await getStatus(job); if (disposed) return;
        failures = 0; setStatus(next);
        if (next.state === 'error') throw new Error(next.error || 'Analysis failed. Try the latest client or another demo.');
        if (next.state === 'done') {
          const response = await fetch(`${getApiBaseUrl()}/desktop/demo/${encodeURIComponent(job)}/result`, { headers: { 'X-NULLCS-KEY': getApiAccessToken() }, signal: AbortSignal.timeout(30000) });
          if (!response.ok) throw new Error('The result could not be read. Retry this demo.');
          const data = await response.json() as Result;
          if (disposed) return;
          setResult(data); setBusy(false); busyRef.current = false; return;
        }
      } catch (e) {
        if (disposed) return;
        failures++;
        // Explicit pipeline errors terminate immediately; transient connection failures get retries.
        if (failures >= 3 || (e instanceof Error && !e.message.includes('unavailable'))) {
          setError(message(e)); setBusy(false); busyRef.current = false;
          if (message(e).includes('unavailable')) { setReady(false); readyRef.current = false; setEngine('Engine unavailable'); }
          return;
        }
      }
      timer = window.setTimeout(poll, 2500);
    };
    void poll(); return () => { disposed = true; clearTimeout(timer); };
  }, [job, busy]);

  async function exportReport() {
    if (!result) return;
    chime();
    const lines = ['NULLCS - MATCH REVIEW', result.filename, `Map: ${result.map_name}`, '',
      'Some matches show clear cheating behavior. Others require a closer look at encounters, match context, and repeated behavior across demos.', '',
      ...result.players.map(p => `#${p.rank} ${p.name} (${p.steamid})\n  ${bandLabels[signalBand(p.model_score, result.model.sha256 === reference.model_sha256)]} | Review score: ${score(p.review_score)}/100 | Model score: ${score(p.model_score)}/100 | Calibrated estimate: ${score(p.calibrated_probability)}${p.calibrated_probability === null ? '' : '%'} | Evidence confidence: ${score(p.confidence)}/100`),
      '', 'REFERENCE CONTEXT', result.model.sha256 === reference.model_sha256 ? 'Historical grouped evaluation: 6,886 player-match records, 860 demos. At raw score >= 50/100: 846 true positives, 301 false positives, 146 false negatives. Display bands do not change scores. Interactive distributions are available inside the app.' : 'No matching benchmark reference is bundled for this model.',
      '', 'HOW TO READ THIS REPORT', ...glossary.map(([term, definition]) => `${term}: ${definition}`), '', 'LIMITATIONS', ...result.warnings,
      '', `Model: ${result.model.name}`, `Model SHA-256: ${result.model.sha256}`, `Parser: ${result.parser_version || 'Not recorded'}`, `Analysis: ${result.job_id}`];
    try { await invoke<boolean>('desktop_save_report', { report: lines.join('\n') }); }
    catch { setError('The report could not be saved. Try another location.'); }
  }

  return <div className="desktop-shell">
    <DesktopAtmosphere paused={!motion || busy || updating} />
    <header className="app-bar"><a className="wordmark" href="#workspace"><svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="11" fill="none" stroke="currentColor" /><circle cx="14" cy="14" r="4" fill="currentColor" /></svg> <span>NULLCS<small>LOCAL DEMO ANALYSIS</small></span></a>
      <div className="app-controls"><button aria-pressed={motion} onClick={() => setMotion(!motion)}>Motion {motion ? 'on' : 'off'}</button><button aria-pressed={sound} onClick={() => { setSound(!sound); }}>Sound {sound ? 'on' : 'off'}</button><a href="#legend">Score guide</a></div>
    </header>
    <main id="workspace">
      <section className="intro"><div><p className="eyebrow">YOUR MATCH. A CLOSER LOOK.</p><h1>Find the players<br /><span>worth a second look.</span></h1><p>Drop a demo. Get a clear review order.<br />Everything is processed on your computer.</p></div>
        <div className="glass engine-card"><span className={`status-dot ${ready ? 'online' : ''}`} /><span>{engine}</span><small>CPU analysis  /  No account needed</small>{!ready && <button onClick={() => void boot()}>Retry engine</button>}</div>
      </section>
      <p className="beta-note"><b>BETA</b> Models will keep improving with newer data. Scores support human review, never automatic bans.</p>
      {update?.version && <aside className="update-notice" role="status"><strong>NullCS {update.version} is available.</strong> Update for the latest parser and model fixes. <a href="#client-updates">Review update</a></aside>}
      {error && <div className="error-box" role="alert">{error}</div>}
      <section className="analysis-grid">
        <div className={`glass intake ${dragging ? 'dragging' : ''}`}>
          <div className="drop-icon" aria-hidden="true">&#8593;</div><p className="eyebrow">01 / SELECT A REPLAY</p>
          <h2>{path ? path.split(/[\\/]/).pop() : 'Your next match review'}</h2>
          <p>Drop one .dem file here, or choose it below.<br />Up to {(maxBytes.current / 1024 ** 3).toFixed(0)} GiB  /  Counter-Strike 2</p>
          <div className="button-row"><button disabled={!ready || busy || updating} onClick={async () => { chime(); const selected = await pickDesktopDemoFile(); if (selected) choose(selected); }}>Choose demo</button><button className="primary" disabled={!ready || !path || busy || updating} onClick={() => void analyze()}>{busy ? 'Analyzing...' : 'Analyze demo'}</button></div>
          <small>Only analyze demos you have permission to use. Local reports stay on this computer.</small>
        </div>
        <div className="glass progress-card" aria-live="polite"><p className="eyebrow">02 / ANALYSIS</p><h2>{result ? 'Your report is ready.' : busy ? status?.stage || 'Preparing demo' : status?.state === 'error' ? 'Analysis stopped.' : 'Ready when you are.'}</h2>
          <ol>{['Parsing', 'Feature processing', 'Temporal inference', 'Scoring', 'Results ready'].map((label, i) => <li key={label} className={(status?.stage_index || 0) >= i + 1 ? 'reached' : ''}><span>{String(i + 1).padStart(2, '0')}</span>{label}</li>)}</ol>
          <small>{busy ? 'Stages follow the engine. Large demos can take longer. Keep NullCS open.' : 'Results appear after the pipeline finishes. No estimated progress percentages.'}</small>
        </div>
      </section>
      {result && <section className="glass results" aria-labelledby="results-title"><div className="result-heading"><div><p className="eyebrow">03 / MATCH REPORT</p><h2 id="results-title">Start your review here.</h2><p>{result.filename}  /  {result.map_name}  /  {result.players.length} players</p></div><button className="primary" onClick={exportReport}>Save simple report</button></div>
        <div className="table-scroll"><table><thead><tr><th>Review order</th><th>Player</th><th><a href="#legend">Review score</a></th><th>Model score</th><th>Calibrated estimate</th></tr></thead><tbody>{result.players.map(p => <tr key={p.steamid}><td><span className="rank">{String(p.rank).padStart(2, '0')}</span></td><td>{p.name}<small>{p.steamid}</small></td><td><b>{score(p.review_score)}</b><span className="out-of"> / 100</span></td><td>{score(p.model_score)}<span className="out-of"> / 100</span></td><td>{score(p.calibrated_probability)}{p.calibrated_probability !== null && '%'}</td></tr>)}</tbody></table></div>
        <ReportCharts key={result.job_id} players={result.players} modelHash={result.model.sha256} />
        <details><summary>Result limitations and model details</summary><ul>{result.warnings.map(w => <li key={w}>{w}</li>)}</ul><p>Model: {result.model.name}  /  Parser: {result.parser_version || 'Not recorded'}</p></details>
      </section>}
      <section id="legend" className="legend"><div><p className="eyebrow">READING THE RESULTS</p><h2>Score, evidence, context.</h2><p>Some matches show clear cheating behavior. Others require a closer look at encounters, match context, and repeated behavior across demos.</p><p>Planned research: compare a player across multiple demos to separate isolated events from recurring patterns. This build analyzes one demo at a time.</p></div><dl>{glossary.map(([term, definition]) => <div key={term}><dt>{term}</dt><dd>{definition}</dd></div>)}</dl></section>
      <footer id="client-updates" className="glass update-panel"><div><b>Keep your parser current.</b><p>{updateMessage || 'Client updates include tested parser, dependency, and model changes.'}</p>{update?.version && <p className="release-notes">{update.notes}</p>}</div><div className="button-row"><button disabled={checking || updating} onClick={() => void checkUpdate()}>Check for updates</button>{update?.version && <button className="primary" disabled={busy || updating} onClick={async () => { setUpdating(true); setUpdateMessage('Downloading and verifying the update. NullCS will close to install.'); try { await invoke('desktop_install_update'); } catch { setUpdateMessage('Update failed. Nothing unverified was installed; check again to retry.'); setUpdating(false); void boot(); } }}>{updating ? 'Updating...' : busy ? 'Finish analysis to update' : 'Update and restart'}</button>}</div></footer>
    </main><div className="bottom-note">NULLCS / BEHAVIORAL RESEARCH  /  LOCAL FIRST</div>
  </div>;
}
