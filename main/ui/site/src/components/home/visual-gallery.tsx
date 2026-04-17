import Image from "next/image";
import { SectionShell } from "@/components/layout/section-shell";
import { screenshotSlots } from "@/lib/site-content";

export function VisualGallery() {
  return (
    <SectionShell
      eyebrow="Visual Surfaces"
      title="Made to accept screenshots, charts, and future product captures."
      description="These blocks are already shaped for the assets you want to add later. Swap in benchmark plots, desktop client views, or research screenshots without redesigning the layout."
    >
      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        {screenshotSlots.map((slot) => (
          <article key={slot.title} className="overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
            <div className="relative aspect-[16/10]">
              <Image src={slot.image} alt={slot.title} fill className="object-cover object-center opacity-75" />
              <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0),rgba(7,9,14,0.86))]" />
            </div>
            <div className="p-6 sm:p-7">
              <div className="text-[0.7rem] uppercase tracking-[0.24em] text-zinc-500">{slot.eyebrow}</div>
              <h3 className="mt-3 font-display text-2xl tracking-[-0.04em] text-white">{slot.title}</h3>
              <p className="mt-3 text-sm leading-7 text-zinc-400">{slot.body}</p>
            </div>
          </article>
        ))}
      </div>
    </SectionShell>
  );
}
