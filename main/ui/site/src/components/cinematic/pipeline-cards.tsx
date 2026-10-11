"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { NeuralNetwork } from "./neural-network";
import sample from "../../../public/assets/observatory/encounter-sample.json";

const panels = [
  {
    title: "MATCH RECORDING",
    note: "Illustrative CS2 footage / separate from the analysis samples",
  },
  {
    title: "ENCOUNTER TELEMETRY",
    note: "Actual encounter summaries / de_inferno validation demo",
  },
  {
    title: "ENCOUNTER CONTEXT",
    note: "Recorded encounter summaries / not a raw 32-tick sequence",
  },
  {
    title: "TEMPORAL ENCOUNTER CNN",
    note: "Conceptual network / node counts illustrative, not live activations",
  },
  {
    title: "PLAYER-LEVEL SIGNALS",
    note: "Actual within-lobby percentiles / illustrative player comparison",
  },
  {
    title: "RANKED FOR REVIEW",
    note: "Actual desktop result / ten players from local validation",
  },
];

export function PipelineCards({
  stage,
  motion,
}: {
  stage: number;
  motion: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [foreground, setForeground] = useState(true);
  useEffect(() => {
    const sync = () => setForeground(!document.hidden);
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) =>
      setVisible(entry.isIntersecting),
    );
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  return (
    <div
      ref={host}
      className="pipeline-card-deck"
      data-motion={motion && visible && foreground}
    >
      {panels.map((panel, i) => {
        const active = i === stage;
        return (
          <article
            key={panel.title}
            className="pipeline-media-card"
            data-active={active}
            aria-hidden={!active}
            inert={!active}
            style={
              {
                "--offset": i - stage,
                zIndex: active ? 10 : 6 - Math.abs(i - stage),
              } as CSSProperties
            }
          >
            <header>
              <span>
                0{i + 1} / {panel.title}
              </span>
              <span>NULLCS</span>
            </header>
            <div className="pipeline-card-content">
              {i === 0 && (
                <div className="pipeline-video">
                  {active && visible && foreground && (
                    <video
                      key={String(motion)}
                      src="/assets/observatory/nullcs-broll.mp4"
                      poster="/assets/observatory/nullcs-broll-poster.webp"
                      aria-label="NullCS CS2 gameplay footage"
                      autoPlay={motion}
                      muted
                      loop
                      playsInline
                      controls={false}
                      disablePictureInPicture
                      preload="metadata"
                    >
                      Your browser does not support video playback.
                    </video>
                  )}
                </div>
              )}
              {i === 1 && (
                <div className="telemetry-sheet">
                  <p>EXTRACT / FIRST 7 ENCOUNTERS</p>
                  <table>
                    <caption className="sr-only">
                      Recorded encounter feature values
                    </caption>
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>
                          Aim error
                          <br />
                          (degrees)
                        </th>
                        <th>
                          Input
                          <br />
                          (units)
                        </th>
                        <th>
                          Angular speed
                          <br />
                          (degrees/tick)
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from({ length: 7 }, (_, row) => (
                        <tr key={row}>
                          <th>{String(row + 1).padStart(3, "0")}</th>
                          {sample.channels.map((c) => (
                            <td key={c.key}>{c.values[row].toFixed(4)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="sheet-footer">
                    SOURCE: PARSED DEMO → ENCOUNTER FEATURES
                  </div>
                </div>
              )}
              {i === 2 && (
                <img
                  src="/assets/observatory/real-visibility-context-timeline.webp"
                  alt="Recorded visibility, movement pressure and pre-shot anticipation across encounters, normalized from zero to one"
                  loading="lazy"
                />
              )}
              {i === 3 && <NeuralNetwork />}
              {i === 4 && (
                <img
                  src="/assets/observatory/real-multilens-radar.webp"
                  alt="Actual player percentile positions across process, occlusion, timing, difficulty, stability and neural-network signal"
                  loading="lazy"
                />
              )}
              {i === 5 && (
                <img
                  src="/assets/observatory/desktop-report.webp"
                  alt="Real NullCS desktop results showing ten players ranked for analyst review"
                  loading="lazy"
                />
              )}
            </div>
            <footer>{panel.note}</footer>
          </article>
        );
      })}
    </div>
  );
}
