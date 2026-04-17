import type { Metadata } from "next";
import { Suspense } from "react";
import { PageViewTracker } from "@/components/analytics/pageview-tracker";
import { BackgroundEffects } from "@/components/layout/background-effects";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Providers } from "@/components/providers";
import { siteMetadata } from "@/lib/site-content";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteMetadata.title,
    template: `%s | ${siteMetadata.title}`,
  },
  description: siteMetadata.description,
  openGraph: {
    title: siteMetadata.title,
    description: siteMetadata.description,
    url: siteUrl,
    siteName: siteMetadata.title,
    images: [
      {
        url: "/assets/hero-cs-bg.png",
        width: 1600,
        height: 900,
        alt: "NullCS project atmosphere",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteMetadata.title,
    description: siteMetadata.description,
    images: ["/assets/hero-cs-bg.png"],
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
          <div className="relative min-h-screen overflow-x-hidden">
            <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top_right,rgba(217,122,74,0.14),transparent_22%),radial-gradient(circle_at_left,rgba(255,255,255,0.04),transparent_18%)]" />
            <BackgroundEffects />
            <SiteHeader />
            <main>{children}</main>
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
