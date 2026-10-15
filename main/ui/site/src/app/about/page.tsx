import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { githubUrl } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "About NullCS",
  description: "What NullCS looks for in a CS2 replay, how to read its results, and what still needs work.",
};

export default function AboutPage() {
  return (
    <article className="subpage">
      <div className="section-register">
        <span>NULLCS / ABOUT THE PROJECT</span>
        <span>INDEPENDENT RESEARCH</span>
      </div>
      <h1>Look beyond<br /><em>the scoreboard.</em></h1>
      <p className="subpage-intro">
        NullCS examines saved Counter-Strike 2 replays and ranks players for a closer look.
        It studies aim, movement, timing, and visibility to help you find unusual behavior.
        The Windows app runs on your computer.
      </p>
      <div className="research-chapter" style={{ marginTop: 70 }}>
        <div>
          <span className="technical-label">01 / HOW IT WORKS</span>
          <h2>From a replay<br />to a review list.</h2>
        </div>
        <div>
          <p>A high kill count does not tell the whole story. NullCS looks at what happened around an encounter: where a player aimed, when they fired, and what they could see.</p>
          <p>Models trained on gameplay data combine those measurements and rank players within the match. The report gives you a starting point for watching the replay.</p>
          <p>Choose a demo file, wait for the analysis, then compare players and save a report. No account or demo upload is required.</p>
          <Link className="text-link" href="/#pipeline">See the steps <ArrowUpRight size={16} /></Link>
        </div>
      </div>
      <div className="research-chapter">
        <div>
          <span className="technical-label">02 / READING THE RESULTS</span>
          <h2>Start here.<br />Look closer.</h2>
        </div>
        <div>
          <p>Players near the top deserve attention first. A score summarizes what the model found; it is not a verdict about the person.</p>
          <p>Some replays show clear cheating. Others need context about skill, visibility, timing, and the information available to the player. Legitimate players can score highly, and cheating can be missed.</p>
          <p>The app explains the scores in its built-in guide. A player may receive no score if the demo does not contain enough usable evidence.</p>
        </div>
      </div>
      <div className="research-chapter">
        <div>
          <span className="technical-label">03 / WORK IN PROGRESS</span>
          <h2>Test it.<br />Keep improving it.</h2>
        </div>
        <div>
          <p>NullCS is a research beta. Tests check which cases it misses and how often legitimate players receive high scores. The dataset labels are imperfect, and more independently reviewed matches are needed.</p>
          <p>A newer model has been trained and is still being checked. The current download uses the earlier model; research results on GitHub explain which version was tested.</p>
          <p>CS2 updates can also change the data stored in demos. Known issues with reading that data and interpreting scores are documented on GitHub.</p>
          <p>The app analyzes one demo at a time. Comparing the same player across several matches is a future feature.</p>
          <a className="text-link" href={`${githubUrl}/blob/main/RESULTS.md`} target="_blank" rel="noreferrer">Tests, results and limitations <ArrowUpRight size={16} /></a>
        </div>
      </div>
      <div className="research-chapter">
        <div>
          <span className="technical-label">04 / THE RESEARCHER</span>
          <h2>Gerry Jones, Jr.</h2>
        </div>
        <div>
          <p>I started NullCS to explore whether gameplay data could help people review suspicious CS2 matches. It grew from a data science project into a local desktop tool.</p>
          <p>I hold a B.S. in Applied Mathematics and am pursuing a master&apos;s degree in Data Science. The project covers collecting data, building models, testing their mistakes, and making the results usable.</p>
          <p>NullCS reviews saved replays. It does not monitor your computer during play or issue bans, and it is not affiliated with Valve.</p>
          <a className="text-link" href={githubUrl} target="_blank" rel="noreferrer">Code and research notes <ArrowUpRight size={16} /></a>
        </div>
      </div>
      <Link className="instrument-button" href="/analyze">Get the desktop app <ArrowUpRight size={18} /></Link>
    </article>
  );
}
