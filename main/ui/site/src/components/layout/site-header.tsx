import Image from "next/image";
import Link from "next/link";
import { Menu } from "lucide-react";
import { navItems } from "@/lib/site-content";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,7,12,0.78)] backdrop-blur-sm">
      <div className="container flex h-18 items-center justify-between gap-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/assets/nullcs-logo-cropped.png"
            alt="NullCS logo"
            width={34}
            height={34}
            className="h-9 w-9 rounded-sm"
          />
          <div>
            <div className="font-display text-sm uppercase tracking-[0.28em] text-zinc-200">NullCS</div>
            <div className="text-xs text-zinc-500">Behavioral review research</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm text-zinc-400 transition-colors hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <Link
          href="/beta"
          className="hidden rounded-full border border-white/12 bg-white/[0.04] px-5 py-3 text-sm text-zinc-100 transition-colors hover:bg-white/[0.08] md:inline-flex"
        >
          Beta soon
        </Link>

        <button
          type="button"
          aria-label="Navigation menu"
          className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 text-zinc-300 md:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
