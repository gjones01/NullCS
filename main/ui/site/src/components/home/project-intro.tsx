import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { capabilityBands } from "@/lib/site-content";

export function ProjectIntro() {
  return (
    <SectionShell
      id="what-it-is"
      eyebrow="What NullCS Is"
      title="A behavioral review project, not a flashy demo site."
      description="NullCS is positioned as technical research software: measured, visual, and extensible. The design is intentionally built to present the work clearly while leaving room for future product evolution."
    >
      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <Reveal>
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-8">
          <p className="max-w-2xl text-lg leading-8 text-zinc-300">
            The project analyzes structured Counter-Strike 2 demo data to surface behavior that deserves review. The current public stack uses 449 player-level engineered features and deeper encounter-level timing channels to study how suspicious patterns separate from strong legitimate play.
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
