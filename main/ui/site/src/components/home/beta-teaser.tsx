import Link from "next/link";
import { Clock3, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function BetaTeaser() {
  return (
    <section className="border-y border-white/8 py-18 sm:py-24">
      <div className="container">
        <div className="grid gap-8 xl:grid-cols-[1fr_0.8fr] xl:items-start">
          <div className="rounded-[2.2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(64,29,18,0.34),rgba(9,11,18,0.92))] p-7 shadow-panel sm:p-9">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] px-4 py-2 text-[0.72rem] uppercase tracking-[0.22em] text-zinc-200">
              <Sparkles className="h-3.5 w-3.5" />
              Web beta
            </div>
            <h2 className="mt-6 max-w-3xl font-display text-4xl tracking-[-0.06em] text-white sm:text-5xl">
              Web beta in development.
            </h2>
            <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300 sm:text-lg">
              The goal is a browser-based review surface for ranked players, reasons, score traces, and evidence. The
              public site comes first. The beta follows when the experience is ready to ship cleanly.
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
              The web beta is being built as a real analyst-facing review flow, not as a half-shipped upload page.
            </div>
          </div>

          <div className="grid gap-4">
            <article className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
              <h3 className="font-display text-2xl tracking-[-0.04em] text-white">What it will include</h3>
              <p className="mt-3 text-sm leading-7 text-zinc-400">
                Demo intake, ranked players, review-facing reasons, score context, and evidence panels shaped for real analysis.
              </p>
            </article>
            <article className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
              <h3 className="font-display text-2xl tracking-[-0.04em] text-white">Current status</h3>
              <p className="mt-3 text-sm leading-7 text-zinc-400">
                In development. The public site is live now; the protected review workflow comes next.
              </p>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
