import type { Metadata } from "next";
import { Download, ArrowUpRight } from "lucide-react";
import Image from "next/image";
import { desktopReleaseUrl } from "@/lib/desktop-release";
import publishedRelease from "@/lib/published-desktop-release.json";

export const metadata: Metadata = { title: "Download NullCS" };

export default function AnalyzePage() {
  const download = desktopReleaseUrl(process.env.NULLCS_DESKTOP_DOWNLOAD_URL ?? publishedRelease.downloadUrl);
  return (
    <div className="subpage">
      <div className="section-register">
        <span>NULLCS / DESKTOP APPLICATION</span>
        <span>WINDOWS x64 / BETA</span>
      </div>
      <div className="download-layout">
        <div>
          <h1>
            Look closer.
            <br />
            <em>Locally.</em>
          </h1>
          <p className="subpage-intro">
            The NullCS research pipeline, on your computer. Analyze a CS2 demo,
            inspect ranked players, and save a straightforward report.
          </p>
          <div style={{ marginTop: 32 }}>
            {download ? (
              <a href={download} className="instrument-button">
                Download for Windows <Download size={18} />
              </a>
            ) : (
              <button disabled className="instrument-button">
                Windows release in preparation <Download size={18} />
              </button>
            )}
          </div>
          <p className="download-status">
            {download
              ? "Community beta: this Windows installer is unsigned and may show an unknown-publisher warning. Download only from the linked GitHub release; do not disable security protections."
              : "The desktop community beta is being prepared. The download will appear here when it is published."}
          </p>
          <p className="technical-label" style={{ marginTop: 24 }}>
            WINDOWS 10/11 / 64-BIT / CPU INFERENCE
          </p>
          <p className="download-status">
            This beta uses the earlier experimental model bundle. The new internal
            benchmarks describe the corrected research baseline, which has not
            replaced this download. See the research notes for current limitations.
          </p>
        </div>
        <div className="download-art">
          <Image
            src="/assets/observatory/desktop-report.webp"
            alt="Real NullCS desktop report with ranked player results"
            width={1700}
            height={1125}
            priority
            sizes="(max-width: 1000px) 90vw, 45vw"
          />
          <p className="data-caption">
            Actual application capture / local validation demo
          </p>
        </div>
      </div>
      <dl className="spec-list">
        <div>
          <dt>01 / Your data stays local</dt>
          <dd>
            Choose or drop a .dem file up to 1 GiB. Analysis runs on your CPU.
            No account or demo upload is required.
          </dd>
        </div>
        <div>
          <dt>02 / Results you can read</dt>
          <dd>
            Review order, model score, and calibrated estimate are presented
            separately. Compare players with interactive score and benchmark
            charts, then save a plain-text report with a score guide.
          </dd>
        </div>
        <div>
          <dt>03 / A complete runtime</dt>
          <dd>
            The installer includes the local inference engine and model
            artifacts. You do not need a separate Python installation.
          </dd>
        </div>
        <div>
          <dt>04 / Keep the client current</dt>
          <dd>
            Automatic updates are not configured in this beta. Check GitHub
            Releases for new installers. Parser and model updates ship together.
          </dd>
        </div>
      </dl>
      <p className="release-note">
        <strong>Research beta.</strong> Models will continue to improve with
        newer data. Some matches show clear cheating behavior; others need
        encounter context and evidence from more matches. This build analyzes
        one demo at a time. Comparing a player across multiple demos is a planned
        research direction.
      </p>
      <a
        className="text-link"
        style={{ marginTop: 35 }}
        href="https://github.com/gjones01/NullCS"
        target="_blank"
        rel="noreferrer"
      >
        Repository and release documentation <ArrowUpRight size={16} />
      </a>
    </div>
  );
}
