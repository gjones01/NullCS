"use client";

import { useRef, useState } from "react";
import { LoaderCircle, Play, Radar, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function BetaLaunchForm() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function assignFile(nextFile: File | null) {
    if (!nextFile) {
      setFile(null);
      return;
    }
    if (!nextFile.name.toLowerCase().endsWith(".dem")) {
      setError("Upload must be a .dem file.");
      setFile(null);
      return;
    }
    setError(null);
    setFile(nextFile);
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose a .dem file first.");
      return;
    }
    setIsRunning(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/api/beta/run", {
        method: "POST",
        body: formData,
      });
      const payload = (await response.json()) as { ok: boolean; demoId?: string; error?: string };
      if (!response.ok || !payload.ok || !payload.demoId) {
        throw new Error(payload.error || "Inference run failed.");
      }
      window.location.assign(`/beta/${payload.demoId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Inference run failed.");
      setIsRunning(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-[2rem] border border-white/10 bg-[#090b12] p-7 shadow-panel">
      <div className="flex items-center gap-3">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-zinc-200">
          <Radar className="h-5 w-5" />
        </span>
        <div>
          <div className="font-display text-2xl tracking-[-0.04em] text-white">Run Local Inference</div>
          <p className="mt-1 text-sm text-zinc-400">
            Drop a `.dem` file here or click to browse. The beta runs the live Python inference stack on this machine and renders a review bundle in the browser.
          </p>
        </div>
      </div>

      <div className="mt-6">
        <input
          ref={inputRef}
          type="file"
          accept=".dem"
          className="hidden"
          onChange={(event) => assignFile(event.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            assignFile(event.dataTransfer.files?.[0] ?? null);
          }}
          className={cn(
            "group flex min-h-56 w-full flex-col items-center justify-center rounded-[1.8rem] border border-dashed px-6 py-10 text-center transition-colors",
            isDragging
              ? "border-white/30 bg-white/[0.07]"
              : "border-white/12 bg-white/[0.03] hover:bg-white/[0.05]"
          )}
        >
          <span className="inline-flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-zinc-100">
            <Upload className="h-5 w-5" />
          </span>
          <div className="mt-5 font-display text-3xl tracking-[-0.05em] text-white">
            Drag and drop a demo file
          </div>
          <p className="mt-3 max-w-xl text-sm leading-7 text-zinc-400">
            Or click this panel to open File Explorer. NullCS will upload the file locally, run inference, and open the
            review bundle automatically.
          </p>
          <div className="mt-6 rounded-full border border-white/10 bg-black/20 px-4 py-2 text-xs uppercase tracking-[0.22em] text-zinc-300">
            {file ? file.name : "No file selected"}
          </div>
        </button>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="submit" size="lg" disabled={isRunning || !file}>
          {isRunning ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {isRunning ? "Running inference..." : "Run beta review"}
        </Button>
        <p className="text-sm text-zinc-500">
          Local-only beta. This path assumes the site server and the Python inference stack are running on the same machine.
        </p>
      </div>

      {error ? (
        <div className="mt-5 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div>
      ) : null}
    </form>
  );
}
