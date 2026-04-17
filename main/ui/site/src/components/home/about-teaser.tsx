import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { SectionShell } from "@/components/layout/section-shell";
import { Button } from "@/components/ui/button";

export function AboutTeaser() {
  return (
    <SectionShell
      eyebrow="Project Background"
      title="The About page carries the project background without turning it into filler."
      description="It explains the founder background, the current benchmark posture, and why NullCS stays cautious about what it claims."
    >
      <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12]">
          <div className="relative aspect-[4/3]">
            <Image src="/assets/aboutpagebg.png" alt="NullCS about page atmosphere" fill className="object-cover object-center opacity-70" />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0.1),rgba(7,9,14,0.82))]" />
          </div>
        </div>
        <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-8">
          <p className="text-lg leading-8 text-zinc-300">
            NullCS is built around a simple question: can suspicious behavior in a demo be surfaced in a way that stays measurable, conservative, and useful for real review?
          </p>
          <p className="mt-5 text-sm leading-7 text-zinc-400">
            The About page expands on the benchmark numbers, Gerry Jones, Jr.'s background, and why the hardest review cases are the ones that matter most.
          </p>
          <div className="mt-8">
            <Link href="/about">
              <Button size="lg">
                Read the About page
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </SectionShell>
  );
}
