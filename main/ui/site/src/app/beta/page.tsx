import type { Metadata } from "next";
import Link from "next/link";
import { Clock3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";

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
              <h1 className="font-display text-4xl tracking-[-0.065em] text-white sm:text-6xl">
                Web beta coming soon.
              </h1>
              <p className="mt-6 text-lg leading-8 text-zinc-300">
                A browser-based review workflow is in development. The goal is a clean analyst-facing surface for ranked
                players, reasons, score traces, and evidence.
              </p>
              <div className="mt-8 rounded-[1.5rem] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-7 text-zinc-300">
                Public site first. Protected beta next.
              </div>
            </div>

            <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.14),rgba(9,11,18,0.98))] p-8 shadow-panel">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
                <Clock3 className="h-6 w-6 text-zinc-100" />
              </div>
              <h2 className="mt-6 font-display text-4xl tracking-[-0.05em] text-white">Secure web review is in development.</h2>
              <p className="mt-5 max-w-2xl text-base leading-8 text-zinc-300">
                The first release is meant to feel like a real review tool, not a rough preview. It will go live when the
                experience is ready to ship cleanly.
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
    </div>
  );
}
