import Image from "next/image";
import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { capabilityBands } from "@/lib/site-content";

export function ProjectIntro() {
  return (
    <SectionShell
      id="what-it-is"
      eyebrow="What NullCS Is"
      title="A research stack for turning demos into reviewable behavioral signals."
      description="NullCS parses CS2 demos, derives encounter and player-level features, and studies whether review-worthy anomalies can be surfaced without overstating certainty."
    >
      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <Reveal>
          <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.03]">
            <div className="grid gap-0 lg:grid-cols-[1fr_0.72fr]">
              <div className="p-8">
                <p className="max-w-2xl text-lg leading-8 text-zinc-300">
                  The project studies whether suspicious benchmark behavior can be surfaced more reliably in real demos
                  without flattening the problem into one loud metric. Some cases are obvious. The harder cases are the
                  lobbies where timing, visibility, aim process, and strong legitimate play start to sit close together.
                </p>
                <div className="mt-8 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.35rem] border border-white/10 bg-[#0c1018] px-4 py-3">
                    <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Training scale</div>
                    <div className="mt-2 font-display text-2xl tracking-[-0.05em] text-white">894 matches</div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">Suspicious, normal legit, and pro stress-test slices in the current CS2 research stack.</p>
                  </div>
                  <div className="rounded-[1.35rem] border border-white/10 bg-[#0c1018] px-4 py-3">
                    <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">Encounter scale</div>
                    <div className="mt-2 font-display text-2xl tracking-[-0.05em] text-white">281,792 rows</div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">One match expands into many encounter windows and control-path measurements.</p>
                  </div>
                </div>
              </div>
              <div className="relative min-h-[280px] border-t border-white/8 lg:min-h-full lg:border-l lg:border-t-0">
                <Image
                  src="/assets/UIPopUp.PNG"
                  alt="NullCS research interface preview"
                  fill
                  className="object-cover object-center opacity-82"
                />
                <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0.18),rgba(7,9,14,0.92))]" />
                <div className="absolute inset-x-0 bottom-0 p-5">
                  <div className="text-[0.68rem] uppercase tracking-[0.22em] text-zinc-500">Why this matters</div>
                  <p className="mt-3 max-w-sm text-sm leading-6 text-zinc-300">
                    The difficult cases are the ones where the evidence has to stay readable even when suspicious benchmark
                    behavior and strong legitimate play start to overlap.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
        <div className="space-y-4">
          {capabilityBands.map((item, index) => (
            <Reveal key={item.title} delay={index * 0.06}>
              <HoverPanel>
                <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5">
                  <item.icon className="h-5 w-5 text-[#d97a4a]" />
                  <h3 className="mt-4 font-display text-xl tracking-[-0.04em] text-white">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">{item.body}</p>
                </div>
              </HoverPanel>
            </Reveal>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}
