import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { githubUrl, proofCards, benchmarkStats } from "@/lib/site-content";
export const metadata: Metadata = {
  title: "Research notes",
  description:
    "The methodology, limitations, and independent research behind NullCS behavioral demo analysis.",
};
export default function AboutPage() {
  return (
    <article className="subpage">
      <div className="section-register">
        <span>NULLCS / RESEARCH NOTES</span>
        <span>AN OPEN INVESTIGATION</span>
      </div>
      <h1>
        Behavior deserves
        <br />
        <em>a closer look.</em>
      </h1>
      <p className="subpage-intro">
        NullCS investigates whether structured Counter-Strike 2 demo data can
        surface behavioral anomalies for review. The goal is an inspectable
        starting point, with uncertainty kept in view.
      </p>
      <div className="research-chapter" style={{ marginTop: 70 }}>
        <div>
          <span className="technical-label">01 / METHODOLOGY</span>
          <h2>
            From telemetry
            <br />
            to review priority.
          </h2>
        </div>
        <div>
          <p>
            The pipeline parses gameplay telemetry and builds encounter windows.
            A temporal neural network reads encounter sequences; shared
            aggregation combines those outputs with engineered behavioral
            features. A gradient-boosted model ranks players within a match.
          </p>
          <p>
            The player-level feature contract contains 449 features. Training
            and inference share aggregation logic. Grouped evaluation uses demo
            IDs to separate matches across folds.
          </p>
          <p>
            Timing, visibility, aim correction, movement pressure, and input
            behavior are considered in context. Individual measurements are
            insufficient to establish a cheating conclusion.
          </p>
          <Link className="text-link" href="/#pipeline">
            Explore the process <ArrowUpRight size={16} />
          </Link>
        </div>
      </div>
      <div className="research-chapter">
        <div>
          <span className="technical-label">02 / EVALUATION</span>
          <h2>
            Benchmark context
            <br />
            is part of the result.
          </h2>
        </div>
        <div>
          <p>
            The existing public CS2CD benchmark reports 860 demos after
            filtering, with 992 positive and 5,894 negative player-demo rows.
            Retrieval figures refer to 293 demos containing a suspicious-player
            label.
          </p>
          <p>
            These measurements describe this dataset and evaluation procedure.
            They do not establish production accuracy on unseen CS2 patches,
            skill distributions, or every type of behavioral anomaly.
          </p>
        </div>
      </div>
      <div className="benchmark-strip">
        {benchmarkStats.map((stat) => (
          <div key={stat.label}>
            <span className="technical-label">{stat.label}</span>
            <strong>{stat.value}</strong>
          </div>
        ))}
      </div>
      <details className="research-figures" style={{ marginTop: 30 }}>
        <summary>
          Inspect the existing research figures <span>+</span>
        </summary>
        <div>
          {proofCards.map((card) => (
            <figure key={card.image}>
              <Image
                src={card.image}
                alt={card.title}
                width={1000}
                height={700}
                sizes="(max-width:760px) 90vw, 45vw"
              />
              <figcaption>
                {card.title}. {card.body}
              </figcaption>
            </figure>
          ))}
        </div>
      </details>
      <div className="research-chapter">
        <div>
          <span className="technical-label">03 / INTERPRETATION</span>
          <h2>Signals have limits.</h2>
        </div>
        <div>
          <p>
            False positives exist, including in strong legitimate play. A high
            ranking is a reason to inspect a replay, not evidence of a specific
            cheat or a recommendation to ban a player.
          </p>
          <p>
            Review score, raw model score, and calibrated probability are
            different concepts. Some model selections lack calibration;
            estimates from labeled data may not generalize to a new match.
          </p>
          <p>
            The verified demoparser2 0.41.4 runtime has a known stale
            user-command-value issue. The saved calibrator also produces a
            scikit-learn version warning. Passing the parser column contract
            does not prove that every input value is fresh. These limitations
            are preserved and documented, not hidden by the interface.
          </p>
        </div>
      </div>
      <div className="research-chapter">
        <div>
          <span className="technical-label">04 / THE RESEARCHER</span>
          <h2>Gerry Jones, Jr.</h2>
        </div>
        <div>
          <p>
            NullCS is an independent project by Gerry Jones, Jr., who holds a
            B.S. in Applied Mathematics and is pursuing a master's degree in
            Data Science.
          </p>
          <p>
            The project began after returning to Counter-Strike in April 2025
            and asking whether post-match demo data could support more
            structured review. That question led to demo collection, player
            labeling, feature engineering, model evaluation, and continued
            investigation of difficult cases.
          </p>
          <p>
            This is ongoing research. NullCS is not a kernel anticheat, a
            universal detector, or an automated enforcement system.
          </p>
          <a
            className="text-link"
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
          >
            Examine the repository <ArrowUpRight size={16} />
          </a>
        </div>
      </div>
      <Link className="instrument-button" href="/analyze">
        Get the desktop application <ArrowUpRight size={18} />
      </Link>
    </article>
  );
}
