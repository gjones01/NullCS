import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Github } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { aboutPrinciples, benchmarkStats, githubUrl } from "@/lib/site-content";

const sections = [
  {
    title: "What NullCS analyzes",
    body: "NullCS focuses on structured Counter-Strike 2 demo analysis. The current public stack works from 449 player-level engineered features, while deeper encounter-level timing and process channels are used to study how suspicious behavior actually unfolds.",
  },
  {
    title: "Why behavioral review matters",
    body: "Suspicious play can look very different from match to match. That makes review hard to scale and easy to oversimplify. A behavioral approach creates a more disciplined way to surface demos or players that deserve closer attention while staying conservative on strong legitimate play.",
  },
  {
    title: "The ML and research angle",
    body: "The project is built as research infrastructure first. Models are useful because they can rank and organize patterns, but the real value comes from keeping the signals measurable, benchmarkable, and explainable across suspicious, legit, and pro stress-test slices.",
  },
  {
    title: "Why this is not a universal cheat detector",
    body: "NullCS is intentionally framed around explainability and analysis depth. It does not claim to detect every cheat type, and it is not presented as a one-click verdict system. The point is better review support, not absolute certainty.",
  },
] as const;

const founderNotes = [
  "B.S. in Applied Mathematics, currently completing an M.S. in Applied Data Science.",
  "Long-time gamer and active Counter-Strike player who came back to CS in April 2025 and kept running into obvious cheating with little visible enforcement response.",
  "Built NullCS as a research effort around irregular-play review, not as a kernel-level anticheat or a claim of universal detection.",
  "Collected demos, manually sourced and labeled SteamIDs, iterated through multiple modeling approaches, and studied cheat communities directly to understand how lower-visibility behavior avoids simple detection.",
] as const;

