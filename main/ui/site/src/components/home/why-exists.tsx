import { SectionShell } from "@/components/layout/section-shell";
import { HoverPanel } from "@/components/ui/hover-panel";
import { Reveal } from "@/components/ui/reveal";

const reasons = [
  {
    title: "Some metrics can be loud",
    body: "Rage behavior, impossible-looking snaps, or repeated obvious abuse can light up a demo quickly. Those are real signals, but they are not the whole problem.",
  },
  {
    title: "Strong legit can still look strange",
    body: "High-ELO and pro players produce uncomfortable rounds too. A useful system has to stay quieter there than a noisy model would, or the output stops being actionable.",
  },
  {
    title: "Subtle cases are the real challenge",
    body: "Some irregular patterns can stay close enough to normal play to avoid obvious signatures. That is the gap NullCS is trying to study without overclaiming.",
  },
] as const;

export function WhyExists() {
  return (
    <SectionShell
      eyebrow="Why It Exists"
      title="Built to separate the loud cases from the hard ones."
      description="Obvious abuse is not the full problem. The harder review task is telling strong legitimate play apart from lower-visibility irregular behavior without pretending one score can settle it."
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
