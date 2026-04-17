import Link from "next/link";
import { AppWindow, ArrowUpRight } from "lucide-react";
import { SectionShell } from "@/components/layout/section-shell";
import { Button } from "@/components/ui/button";

export function DesktopSoon() {
  return (
    <SectionShell
      eyebrow="Desktop Application"
      title="Local review application in development."
      description="The public site is live first. The desktop client is still being built as the local review workflow for deeper evidence inspection."
    >
      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(217,122,74,0.12),rgba(9,11,18,0.95))] p-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06]">
            <AppWindow className="h-6 w-6 text-[#f0e7dc]" />
          </div>
          <h3 className="mt-6 font-display text-3xl tracking-[-0.05em] text-white">Desktop client coming soon</h3>
          <p className="mt-4 max-w-xl text-sm leading-7 text-zinc-300">
            Download support is not part of this first public release. The desktop client remains the planned local workflow for deeper review and evidence inspection.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 text-sm text-zinc-300">
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2">Local review workflow</span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2">Evidence inspection</span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2">Future download delivery</span>
          </div>
        </div>
        <div className="rounded-[2rem] border border-white/10 bg-[#0a0d14] p-8">
          <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Planned release path</div>
          <ul className="mt-5 space-y-4 text-sm leading-7 text-zinc-400">
            <li>Desktop review surface for local evidence browsing</li>
            <li>Deeper per-demo investigation flows</li>
            <li>Future distribution path once the client is ready</li>
          </ul>
          <div className="mt-8">
            <Link href="/client">
              <Button variant="secondary" size="lg">
                Visit the client page
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </SectionShell>
  );
}
