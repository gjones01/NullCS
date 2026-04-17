import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Github } from "lucide-react";
import { ParallaxMedia } from "@/components/ui/parallax-media";
import { Reveal } from "@/components/ui/reveal";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { githubUrl, heroMetrics } from "@/lib/site-content";

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-white/8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(180,74,33,0.2),transparent_26%),linear-gradient(180deg,rgba(5,7,12,0.1),rgba(5,7,12,0.9))]" />
      <div className="absolute inset-0 bg-grid bg-[size:72px_72px] opacity-[0.08]" />
      <div className="container relative grid gap-14 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-end lg:py-28">
        <div className="max-w-2xl">
          <Reveal>
            <Chip>Machine Learning Research for CS2 Demo Review</Chip>
          </Reveal>
          <Reveal delay={0.06}>
            <h1 className="mt-7 max-w-4xl font-display text-4xl tracking-[-0.065em] text-white sm:text-6xl lg:text-7xl">
              NullCS studies suspicious behavior without turning the review process into a black box.
            </h1>
          </Reveal>
          <Reveal delay={0.12}>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-400 sm:text-xl">
              NullCS is a behavioral review project for Counter-Strike 2 demos. It ranks suspicious players from structured
              demo signals and returns evidence that can be reviewed, especially in the harder cases where subtle cheating
              and strong legitimate play start to look closer than they should.
            </p>
          </Reveal>
          <Reveal delay={0.18}>
            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <Link href="/about">
                <Button size="lg">Explore the project</Button>
              </Link>
              <Link href={githubUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary" size="lg">
                  <Github className="h-4 w-4" />
                  View GitHub
                </Button>
              </Link>
            </div>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-12 grid gap-4 border-t border-white/10 pt-8 sm:grid-cols-3">
              {heroMetrics.map((metric) => (
                <div key={metric.label}>
                  <div className="text-[0.72rem] uppercase tracking-[0.2em] text-zinc-500">{metric.label}</div>
                  <div className="mt-2 text-sm leading-6 text-zinc-200">{metric.value}</div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>

        <div className="relative">
          <div className="absolute -inset-3 rounded-[2rem] border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.05),rgba(255,255,255,0.01))]" />
          <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-[#090b12] shadow-panel">
            <div className="absolute inset-0 bg-[linear-gradient(130deg,rgba(189,76,35,0.22),transparent_45%,rgba(255,255,255,0.04))]" />
            <div className="absolute left-0 top-0 h-full w-px bg-white/10" />
            <div className="absolute right-[18%] top-0 h-full w-px bg-white/10" />
            <div className="relative aspect-[4/3] sm:aspect-[4/5]">
              <ParallaxMedia>
                <Image
                  src="/assets/hero-cs-bg.png"
                  alt="Atmospheric Counter-Strike themed scene"
                  fill
                  priority
                  className="object-cover object-center opacity-55"
                />
              </ParallaxMedia>
              <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,9,14,0.08),rgba(7,9,14,0.7))]" />
              <div className="absolute bottom-0 left-0 right-0 p-6 sm:p-8">
                <div className="rounded-[1.75rem] border border-white/10 bg-black/35 p-5 backdrop-blur-[2px] transition-transform duration-500 hover:-translate-y-1">
                  <div className="text-[0.7rem] uppercase tracking-[0.24em] text-zinc-400">Current direction</div>
                  <div className="mt-3 font-display text-2xl tracking-[-0.05em] text-white">Serious review for the loud cases and the subtle ones</div>
                  <p className="mt-3 max-w-md text-sm leading-6 text-zinc-300">
                    Some demo metrics do scream that something is wrong. The harder problem is the quieter behavior that only starts to separate once timing, context, and process are modeled together.
                  </p>
                  <Link href="/about" className="mt-5 inline-flex items-center gap-2 text-sm text-white transition-opacity hover:opacity-80">
                    Read the project background
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
