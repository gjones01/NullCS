import { cn } from "@/lib/utils";

type SectionShellProps = {
  id?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
};

export function SectionShell({
  id,
  eyebrow,
  title,
  description,
  className,
  children,
}: SectionShellProps) {
  return (
    <section id={id} className={cn("relative py-20 sm:py-28", className)}>
      <div className="container">
        <div className="max-w-3xl">
          {eyebrow ? (
            <div className="mb-5 text-[0.72rem] uppercase tracking-[0.28em] text-zinc-500">{eyebrow}</div>
          ) : null}
          <h2 className="font-display text-3xl tracking-[-0.04em] text-white sm:text-5xl">{title}</h2>
          {description ? <p className="mt-5 max-w-2xl text-base leading-7 text-zinc-400 sm:text-lg">{description}</p> : null}
        </div>
        <div className="mt-12">{children}</div>
      </div>
    </section>
  );
}
