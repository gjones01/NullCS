import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Github } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { aboutPrinciples, benchmarkStats, githubUrl } from "@/lib/site-content";

const sections = [
  {
    title: "What NullCS analyzes",
    body: "NullCS works from structured Counter-Strike 2 demo data. The current public stack builds 449 player-level engineered features and deeper encounter-level timing and process channels to study how suspicious behavior actually unfolds.",
  },
  {
    title: "Why behavioral review matters",
    body: "Some demo metrics can make blatant abuse look obvious, but that is not always enough to settle the case. The harder problem is when strong legitimate play and lower-visibility cheating begin to overlap.",
  },
  {
    title: "What the current models are for",
    body: "The models are there to rank, organize, and explain suspicious behavior. They are useful when they surface the right players near the top of a lobby while staying quieter on strong legitimate and pro-level slices.",
  },
  {
    title: "What NullCS does not claim",
    body: "NullCS is a review-support system, not a kernel anticheat and not a universal detector. The current work is serious progress, but the research is still ongoing in a difficult and dynamic environment.",
  },
] as const;

const currentFocus = [
  "Blatant abuse can be loud in the metrics, but that is only one part of the review problem.",
  "The harder cases are subtle aim assist, recoil assist, and information abuse that try to stay close to strong legitimate play.",
  "NullCS is still under active research. The current state reflects real progress, not a claim that the problem has been solved.",
] as const;

export default function AboutPage() {
  return (
    <div className="relative overflow-hidden">
      <section className="relative border-b border-white/8">
        <div className="absolute inset-0">
          <Image
            src="/assets/aboutpagebg.png"
            alt="About page background"
            fill
            priority
            className="object-cover object-center opacity-20"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(5,7,12,0.45),rgba(5,7,12,0.94))]" />
        </div>
        <div className="container relative py-20 sm:py-28">
          <Chip>About NullCS</Chip>
          <div className="mt-7 max-w-4xl">
            <h1 className="font-display text-4xl tracking-[-0.065em] text-white sm:text-6xl">
              Behavioral demo analysis for the cases that are easy to miss and hard to explain.
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-zinc-300">
              NullCS studies whether suspicious behavior in Counter-Strike 2 demos can be surfaced in a way that stays
              measurable, reviewable, and honest about uncertainty. The goal is not to act like the problem is solved. The
              goal is to make serious progress on a difficult review task without hiding behind black-box language.
            </p>
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
              The first three numbers are not cheat probabilities. They summarize how loud the strongest player signal looks
              inside each benchmark slice. Median top-ranked signal means: for each demo, take the highest-ranked player in
              the lobby, then look at the middle value across that group of demos.
            </p>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              So a suspicious median of <span className="text-zinc-200">0.748</span> versus{" "}
              <span className="text-zinc-200">0.0073</span> on held-out normal legit demos means the suspicious slice is
              surfacing much more strongly, while the legit slice stays almost pinned near zero. The pro value staying at{" "}
              <span className="text-zinc-200">0.0073</span> matters for the same reason: strong legitimate players are not
              being inflated just because they are skilled.
            </p>
          </article>
          <article className="rounded-[1.7rem] border border-white/10 bg-[#0a0d14] p-6">
            <h2 className="font-display text-2xl tracking-[-0.05em] text-white">Why that is significant</h2>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              For a review system like NullCS, the shape is more important than the raw magnitude. You want suspicious
              benchmark demos to be visibly louder, while normal legit and pro stress-test demos stay quiet. If all three
              slices were high, the system would be noisy. If all three were low, it would not be useful.
            </p>
            <p className="mt-4 text-sm leading-7 text-zinc-400">
              The <span className="text-zinc-200">0.90</span> top-3 retrieval number answers a different question: how often
              does a labeled suspicious player appear somewhere in the top three ranked players for a suspicious benchmark
              demo? That matters because NullCS is framed as triage and review support. The goal is to reliably surface the
              right players near the top of the lobby, not to claim that one score is a final verdict.
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
              NullCS is being built by Gerry Jones, Jr., who holds a B.S. in Applied Mathematics and is currently pursuing a
              master's degree in Data Science. The project started after returning to Counter-Strike in April 2025 and
              repeatedly running into blatant abuse, including aimbotting, triggerbotting, and spinbotting, with the obvious
              question of why some of those cases appeared to move through the ecosystem without meaningful response.
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              That turned into a research problem rather than a complaint. The goal was not to build an anticheat or market a
              magical detector. The goal was to investigate whether suspicious behavior in demos could be surfaced more
              systematically, including both the obvious cases and the harder ones: aim assist, recoil assist, and information
              abuse that often try to stay just subtle enough to blend into strong legitimate play.
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              Building that required repeated iteration: sourcing demo data, manually pulling and labeling SteamIDs for
              training, testing different feature and modeling strategies, and spending time inside cheat communities to better
              understand how players discuss avoiding bans and staying below the threshold of current systems such as VAC.
              There is still substantial work ahead, but the current state of NullCS already reflects meaningful progress.
            </p>
          </article>
          <article className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.10),rgba(9,11,18,0.98))] p-8">
            <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Current research posture</div>
            <h2 className="mt-4 font-display text-3xl tracking-[-0.05em] text-white">Serious progress, ongoing work.</h2>
            <div className="mt-6 space-y-4">
              {currentFocus.map((note) => (
                <p key={note} className="border-l border-white/10 pl-4 text-sm leading-7 text-zinc-300">
                  {note}
                </p>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="py-20 sm:py-28">
        <div className="container grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.12),rgba(9,11,18,0.98))] p-8">
            <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Project direction</div>
            <h2 className="mt-4 font-display text-4xl tracking-[-0.06em] text-white">Public site now, deeper review tooling next.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-300">
              The current release is meant to communicate the benchmark story, the modeling direction, and the technical
              depth behind NullCS. The next milestone is not a bigger claim. It is a better review surface.
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
              <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Next milestone</div>
              <p className="mt-3 text-sm leading-7 text-zinc-400">
                The next step is a stronger review surface: clearer evidence panels, richer benchmark modules, and better
                operator-facing workflows once they are ready to ship cleanly.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
