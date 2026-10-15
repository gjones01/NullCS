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
        NullCS is an end-to-end data science project for Counter-Strike 2:
        replay parsing, behavioral feature engineering, temporal modeling,
        player ranking, and a local desktop application. It turns match telemetry
        into a ranked list of players for replay review.
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
            The ranking model uses 449 features. Training and analysis use the
            same feature calculations. The new evaluation keeps each match and
            known repeated players together when separating training from testing.
          </p>
          <p>
            Timing, visibility, aim correction, movement pressure, and input
            behavior provide complementary signals. The report separates the
            raw model output, calibrated estimate, and evidence-adjusted review score.
          </p>
          <p>
            The parser rejects missing required model inputs. Inference records
            model and parser versions, making changes and input failures
            traceable when CS2 updates.
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
            The October 2026 internal evaluation scores 6,886
            player-match records across 860 of 894 historical demos: 992
            positive and 5,894 negative source labels. Matches, overlapping
            windows, and known repeated-player groups stay together across folds.
          </p>
          <p>
            Raw scores reach average precision of 0.797 and ROC-AUC of 0.957.
            For each test group, the CNN, XGBoost and calibration are fitted
            without those matches. CNN features used to train XGBoost also
            come from models that have not trained on those groups. Review
            scores have average precision of 0.764 and ROC-AUC of 0.939.
          </p>
          <p>
            The desktop beta still uses the earlier models. We could not fully
            match their training files, so we rebuilt the evaluation. The new
            model needs better calibration before release. Some dataset labels
            and player identities also need verification. These are internal
            benchmarks, not a measured success rate on new matches.
          </p>
          <a className="text-link" href={`${githubUrl}/blob/main/RESEARCH_VALIDATION.md`} target="_blank" rel="noreferrer">
            Read the research notes <ArrowUpRight size={16} />
          </a>
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
          <h2>Interpret the evidence.</h2>
        </div>
        <div>
          <p>
            Some replays show clear cheating behavior. Other cases need encounter
            context: visibility, timing, player skill, and what information was
            available. Strong model signals focus that review; false positives
            and missed cases are measured in the evaluation.
          </p>
          <p>
            Review score, raw model score, and calibrated probability are
            different concepts. Some model selections lack calibration;
            estimates from labeled data may not generalize to a new match.
          </p>
          <p>
            Next research direction: compare the same player across multiple
            demos, measuring whether unusual behavior repeats. The current app
            processes one demo at a time; player-history analysis is not yet available.
          </p>
          <p>
            Known limits: the parser can retain old input-command values, and
            the released calibration file reports a library-version warning.
            The research notes explain these issues and what has been tested.
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
