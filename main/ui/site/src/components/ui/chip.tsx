import { cn } from "@/lib/utils";

export function Chip({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-white/12 bg-white/[0.03] px-3 py-1 text-[0.7rem] uppercase tracking-[0.22em] text-zinc-300",
        className
      )}
    >
      {children}
    </span>
  );
}
