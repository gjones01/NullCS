import Image from "next/image";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { SectionShell } from "@/components/layout/section-shell";
import { benchmarkStats, proofCards, proofExample } from "@/lib/site-content";

export function ProofGrid() {
  return (
    <SectionShell
      id="proof"
      eyebrow="Proof and Benchmarks"
      title="Benchmark views that show where the current system is actually separating."
      description="These plots are there to show how suspicious slices behave against legit and pro baselines, not to decorate the page."
    >
      <Reveal>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {benchmarkStats.map((stat) => (
            <div key={stat.label} className="rounded-[1.6rem] border border-white/10 bg-white/[0.03] p-5">
              <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">{stat.label}</div>
              <div className="mt-3 font-display text-4xl tracking-[-0.05em] text-white">{stat.value}</div>
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.04}>
        <article className="mt-10 overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
          <div className="grid gap-0 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="p-7 sm:p-8">
              <div className="text-[0.7rem] uppercase tracking-[0.24em] text-zinc-500">{proofExample.eyebrow}</div>
              <h3 className="mt-4 max-w-3xl font-display text-3xl tracking-[-0.05em] text-white sm:text-4xl">
                {proofExample.title}
              </h3>
              <p className="mt-5 max-w-3xl text-sm leading-7 text-zinc-300">{proofExample.body}</p>
              <div className="mt-6 rounded-[1.35rem] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-7 text-zinc-300">
                {proofExample.caption}
              </div>
            </div>
            <div className="relative min-h-[340px] border-t border-white/8 bg-[linear-gradient(180deg,#0b1018,#080b12)] lg:min-h-full lg:border-l lg:border-t-0">
              <div className="absolute inset-0 p-5 sm:p-6">
                <Image
                  src={proofExample.image}
                  alt={proofExample.title}
                  fill
                  className="object-contain object-center p-4"
                />
              </div>
            </div>
          </div>
        </article>
      </Reveal>

      <div className="mt-10 grid gap-5 lg:grid-cols-2">
        {proofCards.map((card, index) => (
          <Reveal key={card.title} delay={index * 0.06}>
            <HoverPanel className="h-full">
              <article className="overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
                <div className="relative aspect-[16/11] overflow-hidden border-b border-white/8 bg-[linear-gradient(180deg,#0b1018,#080b12)]">
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.03),transparent_55%)]" />
                  <div className="absolute inset-0 p-5 sm:p-6">
                    <Image
                      src={card.image}
                      alt={card.title}
                      fill
                      className="object-contain object-center p-4 transition-transform duration-700 group-hover:scale-[1.015]"
                    />
                  </div>
                  <div className="absolute inset-x-0 bottom-0 h-20 bg-[linear-gradient(180deg,rgba(7,9,14,0),rgba(7,9,14,0.94))]" />
                </div>
                <div className="p-6">
                  <div className="text-[0.7rem] uppercase tracking-[0.24em] text-zinc-500">{card.eyebrow}</div>
                  <h3 className="mt-3 font-display text-2xl tracking-[-0.04em] text-white">{card.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-zinc-400">{card.body}</p>
                </div>
              </article>
            </HoverPanel>
          </Reveal>
        ))}
      </div>
    </SectionShell>
  );
}
