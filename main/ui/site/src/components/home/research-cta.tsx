import Link from "next/link";
import { ArrowUpRight, Github } from "lucide-react";
import { SectionShell } from "@/components/layout/section-shell";
import { Reveal } from "@/components/ui/reveal";
import { Button } from "@/components/ui/button";
import { credibilityNotes, githubUrl } from "@/lib/site-content";

export function ResearchCta() {
  return (
    <SectionShell
      eyebrow="Technical Credibility"
      title="Repository, benchmarks, and ongoing work."
      description="NullCS is public as a real technical project now. The repository and benchmark pages are the best entry points into the current state of the work."
    >
      <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <Reveal>
          <div className="rounded-[1.9rem] border border-white/10 bg-[#0a0d14] p-7">
          <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Repository</div>
          <h3 className="mt-4 font-display text-3xl tracking-[-0.05em] text-white">Explore the GitHub repository</h3>
          <p className="mt-4 text-sm leading-7 text-zinc-400">
            The project is still evolving. Use the repo to inspect the current pipeline, benchmark artifacts, and model work as it continues to improve.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href={githubUrl} target="_blank" rel="noreferrer">
              <Button size="lg">
                <Github className="h-4 w-4" />
                Open GitHub
              </Button>
            </Link>
            <Link href="/about">
              <Button size="lg" variant="secondary">
                Read the background
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
          </div>
        </Reveal>
        <div className="grid gap-4">
          {credibilityNotes.map((note, index) => (
            <Reveal key={note} delay={index * 0.05}>
              <div className="flex items-start gap-4 rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 text-xs text-zinc-300">
                  {index + 1}
                </div>
                <p className="text-sm leading-7 text-zinc-300">{note}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}
