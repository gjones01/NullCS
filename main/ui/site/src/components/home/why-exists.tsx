import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";

const reasons = [
  {
    title: "Strong legitimate play is the real pressure test",
    body: "High-ELO and pro players can produce strange but legitimate rounds. A useful system has to stay quiet there more often than a noisy model would.",
  },
  {
    title: "The hard cases are subtle",
    body: "Blatant rage behavior is usually easier to surface. The tougher review problem is lower-visibility aim assist, recoil assist, and information advantage that sits closer to normal play.",
  },
  {
    title: "NullCS does not claim universal detection",
    body: "The project is built as a review and analysis system. It does not claim to detect every cheat type, and it does not present its outputs as proof by themselves.",
  },
] as const;

export function WhyExists() {
  return (
    <SectionShell
      eyebrow="Why It Exists"
      title="Built to make suspicious behavior review more disciplined."
      description="The goal is not instant judgment. The goal is better triage, clearer evidence, and a path toward serious tooling instead of vague suspicion."
    >
      <div className="grid gap-5 md:grid-cols-3">
        {reasons.map((reason, index) => (
          <Reveal key={reason.title} delay={index * 0.06}>
            <HoverPanel>
              <article className="rounded-[1.75rem] border border-white/10 bg-[#0a0d14] p-6">
                <h3 className="font-display text-2xl tracking-[-0.04em] text-white">{reason.title}</h3>
                <p className="mt-4 text-sm leading-7 text-zinc-400">{reason.body}</p>
              </article>
            </HoverPanel>
          </Reveal>
        ))}
      </div>
    </SectionShell>
  );
}
