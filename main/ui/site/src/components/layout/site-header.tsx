"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Menu, X } from "lucide-react";
export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  return (
    <header className="lab-header">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Link className="lab-brand" href="/" aria-label="NullCS home">
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
          <path
            d="M14 2 24.4 8v12L14 26 3.6 20V8Z"
            fill="none"
            stroke="currentColor"
          />
          <path
            d="m14 8 5.2 3v6L14 20l-5.2-3v-6Z"
            fill="none"
            stroke="currentColor"
          />
          <path
            d="M14 2v6m10.4 0-5.2 3m5.2 9-5.2-3M14 26v-6M3.6 20l5.2-3M3.6 8l5.2 3"
            stroke="currentColor"
          />
        </svg>
        <span>
          NULLCS<small>INDEPENDENT RESEARCH</small>
        </span>
      </Link>
      <nav className="lab-nav" aria-label="Main navigation">
        <Link href="/#signals">Observation</Link>
        <Link href="/#pipeline">Process</Link>
        <Link href="/about">Research</Link>
      </nav>
      <div className="header-actions">
        <Link className="header-download" href="/analyze">
          Desktop app <ArrowUpRight size={15} />
        </Link>
        <button
          className="menu-toggle"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          aria-controls="mobile-navigation"
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>
      {open && (
        <nav
          id="mobile-navigation"
          className="lab-mobile-nav"
          aria-label="Mobile navigation"
        >
          {[
            { href: "/#signals", label: "Observation" },
            { href: "/#pipeline", label: "The process" },
            { href: "/about", label: "Research notes" },
            { href: "/analyze", label: "Desktop app" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
            >
              {item.label}
              <ArrowUpRight size={20} />
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
