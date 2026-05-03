import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Download, Gauge, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { clientRoadmap, githubUrl } from "@/lib/site-content";

const releaseUrl = `${githubUrl}/releases`;

export const metadata: Metadata = {
  title: "Desktop Beta",
  description: "Download the NullCS Windows desktop beta for local Counter-Strike demo review.",
};

export default function BetaPage() {
  return (
    <div className="relative overflow-hidden">
      <section className="border-b border-white/8 py-20 sm:py-28">
        <div className="container">
          <Chip>Desktop beta</Chip>
          <div className="mt-7 grid gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
            <div className="max-w-2xl">
              <h1 className="font-display text-4xl tracking-[-0.065em] text-white sm:text-6xl">
                Download the NullCS beta client.
              </h1>
              <p className="mt-6 text-lg leading-8 text-zinc-300">
                The first public beta is a Windows desktop app for local Counter-Strike demo review. It accepts .dem files,
                ranks players inside the match, and keeps the workflow on your PC.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href={releaseUrl} target="_blank" rel="noreferrer">
                  <Button size="lg">
                    <Download className="h-4 w-4" />
                    Download from GitHub Releases
                  </Button>
                </Link>
                <Link href="/#proof">
                  <Button size="lg" variant="secondary">
                    View benchmark proof
                    <ArrowUpRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
              <div className="mt-8 rounded-[1.5rem] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-7 text-zinc-300">
                This is a beta review tool, not an anti-cheat system or automated ban system. Review labels mean a player
                deserves closer inspection, especially across demo context and repeat matches.
              </div>
            </div>

            <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.14),rgba(9,11,18,0.98))] p-8 shadow-panel">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
                <ShieldCheck className="h-6 w-6 text-zinc-100" />
              </div>
              <h2 className="mt-6 font-display text-4xl tracking-[-0.05em] text-white">Beta client is live.</h2>
              <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300">
                Install the Windows release asset, open NullCS, and load a Counter-Strike .dem file. The app parses the
                match locally, builds behavioral features, runs the model pipeline, and presents a ranked review surface.
              </p>
              <ul className="mt-7 space-y-3 text-sm leading-7 text-zinc-300">
                {clientRoadmap.map((item) => (
                  <li key={item} className="flex gap-3 rounded-[1.2rem] border border-white/10 bg-white/[0.03] px-4 py-3">
                    <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-[#7ee0a1]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      </section>

      <section className="py-18 sm:py-24">
        <div className="container grid gap-5 lg:grid-cols-3">
          <article className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <Download className="h-5 w-5 text-zinc-200" />
            <h3 className="mt-5 font-display text-2xl tracking-[-0.04em] text-white">Install path</h3>
            <p className="mt-3 text-sm leading-7 text-zinc-400">
              Use the installer attached to the latest GitHub Release. Do not download builds from random mirrors.
            </p>
          </article>
          <article className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <Gauge className="h-5 w-5 text-zinc-200" />
            <h3 className="mt-5 font-display text-2xl tracking-[-0.04em] text-white">Baseline runtime</h3>
            <p className="mt-3 text-sm leading-7 text-zinc-400">
              On an i5-13400F, RTX 3060 Ti, and 32 GB DDR5 system, a 143.3 MiB demo completed in about 25.2 seconds.
              Larger demos and slower systems can take longer.
            </p>
          </article>
          <article className="rounded-[1.8rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <ShieldCheck className="h-5 w-5 text-zinc-200" />
            <h3 className="mt-5 font-display text-2xl tracking-[-0.04em] text-white">Review context</h3>
            <p className="mt-3 text-sm leading-7 text-zinc-400">
              A review tier is a triage signal. Strong play, edge cases, and single-demo uncertainty still need human
              inspection and supporting context.
            </p>
          </article>
        </div>
      </section>
    </div>
  );
}
