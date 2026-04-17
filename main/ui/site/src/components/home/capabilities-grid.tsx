import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { featureCards } from "@/lib/site-content";

export function CapabilitiesGrid() {
  return (
    <SectionShell
      id="capabilities"
      eyebrow="Capabilities"
      title="Core ideas presented like a product, grounded like research."
      description="The first public version of the site highlights what the system actually does without pretending the project is already a finished SaaS platform."
    >
      <div className="grid gap-5 md:grid-cols-2">
        {featureCards.map((card, index) => (
          <Reveal key={card.title} delay={index * 0.05}>
            <HoverPanel>
              <article className="group rounded-[1.9rem] border border-white/10 bg-white/[0.03] p-7 transition-colors hover:border-white/20 hover:bg-white/[0.045]">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-[#11141d] transition-transform duration-500 group-hover:rotate-3">
                  <card.icon className="h-5 w-5 text-[#d97a4a]" />
                </div>
                <h3 className="mt-6 font-display text-2xl tracking-[-0.05em] text-white">{card.title}</h3>
                <p className="mt-3 max-w-lg text-sm leading-7 text-zinc-400">{card.body}</p>
              </article>
            </HoverPanel>
          </Reveal>
        ))}
      </div>
    </SectionShell>
  );
}
