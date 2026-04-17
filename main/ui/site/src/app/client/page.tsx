import Link from "next/link";
import { ArrowUpRight, Download, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { clientRoadmap } from "@/lib/site-content";

export default function ClientPage() {
  return (
    <div className="container py-20 sm:py-28">
      <Chip>Desktop Client</Chip>
      <div className="mt-8 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.14),rgba(9,11,18,0.98))] p-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
            <Download className="h-6 w-6 text-zinc-100" />
          </div>
          <h1 className="mt-6 font-display text-5xl tracking-[-0.06em] text-white">Downloadable client in development.</h1>
          <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300">
            NullCS is being released publicly in stages. The research site is live now, while the desktop client is being built as the local review surface for demo intake, ranked player inspection, and evidence-first match analysis.
          </p>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-400">
            The goal is a focused local tool for loading demos, surfacing suspicious players inside a match, and drilling into the evidence without turning the project into a noisy pseudo-SaaS landing page.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button size="lg" variant="secondary" disabled>
              <Wrench className="h-4 w-4" />
              Download unavailable during development
            </Button>
            <Link href="/about">
              <Button size="lg">
                Read the project background
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </section>

        <section className="rounded-[2rem] border border-white/10 bg-[#0a0d14] p-8">
          <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Planned direction</div>
          <ul className="mt-6 space-y-4 text-sm leading-7 text-zinc-300">
            {clientRoadmap.map((item) => (
              <li key={item} className="rounded-[1.2rem] border border-white/10 bg-white/[0.03] px-4 py-4">
                {item}
              </li>
            ))}
          </ul>
          <div className="mt-8 rounded-[1.4rem] border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm leading-7 text-zinc-400">
            The desktop release will come after the review workflow is ready. Until then, this page is here to state the direction clearly instead of pretending there is a download that already exists.
          </div>
        </section>
      </div>
    </div>
  );
}
