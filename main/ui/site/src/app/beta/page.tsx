import type { Metadata } from "next";
import Link from "next/link";
import { Clock3, FlaskConical, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";

const betaRoadmap = [
  "Authenticated beta access instead of an open upload route",
  "Web review bundles with ranked players, reasons, and evidence panels",
  "Safer background job execution before any public inference release",
] as const;

export const metadata: Metadata = {
  title: "Beta Soon",
  robots: {
    index: false,
    follow: false,
  },
};

export default function BetaPage() {
  return (
    <div className="relative overflow-hidden">
      <section className="border-b border-white/8 py-20 sm:py-28">
        <div className="container">
          <Chip>Web beta</Chip>
          <div className="mt-7 grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="max-w-2xl">
              <h1 className="font-display text-5xl tracking-[-0.07em] text-white sm:text-6xl">
                Web beta coming soon.
              </h1>
              <p className="mt-6 text-lg leading-8 text-zinc-300">
                The public site is live first. The interactive review beta is being held back until the deployment model,
                security boundaries, and upload/inference flow are ready to expose without cutting corners.
              </p>
              <div className="mt-8 grid gap-3">
                <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-7 text-zinc-300">
                  The target is still a browser-based analyst surface for ranked players, reasons, score traces, and
                  evidence tables.
                </div>
                <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-7 text-zinc-300">
                  What is not shipping publicly yet is the live upload and inference path. That will come after the
                  execution model is hardened properly.
                </div>
              </div>
            </div>

            <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.14),rgba(9,11,18,0.98))] p-8 shadow-panel">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
                <Clock3 className="h-6 w-6 text-zinc-100" />
              </div>
              <h2 className="mt-6 font-display text-4xl tracking-[-0.05em] text-white">Secure web review is in development.</h2>
              <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300">
                The beta is being designed as a real review surface, not a thin upload gimmick. That means tightening
                auth, storage, job execution, and evidence handling before it goes live.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button size="lg" variant="secondary" disabled>
                  <Clock3 className="h-4 w-4" />
                  Beta unavailable during development
                </Button>
                <Link href="/about">
                  <Button size="lg">Read the project background</Button>
                </Link>
              </div>
            </section>
          </div>
        </div>
      </section>

      <section className="py-16 sm:py-20">
        <div className="container grid gap-6 lg:grid-cols-[0.7fr_1.3fr]">
          <div className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <div className="flex items-center gap-2 text-zinc-400">
              <FlaskConical className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Beta framing</span>
            </div>
            <h2 className="mt-4 font-display text-3xl tracking-[-0.05em] text-white">What the beta is meant to prove</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-zinc-400">
              <p>The web beta is meant to expose the actual NullCS review workflow in a browser: ranked players, risk display, confidence, reasons, score traces, and evidence tables.</p>
              <p>It is not meant to be a public file-upload toy. The release bar is a protected, analyst-facing workflow that does not expose the local inference stack carelessly.</p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-[#090b12] p-6 shadow-panel">
            <div className="flex items-center gap-2 text-zinc-400">
              <ShieldCheck className="h-4 w-4" />
              <span className="text-[0.72rem] uppercase tracking-[0.22em]">Planned release path</span>
            </div>
            <div className="mt-5 space-y-4">
              {betaRoadmap.map((item) => (
                <div key={item} className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] px-4 py-4 text-sm leading-7 text-zinc-300">
                  {item}
                </div>
              ))}
              <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-white/[0.02] px-4 py-4 text-sm leading-7 text-zinc-400">
                The public site stays online now. The beta comes later, behind the right deployment and security model.
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
