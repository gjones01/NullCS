import Link from "next/link";
import { githubUrl } from "@/lib/site-content";
export function SiteFooter() {
  return (
    <footer className="lab-footer">
      <div className="footer-top">
        <p>
          NULLCS / INDEPENDENT RESEARCH
          <br />
          <span>A closer look at your CS2 replays.</span>
        </p>
        <nav aria-label="Footer navigation">
          <Link href="/about">About NullCS</Link>
          <a href={githubUrl} target="_blank" rel="noreferrer">
            GitHub ↗
          </a>
          <Link href="/analyze">Desktop app ↗</Link>
          <a href="#main-content">Back to top ↑</a>
        </nav>
      </div>
      <div className="footer-wordmark" aria-hidden="true">
        NULLCS<span>®</span>
      </div>
      <div className="footer-bottom">
        <span>BUILT FOR CLOSER OBSERVATION.</span>
        <span>NOT AFFILIATED WITH VALVE.</span>
      </div>
    </footer>
  );
}