export default function AboutPage() {
  return (
    <div className="relative overflow-hidden">
      <section className="relative border-b border-white/8">
        <div className="absolute inset-0">
          <Image src="/assets/aboutpagebg.png" alt="About page background" fill priority className="object-cover object-center opacity-20" />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(5,7,12,0.45),rgba(5,7,12,0.94))]" />
        </div>
        <div className="container relative py-20 sm:py-28">
          <Chip>About NullCS</Chip>
          <div className="mt-7 grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-end">
            <div className="max-w-3xl">
              <h1 className="font-display text-5xl tracking-[-0.07em] text-white sm:text-6xl">
                A behavioral analysis project built to stay technical, explainable, and credible.
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-300">
                NullCS exists to study whether suspicious behavior in Counter-Strike 2 demos can be surfaced in a way that is measurable enough for research and understandable enough for real review, especially in the harder cases where strong legitimate players and subtle assistance can look uncomfortably close.
              </p>
            </div>
            <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-7">
              <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Public framing</div>
              <p className="mt-4 text-sm leading-7 text-zinc-300">
                NullCS is presented here as a real technical project: benchmark-backed, explainable, and conservative about what it claims. The site is meant to make the research legible without flattening it into generic startup language.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 sm:py-28">
        <div className="container grid gap-5 lg:grid-cols-3">
          {aboutPrinciples.map((principle) => (
            <article key={principle.title} className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-7">
              <h2 className="font-display text-2xl tracking-[-0.05em] text-white">{principle.title}</h2>
              <p className="mt-4 text-sm leading-7 text-zinc-400">{principle.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-white/8 bg-white/[0.02] py-16">
        <div className="container grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {benchmarkStats.map((stat) => (
            <div key={stat.label} className="rounded-[1.5rem] border border-white/10 bg-[#0a0d14] p-5">
              <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">{stat.label}</div>
              <div className="mt-3 font-display text-4xl tracking-[-0.05em] text-white">{stat.value}</div>
            </div>
          ))}
        </div>
        <div className="container mt-8 grid gap-5 lg:grid-cols-2">
          <article className="rounded-[1.7rem] border border-white/10 bg-[#0a0d14] p-6">
            <h2 className="font-display text-2xl tracking-[-0.05em] text-white">What these values mean</h2>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              The first three numbers are not “probability of cheating” claims. They summarize how loud the strongest player signal looks inside each benchmark slice. “Median top-ranked signal” means: for each demo, take the highest-ranked player in the lobby, then look at the middle value across that group of demos.
            </p>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              So a suspicious median of <span className="text-zinc-200">0.748</span> versus <span className="text-zinc-200">0.0073</span> on held-out normal legit demos means the suspicious slice is surfacing much more strongly, while the legit slice stays almost pinned near zero. The pro value staying at <span className="text-zinc-200">0.0073</span> matters for the same reason: strong legitimate players are not being inflated just because they are skilled.
            </p>
          </article>
          <article className="rounded-[1.7rem] border border-white/10 bg-[#0a0d14] p-6">
            <h2 className="font-display text-2xl tracking-[-0.05em] text-white">Why that is significant</h2>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              For a review system like NullCS, the shape is more important than the raw magnitude. You want suspicious benchmark demos to be visibly louder, while normal legit and pro stress-test demos stay quiet. If all three slices were high, the system would be noisy. If all three were low, it would not be useful.
            </p>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              The <span className="text-zinc-200">0.90</span> top-3 retrieval number answers a different question: how often does a labeled suspicious player appear somewhere in the top three ranked players for a suspicious benchmark demo? That matters because NullCS is framed as triage and review support. The goal is to reliably surface the right players near the top of the lobby, not to claim that one score is a final verdict.
            </p>
          </article>
        </div>
      </section>

      <section className="border-y border-white/8 bg-white/[0.02] py-20 sm:py-28">
        <div className="container grid gap-5 lg:grid-cols-2">
          {sections.map((section) => (
            <article key={section.title} className="rounded-[1.8rem] border border-white/10 bg-[#0a0d14] p-7">
              <h2 className="font-display text-3xl tracking-[-0.05em] text-white">{section.title}</h2>
              <p className="mt-4 text-sm leading-7 text-zinc-400">{section.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="py-20 sm:py-28">
        <div className="container grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <article className="rounded-[2rem] border border-white/10 bg-[#0a0d14] p-8">
            <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">About the researcher</div>
            <h2 className="mt-4 font-display text-4xl tracking-[-0.06em] text-white">Gerry Jones, Jr.</h2>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-300">
              NullCS is being built by Gerry Jones, Jr., whose background combines applied mathematics, graduate study in data science, and a direct personal interest in Counter-Strike. The project started after returning to CS in April 2025 and repeatedly encountering blatant abuse, including aimbotting, triggerbotting, and spinbotting, with the obvious question of why some of those cases appeared to move through the ecosystem without meaningful response.
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              That turned into a research problem rather than a complaint. The goal was not to build an anticheat or market a magical detector. The goal was to investigate whether suspicious behavior in demos could be surfaced more systematically, including both the easy cases and the harder ones: aim assist, recoil assist, and information abuse that often try to stay just subtle enough to blend into strong legitimate play.
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              Building that required repeated iteration. The work has included sourcing demo data, manually pulling and labeling SteamIDs for training, testing different feature and modeling strategies, and even spending time inside cheat communities to better understand how players discuss avoiding bans and staying below the threshold of current systems such as VAC. There is still substantial work ahead, but the current state of NullCS already reflects significant progress in turning that research into measurable review infrastructure.
            </p>
          </article>
          <article className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.10),rgba(9,11,18,0.98))] p-8">
            <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Research context</div>
            <h2 className="mt-4 font-display text-3xl tracking-[-0.05em] text-white">Why that background matters here</h2>
            <div className="mt-6 space-y-4">
              {founderNotes.map((note) => (
                <p key={note} className="border-l border-white/10 pl-4 text-sm leading-7 text-zinc-300">
                  {note}
                </p>
              ))}
            </div>
            <p className="mt-6 text-sm leading-7 text-zinc-400">
              The result is a project framed around careful review support: technically serious, explicit about uncertainty, and grounded in the practical realities of how suspicious play actually presents itself in Counter-Strike demos.
            </p>
          </article>
        </div>
      </section>

      <section className="py-20 sm:py-28">
        <div className="container grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.12),rgba(9,11,18,0.98))] p-8">
            <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Project direction</div>
            <h2 className="mt-4 font-display text-4xl tracking-[-0.06em] text-white">A public research site now, a deeper review product later.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              The current release is meant to communicate the benchmark story, the modeling direction, and the level of technical depth behind NullCS. The architecture is still set up cleanly so the review client and future app-connected layers can be added without rebuilding the public-facing foundation.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href={githubUrl} target="_blank" rel="noreferrer">
                <Button size="lg">
                  <Github className="h-4 w-4" />
                  View GitHub
                </Button>
              </Link>
              <Link href="/">
                <Button size="lg" variant="secondary">
                  Back to homepage
                  <ArrowUpRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
          <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
            <div className="relative aspect-[4/3]">
              <Image src="/assets/UIPopUp.PNG" alt="NullCS UI concept panel" fill className="object-cover object-center opacity-80" />
              <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0.08),rgba(7,9,14,0.88))]" />
            </div>
            <div className="p-6">
              <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Future product layer</div>
              <p className="mt-3 text-sm leading-7 text-zinc-400">
                This side of the project is meant to grow into richer review surfaces over time: desktop previews, benchmark modules, evidence panels, and backend-connected workflows when they are worth exposing publicly.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
