import type { Metadata } from "next";
import { Suspense } from "react";
import { PageViewTracker } from "@/components/analytics/pageview-tracker";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Providers } from "@/components/providers";
import { siteMetadata } from "@/lib/site-content";
import "./globals.css";
import "./cinematic.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteMetadata.title,
    template: `%s | ${siteMetadata.title}`,
  },
  description: siteMetadata.description,
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: siteMetadata.title,
    description: siteMetadata.description,
    url: siteUrl,
    siteName: siteMetadata.title,
    images: [
      {
        url: "/assets/observatory/social-preview.webp",
        width: 1440,
        height: 1000,
        alt: "NullCS: Beyond the score. A precision optical instrument for behavioral research.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteMetadata.title,
    description: siteMetadata.description,
    images: ["/assets/observatory/social-preview.webp"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>
          <div className="relative isolate min-h-screen overflow-x-clip">
            <SiteHeader />
            <noscript>
              <style>
                {"#main-content{display:none}.menu-toggle{display:none}"}
              </style>
              <section className="subpage">
                <p className="technical-label">NULLCS / STATIC OVERVIEW</p>
                <h1>Beyond the score.</h1>
                <p className="subpage-intro">
                  NullCS is independent behavioral analysis research for
                  Counter-Strike 2. Demo telemetry becomes encounter windows,
                  temporal model outputs, and ranked players for human review.
                  These are review signals, not cheating verdicts.
                </p>
                <p className="subpage-intro" style={{ marginTop: 24 }}>
                  The Windows desktop application runs analysis locally and
                  exports a readable report. Enable JavaScript for the
                  interactive research presentation and configured website
                  download, or visit the repository for documentation and
                  published releases.
                </p>
                <a
                  className="instrument-button"
                  style={{ marginTop: 32 }}
                  href="https://github.com/gjones01/NullCS"
                >
                  Project and release information ↗
                </a>
              </section>
            </noscript>
            <main id="main-content">{children}</main>
            <SiteFooter />
          </div>
          <Suspense fallback={null}>
            <PageViewTracker />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
