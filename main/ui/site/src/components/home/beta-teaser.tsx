import Link from "next/link";
import { Clock3, FlaskConical, Radar, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const betaHighlights = [
  {
    title: "Protected beta release",
    body: "The beta is being held until the upload, job execution, and review-bundle flow are exposed behind the right security model instead of a rushed public endpoint.",
    icon: FlaskConical,
  },
  {
    title: "Latest encounter NN",
    body: "The beta uses the expanded temporal encounter model with the newer control-path channels, then folds those outputs into the current player-level ranking stack.",
    icon: Radar,
  },
  {
    title: "Analyst-facing review surface",
    body: "Ranked players, risk bands, reasons, score traces, and evidence tables are shown in one place so the web flow behaves like a real operator console.",
    icon: ShieldCheck,
  },
] as const;

export function BetaTeaser() {
  return (
    <section className="border-y border-white/8 py-18 sm:py-24">
      <div className="container">
        <div className="grid gap-8 xl:grid-cols-[0.95fr_1.05fr] xl:items-start">
          <div className="rounded-[2.2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(64,29,18,0.34),rgba(9,11,18,0.92))] p-7 shadow-panel sm:p-9">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] px-4 py-2 text-[0.72rem] uppercase tracking-[0.22em] text-zinc-200">
              <Sparkles className="h-3.5 w-3.5" />
              Web beta
            </div>
            <h2 className="mt-6 max-w-3xl font-display text-4xl tracking-[-0.06em] text-white sm:text-5xl">
              The full NullCS review stack can now run through the site.
            </h2>
            <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300 sm:text-lg">
              This beta turns the project website into a real review surface. A local demo path can be sent through the
              live Python pipeline, scored with the current encounter plus XGBoost stack, and returned as a ranked player
              bundle with reasons, confidence, and evidence.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href="/beta">
                <Button size="lg">
                  Beta soon
                  <Clock3 className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/about">
                <Button variant="secondary" size="lg">
                  Read the methodology
                </Button>
              </Link>
            </div>
            <div className="mt-8 rounded-[1.6rem] border border-white/10 bg-black/20 px-5 py-4 text-sm leading-7 text-zinc-300">
              Local-only right now. The Next server and the Python inference pipeline still need to live on the same
              machine, but the user-facing review flow is now web-native instead of desktop-only.
            </div>
          </div>

          <div className="grid gap-4">
            {betaHighlights.map((item) => {
              const Icon = item.icon;
              return (
                <article
                  key={item.title}
                  className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel transition-transform duration-300 hover:-translate-y-1"
                >
                  <div className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-zinc-200">
                    <Icon className="h-4.5 w-4.5" />
                  </div>
                  <h3 className="mt-5 font-display text-2xl tracking-[-0.04em] text-white">{item.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-zinc-400">{item.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
