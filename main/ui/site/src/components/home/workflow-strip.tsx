import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";
import { workflowSteps } from "@/lib/site-content";

export function WorkflowStrip() {
  return (
    <SectionShell
      id="workflow"
      eyebrow="How It Works"
      title="Parse, score, explain."
      description="Raw demos are turned into structured events, behavior signals, and ranked review output."
    >
      <div className="grid gap-4 lg:grid-cols-3">
        {workflowSteps.map((item, index) => (
          <Reveal key={item.step} delay={index * 0.06}>
            <HoverPanel>
              <div className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#0a0d14] p-6">
                <div className="absolute left-0 top-0 h-1 w-full bg-[linear-gradient(90deg,rgba(217,122,74,0.9),rgba(217,122,74,0))] animate-pulse-line" />
                <div className="text-[0.72rem] uppercase tracking-[0.22em] text-zinc-500">{item.step}</div>
                <div className="mt-6 flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03]">
                  <item.icon className="h-4 w-4 text-zinc-200" />
                </div>
                <h3 className="mt-6 font-display text-2xl tracking-[-0.04em] text-white">{item.title}</h3>
                <p className="mt-3 text-sm leading-7 text-zinc-400">{item.body}</p>
              </div>
            </HoverPanel>
          </Reveal>
        ))}
      </div>
    </SectionShell>
  );
}
