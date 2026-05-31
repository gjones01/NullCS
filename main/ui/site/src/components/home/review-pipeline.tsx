import Image from "next/image";
import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { actualFindings, pipelineSteps } from "@/lib/site-content";

export function ReviewPipeline() {
  return (
    <SectionShell
      id="pipeline"
      eyebrow="Review Pipeline"
      title="From demo file to review queue."
      description="NullCS turns CS2 demos into structured behavior evidence, then ranks the players and moments that deserve closer inspection."
    >
      <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <Reveal>
          <div className="relative min-h-[420px] overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#090b12] shadow-panel">
            <Image
              src="/assets/UIPopUp.PNG"
              alt="NullCS review interface preview"
              fill
              className="object-cover object-center opacity-75"
            />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0.18),rgba(7,9,14,0.94))]" />
            <div className="absolute inset-x-0 bottom-0 p-6">
              <div className="text-[0.7rem] uppercase tracking-[0.22em] text-zinc-500">Output</div>
              <h3 className="mt-3 max-w-md font-display text-3xl tracking-[-0.05em] text-white">
                Ranked signals, evidence rows, and failure-aware scores.
              </h3>
              <p className="mt-3 max-w-lg text-sm leading-6 text-zinc-300">
                A high score means inspect this player first. It does not mean the match is settled.
              </p>
            </div>
          </div>
        </Reveal>

        <div className="grid gap-4">
          {pipelineSteps.map((step, index) => (
            <Reveal key={step.title} delay={index * 0.06}>
              <HoverPanel>
                <article className="grid gap-5 rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5 sm:grid-cols-[auto_1fr]">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-[#11141d]">
                    <step.icon className="h-5 w-5 text-[#d97a4a]" />
                  </div>
                  <div>
                    <div className="text-[0.7rem] uppercase tracking-[0.22em] text-zinc-500">{step.label}</div>
                    <h3 className="mt-2 font-display text-2xl tracking-[-0.04em] text-white">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">{step.body}</p>
                  </div>
                </article>
              </HoverPanel>
            </Reveal>
          ))}
        </div>
      </div>

      <Reveal delay={0.14}>
        <div className="mt-10">
          <div className="max-w-3xl">
            <div className="text-[0.7rem] uppercase tracking-[0.22em] text-zinc-500">What It Actually Finds</div>
            <h3 className="mt-3 font-display text-3xl tracking-[-0.05em] text-white">Concrete signals from the demo telemetry.</h3>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {actualFindings.map((finding) => (
              <div key={finding.title} className="rounded-[1.35rem] border border-white/10 bg-[#0a0d14] p-5">
                <div className="text-[0.7rem] uppercase tracking-[0.22em] text-zinc-500">{finding.title}</div>
                <p className="mt-3 text-sm leading-6 text-zinc-300">{finding.body}</p>
              </div>
            ))}
          </div>
          <p className="mt-5 max-w-3xl text-sm leading-6 text-zinc-500">
            These are review signals. They point to behavior worth inspecting; they do not identify a cheat type by themselves.
          </p>
        </div>
      </Reveal>
    </SectionShell>
  );
}
