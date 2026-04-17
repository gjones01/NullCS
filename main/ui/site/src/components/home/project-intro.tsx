import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { capabilityBands } from "@/lib/site-content";

export function ProjectIntro() {
  return (
    <SectionShell
      id="what-it-is"
      eyebrow="What NullCS Is"
      title="Structured demo review built for the hard cases."
      description="NullCS analyzes CS2 demos, builds behavior signals, and returns ranked review output that can still be explained under scrutiny."
    >
      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <Reveal>
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-8">
          <p className="max-w-2xl text-lg leading-8 text-zinc-300">
            The project studies whether suspicious behavior can be surfaced more reliably in real demos without flattening the problem into a single loud metric. Some cases are obvious. The harder ones are the lobbies where subtle assistance, strange timing, and strong legitimate play start to sit uncomfortably close together.
          </p>
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
