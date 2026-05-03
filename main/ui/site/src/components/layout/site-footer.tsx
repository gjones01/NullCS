import Link from "next/link";
import { footerLinks } from "@/lib/site-content";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/8 py-10">
      <div className="container flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-display text-lg tracking-[-0.04em] text-white">NullCS</div>
          <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-500">
            Counter-Strike 2 behavioral review research focused on structured demo analysis, explainable signals, and local desktop review tooling.
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm text-zinc-400">
          {footerLinks.map((item) => (
            <Link key={item.href} href={item.href} className="transition-colors hover:text-white">
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </footer>
  );
}
