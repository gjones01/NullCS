"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

type BetaPendingProps = {
  demoId: string;
};

export function BetaPending({ demoId }: BetaPendingProps) {
  const router = useRouter();
  const [checks, setChecks] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setChecks((value) => value + 1);
      router.refresh();
    }, 2000);

    return () => window.clearInterval(interval);
  }, [router]);

  return (
    <div className="rounded-[2rem] border border-white/10 bg-[#090b12] p-8 shadow-panel">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-zinc-100">
        <LoaderCircle className="h-5 w-5 animate-spin" />
      </div>
      <div className="mt-6 max-w-2xl">
        <div className="text-[0.72rem] uppercase tracking-[0.24em] text-zinc-500">Preparing review bundle</div>
        <h2 className="mt-3 font-display text-3xl tracking-[-0.05em] text-white">Inference finished. Waiting for the analyst bundle to land.</h2>
        <p className="mt-4 text-sm leading-7 text-zinc-400">
          The demo has already been processed, but the web surface did not see the exported review bundle on the first
          check. This page is retrying automatically instead of throwing a false 404.
        </p>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <div className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] px-4 py-4">
          <div className="text-[0.7rem] uppercase tracking-[0.2em] text-zinc-500">Demo ID</div>
          <div className="mt-2 break-all text-sm text-zinc-200">{demoId}</div>
        </div>
        <div className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] px-4 py-4">
          <div className="text-[0.7rem] uppercase tracking-[0.2em] text-zinc-500">Refresh cadence</div>
          <div className="mt-2 text-sm text-zinc-200">Every 2 seconds</div>
        </div>
        <div className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] px-4 py-4">
          <div className="text-[0.7rem] uppercase tracking-[0.2em] text-zinc-500">Checks</div>
          <div className="mt-2 text-sm text-zinc-200">{checks}</div>
        </div>
      </div>

      <div className="mt-6">
        <Button type="button" variant="secondary" onClick={() => router.refresh()}>
          <RefreshCcw className="h-4 w-4" />
          Check again now
        </Button>
      </div>
    </div>
  );
}
