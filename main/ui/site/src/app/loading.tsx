export default function Loading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-16 w-16 animate-pulse rounded-full border border-white/10 bg-[radial-gradient(circle,rgba(217,122,74,0.35),rgba(255,255,255,0.02))]" />
        <div className="text-[0.75rem] uppercase tracking-[0.28em] text-zinc-500">Loading NullCS</div>
      </div>
    </div>
  );
}
