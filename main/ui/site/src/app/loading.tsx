export default function Loading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div
          className="h-12 w-12 animate-pulse border border-primary/40 bg-primary/5"
          aria-hidden="true"
        />
        <div className="text-[0.75rem] uppercase tracking-[0.28em] text-zinc-500">
          Loading NullCS
        </div>
      </div>
    </div>
  );
}
