"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, ArrowRight, Pause, Play } from "lucide-react";
import { InstrumentScene } from "./scene";
import { PipelineCards } from "./pipeline-cards";
import { githubUrl, benchmarkStats } from "@/lib/site-content";

const stages = [
  {
    title: "A match becomes a record.",
    short: "Demo",
    code: ".DEM / INPUT",
    body: "Start with a real Counter-Strike 2 replay. The demo contains the match history the pipeline will examine.",
  },
  {
    title: "Every action has context.",
    short: "Telemetry",
    code: "TICKS / EVENTS",
    body: "Parse player state, view angles, input, shots, damage, and visibility. Preserve timing before looking for patterns.",
  },
  {
    title: "Isolate the encounter.",
    short: "Windows",
    code: "32 TICKS / SEQUENCE",
    body: "Build encounter windows around player interactions. The temporal model reads a sequence, rather than one isolated moment.",
  },
  {
    title: "Read behavior over time.",
    short: "Temporal model",
    code: "CNN / ENCOUNTER",
    body: "The temporal neural network evaluates how behavior develops across an encounter. Its outputs become part of the player-level representation.",
  },
  {
    title: "Bring the signals together.",
    short: "Aggregation",
    code: "449 FEATURES / XGBOOST",
    body: "Shared aggregation combines encounter and behavioral features. Gradient-boosted models produce the existing player-level scores.",
  },
  {
    title: "Give the reviewer a starting point.",
    short: "Review",
    code: "RANKED PLAYERS / OUTPUT",
    body: "Rank players within the match. Keep model scores, calibrated estimates, and review priority distinct. A person makes the judgment.",
  },
] as const;
type Channel = { key: string; label: string; unit: string; values: number[] };
export function CinematicExperience({ channels }: { channels: Channel[] }) {
  const [motion, setMotion] = useState(true),
    [stage, setStage] = useState(0),
    [channel, setChannel] = useState(0),
    [sample, setSample] = useState(0);
  const hero = useRef<HTMLElement>(null),
    pipeline = useRef<HTMLElement>(null),
    showcase = useRef<HTMLDivElement>(null);
  const heroProgress = useRef(0),
    pipelineProgress = useRef(0),
    activeStage = useRef(0);
  const samples = useMemo(() => channels.map((c) => c.values), [channels]);
  useEffect(() => {
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setMotion(!query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const hr = hero.current?.getBoundingClientRect(),
        pr = pipeline.current?.getBoundingClientRect(),
        sr = showcase.current?.getBoundingClientRect();
      if (hr)
        heroProgress.current = Math.max(0, Math.min(1, -hr.top / hr.height));
      if (pr && innerWidth > 760 && motion) {
        const p = Math.max(
          0,
          Math.min(0.999, -pr.top / (pr.height - innerHeight)),
        );
        pipelineProgress.current = p;
        const next = Math.floor(p * 6);
        if (next !== activeStage.current) {
          activeStage.current = next;
          setStage(next);
        }
      }
      if (sr && showcase.current) {
        const p = Math.max(
          -1,
          Math.min(1, (sr.top - innerHeight * 0.4) / innerHeight),
        );
        showcase.current.style.setProperty(
          "--tilt",
          motion ? `${p * 9}deg` : "0deg",
        );
      }
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [motion]);
  function selectStage(index: number) {
    setStage(index);
    activeStage.current = index;
    if (innerWidth > 760 && motion && pipeline.current) {
      const rect = pipeline.current.getBoundingClientRect();
      window.scrollTo({
        top:
          scrollY +
          rect.top +
          ((rect.height - innerHeight) * (index + 0.15)) / 6,
        behavior: "smooth",
      });
    }
  }
  const current = channels[channel],
    max = Math.max(...current.values, 0.001);
  const path = current.values
    .map(
      (v, i) => `${i ? "L" : "M"}${(i / 63) * 1000},${150 - (v / max) * 120}`,
    )
    .join(" ");
  return (
    <div className={`observatory ${motion ? "motion-active" : "motion-still"}`}>
      <section
        className="observatory-hero"
        ref={hero}
        aria-labelledby="hero-title"
      >
        <div className="hero-register">
          <span>
            <i className="status-light" />
            INDEPENDENT RESEARCH / CS2
          </span>
          <span>BEHAVIORAL ANALYSIS SYSTEM</span>
        </div>
        <div className="hero-watermark" aria-hidden="true">
          NULLCS
        </div>
        <div className="hero-instrument">
          <div className="hero-agent" aria-hidden="true">
            <div className="agent-portrait" />
            <span className="agent-registration agent-registration-top">
              CS2 / ENCOUNTER STUDY
            </span>
            <span className="agent-registration agent-registration-bottom">
              AIM / MOVEMENT / TIMING
            </span>
          </div>
          <span className="instrument-caption">
            FIG. 01 / THE ENCOUNTER / CONCEPTUAL VIEW
          </span>
        </div>
        <div className="hero-copy">
          <p className="technical-label">Look closer.</p>
          <h1 id="hero-title">
            Beyond
            <br />
            the <span>score.</span>
          </h1>
          <p className="hero-description">
            Machine learning for Counter-Strike 2 telemetry.
            <br className="desktop-break" /> From replay data to player-level behavioral analysis.
          </p>
          <Link className="instrument-button" href="/analyze">
            Get the desktop app <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="hero-bottom">
          <a href="#signals" className="scroll-cue">
            <ArrowDown size={16} /> ENTER THE OBSERVATORY
          </a>
          <button
            className="motion-control"
            onClick={() => setMotion(!motion)}
            aria-pressed={motion}
          >
            {motion ? <Pause size={12} /> : <Play size={12} />} MOTION{" "}
            {motion ? "ON" : "OFF"}
          </button>
          <span>RESEARCH SIGNALS. HUMAN JUDGMENT.</span>
        </div>
      </section>
      <section
        className="signal-section editorial-section"
        id="signals"
        aria-labelledby="signals-title"
      >
        <div className="section-register">
          <span>01 / OBSERVATION</span>
          <span>FROM PLAY TO PATTERN</span>
        </div>
        <div className="section-intro">
          <h2 id="signals-title">
            The moments
            <br />
            between <em>moments.</em>
          </h2>
          <p>
            A flick is one moment. How the crosshair arrives, settles, and
            responds is a sequence. NullCS studies the structure around player
            interactions.
          </p>
        </div>
        <div className="signal-console">
          <div className="signal-tools">
            <span className="technical-label">
              RECORDED ENCOUNTERS / DE_INFERNO
            </span>
            <div role="group" aria-label="Telemetry channel">
              {channels.map((c, i) => (
                <button
                  key={c.key}
                  aria-pressed={channel === i}
                  onClick={() => setChannel(i)}
                >
                  {String(i + 1).padStart(2, "0")} {c.label}
                </button>
              ))}
            </div>
          </div>
          <div className="signal-space">
            <InstrumentScene
              mode="telemetry"
              samples={samples}
              channel={channel}
              motion={motion}
            />
            <div className="signal-axis">
              <span>ENCOUNTER 01</span>
              <span>64</span>
            </div>
          </div>
          <div className="signal-readout">
            <div>
              <span className="technical-label">{current.label}</span>
              <strong>
                {current.values[sample].toFixed(2)}{" "}
                <small>{current.unit}</small>
              </strong>
            </div>
            <div className="signal-chart">
              <svg
                viewBox="0 0 1000 170"
                role="img"
                aria-label={`${current.label} across 64 recorded encounters`}
              >
                <path
                  d={path}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <line
                  x1={(sample / 63) * 1000}
                  x2={(sample / 63) * 1000}
                  y1="0"
                  y2="170"
                  stroke="#e0e6d0"
                  strokeDasharray="4 6"
                />
              </svg>
              <label htmlFor="sample-scrub">
                Inspect encounter {String(sample + 1).padStart(2, "0")}
                <input
                  id="sample-scrub"
                  type="range"
                  min="0"
                  max="63"
                  value={sample}
                  onChange={(e) => setSample(Number(e.target.value))}
                />
              </label>
            </div>
          </div>
          <p className="data-caption">
            Actual encounter summaries from the local validation demo. Each 3D
            trace is scaled independently for legibility; it is not a detection
            result.{" "}
            <a href="/assets/observatory/encounter-sample.json">
              Inspect source data <ArrowUpRight size={12} />
            </a>
          </p>
        </div>
        <div className="signal-footnote">
          <span>INPUT &rarr; RESPONSE &rarr; CONTEXT</span>
          <p>
            Timing. Aim process. Movement. Visibility.
            <br />
            No single measurement tells the whole story.
          </p>
        </div>
      </section>
      <section
        className="pipeline-sequence"
        id="pipeline"
        ref={pipeline}
        aria-label="How NullCS processes a demo"
      >
        <div className="pipeline-sticky">
          <div className="section-register">
            <span>02 / THE ANALYSIS</span>
            <span>ONE PIPELINE. MULTIPLE PERSPECTIVES.</span>
          </div>
          <div className="pipeline-body">
            <div className="pipeline-copy">
              <span className="stage-number">
                0{stage + 1}
                <small>/ 06</small>
              </span>
              <p className="technical-label">{stages[stage].code}</p>
              <h2 key={stage}>{stages[stage].title}</h2>
              <p>{stages[stage].body}</p>
            </div>
            <div className="pipeline-object">
              <PipelineCards stage={stage} motion={motion} />
            </div>
          </div>
          <nav className="stage-navigation" aria-label="Pipeline stages">
            {stages.map((s, i) => (
              <button
                key={s.short}
                aria-current={stage === i ? "step" : undefined}
                onClick={() => selectStage(i)}
              >
                <span>0{i + 1}</span>
                {s.short}
                <i />
              </button>
            ))}
          </nav>
          <details className="pipeline-transcript">
            <summary>Read the full pipeline</summary>
            <ol>
              {stages.map((s) => (
                <li key={s.short}>
                  <strong>{s.title}</strong> {s.body}
                </li>
              ))}
            </ol>
          </details>
        </div>
      </section>
      <section
        className="desktop-section editorial-section"
        id="desktop"
        aria-labelledby="desktop-title"
      >
        <div className="section-register">
          <span>03 / THE INSTRUMENT, IN YOUR HANDS</span>
          <span>WINDOWS DESKTOP / BETA</span>
        </div>
        <div className="section-intro">
          <h2 id="desktop-title">
            Your match.
            <br />
            <em>Your machine.</em>
          </h2>
          <div>
            <p>
              The research pipeline, packaged for local analysis. Drop a demo.
              Follow the analysis. Leave with a clear order for review.
            </p>
            <Link className="instrument-button" href="/analyze">
              Download NullCS <ArrowUpRight size={18} />
            </Link>
          </div>
        </div>
        <div className="desktop-perspective" ref={showcase}>
          <div className="desktop-frame">
            <div className="window-trim">
              <span>
                <i />
                <i />
                <i />
              </span>
              <span>NULLCS / LOCAL ANALYSIS</span>
              <span>WINDOWS x64</span>
            </div>
            <Image
              src="/assets/observatory/desktop-report.webp"
              alt="Actual NullCS desktop report showing ranked players with separate review scores, model scores, and calibrated estimates"
              width={1700}
              height={1125}
              sizes="(max-width: 760px) 100vw, 85vw"
            />
          </div>
          <div className="desktop-shadow" />
        </div>
        <div className="desktop-specs">
          <p>
            ACTUAL APPLICATION CAPTURE
            <br />
            <span>Local validation demo / de_inferno</span>
          </p>
          <p>
            LOCAL PROCESSING
            <br />
            <span>No demo uploads. No account.</span>
          </p>
          <p>
            READABLE OUTPUT
            <br />
            <span>Ranked players. Plain-text reports.</span>
          </p>
        </div>
      </section>
      <section
        className="research-section editorial-section"
        id="proof"
        aria-labelledby="research-title"
      >
        <div className="section-register">
          <span>04 / RESEARCH RECORD</span>
          <span>MEASURED. DOCUMENTED. OPEN TO SCRUTINY.</span>
        </div>
        <div className="section-intro">
          <h2 id="research-title">
            Evidence before
            <br />
            <em>certainty.</em>
          </h2>
          <p>
            Five-fold internal evaluation keeps test groups out of every learned
            stage, including CNN feature generation and calibration. These results
            describe the corrected research baseline on historical source labels.
            They do not validate the current desktop release or replace an
            independent real-world test.
          </p>
        </div>
        <div className="benchmark-strip">
          {benchmarkStats.map((stat, i) => (
            <div key={stat.label}>
              <span className="technical-label">
                0{i + 1} / {stat.label}
              </span>
              <strong>{stat.value}</strong>
            </div>
          ))}
        </div>
        <div className="research-record">
          <span className="record-index">RECORD / 001</span>
          <div>
            <h3>Follow the methodology.</h3>
            <p>
              Trace the work from telemetry to 449 player-level features,
              temporal encounter modeling, and gradient boosting. Inspect
              grouped evaluation, calibration, and documented failure cases.
            </p>
          </div>
          <Link className="text-link" href="/about">
            Research notes <ArrowUpRight size={18} />
          </Link>
        </div>
        <details className="research-figures">
          <summary>
            Open the corrected internal benchmark figures <span>+</span>
          </summary>
          <div>
            {[
              {
                src: "corrected-score-distributions.png",
                title: "Corrected raw-score distributions",
              },
              {
                src: "corrected-review-retrieval.png",
                title: "Review retrieval including unscored matches",
              },
              {
                src: "corrected-calibration.png",
                title: "Disjoint calibration evaluation",
              },
            ].map((plot) => (
              <figure key={plot.src}>
                <Image
                  src={`/assets/proof-pack/${plot.src}`}
                  alt={plot.title}
                  width={1000}
                  height={700}
                  sizes="(max-width: 760px) 90vw, 45vw"
                />
                <figcaption>
                  {plot.title} / internal evaluation, October 2026
                </figcaption>
              </figure>
            ))}
          </div>
        </details>
      </section>
      <section className="interpretation editorial-section">
        <div className="section-register">
          <span>05 / INTERPRETATION</span>
          <span>THE HUMAN STAYS IN THE LOOP</span>
        </div>
        <p className="closing-statement">
          Measure the behavior.
          <br />
          <span>Examine the evidence.</span>
        </p>
        <div className="closing-bottom">
          <p>
            Some matches show clear cheating behavior. Others require encounter
            context and evidence across matches. NullCS measures behavioral
            signals, ranks players, and shows score and benchmark context.
            Multi-demo player analysis is a planned research direction; the
            current app processes one demo at a time.
          </p>
          <div>
            <Link href="/analyze" className="instrument-button">
              Get the desktop app <ArrowUpRight size={18} />
            </Link>
            <a
              href={githubUrl}
              className="text-link"
              target="_blank"
              rel="noreferrer"
            >
              Explore the repository <ArrowRight size={16} />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
