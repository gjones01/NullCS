# NullCS / The Observatory

The website opens with the existing CT portrait without the previous helix. Graphite, chrome, silver, and restrained instrument lighting replace the previous blue presentation. The narrative moves through observation, recorded telemetry, the model pipeline, the local desktop tool, research, and interpretation.

## Implementation

- `src/components/cinematic/experience.tsx`: page narrative, actual telemetry controls, six-stage scroll sequence, motion control, and dimensional application showcase.
- `src/components/cinematic/instrument-engine.ts`: CSS 3D media cards and Three.js telemetry, physically based materials, a generated studio environment, and recorded-data traces. No third-party runtime asset requests are required.
- `src/components/cinematic/scene.tsx`: viewport-triggered dynamic import, lifecycle cleanup, WebGL failure handling, and CSS still-view fallback.
- `src/app/cinematic.css`: responsive art direction and motion. Native scrolling is retained; there is no scroll hijacking or mandatory introduction.
- `src/components/layout/site-header.tsx` and `site-footer.tsx`: persistent desktop CTA, mobile navigation, project links, and keyboard access.
- `/about` and `/analyze`: redesigned research and download pages. Existing API and historical job routes remain intact.
- `layout.tsx`, `robots.ts`, `sitemap.ts`, and `public/favicon.svg`: metadata, icon, download-page discovery, and a static no-JavaScript overview. The framework streams client-page content through a JavaScript reveal, so the no-JavaScript overview is intentionally separate from the interactive presentation.

New dependencies are `three` 0.174.0 and matching `@types/three` 0.174.0. The lockfile pins installed versions. No Python, research, model, calibration, inference, installer, or updater code was changed for this redesign.

## Data and claims

`public/assets/observatory/encounter-sample.json` contains the first 64 encounter rows from the verified local run of `TEST_20260501_102349_02b8afde.dem` (de_inferno). The three channels are `aim_error_min`, `mouse_delta_abs_mean`, and `angular_velocity_mean`; none of these selected values were null. Values were rounded to four decimal places for display. Player names and identifiers are omitted. Traces are independently normalized for geometry; the scrubber reports the recorded value with its unit. These are encounter summaries, not a reconstructed tick trajectory or a classification result.

The desktop image is a compressed capture of the actual ten-player result displayed by the native app in the preceding integration validation. The CT artwork is reused from the existing project; the processing-plane motifs are conceptual, not fabricated analysis output. Existing benchmark numbers and figures were retained with dataset and interpretation context. The research page documents the parser and calibrator limitations.

## Rendering and accessibility

Scenes load near their viewport and stop drawing offscreen or when the document is hidden. Rendering is capped at approximately 30 frames per second; DPR is capped at 1.5 on desktop and 1.25 on narrow screens. Sustained slow renders reduce DPR to 1. Geometry, materials, environment textures, observers, event listeners, and animation callbacks are disposed on unmount.

Motion preferences follow the OS, with a visible override. Reduced motion draws a static scene and replaces the long pinned pipeline with direct stage selection. Mobile uses direct stage controls and a separate composition. The SVG telemetry graph and textual pipeline remain available independently of WebGL. Context loss and unavailable WebGL fall back to the CT portrait (other scenes retain their CSS illustration). No-JavaScript visitors receive a static project overview and repository/release link.

The CT hero uses no WebGL canvas and a 68,098-byte WebP derived from the existing portrait. These are local asset/render counts, not production frame-rate guarantees.

## Download and deployment

The existing server-side `NULLCS_DESKTOP_DOWNLOAD_URL` validation is unchanged: only an HTTPS `.exe` release URL under `github.com/gjones01/NullCS/releases/download/` is accepted, without credentials, query, or fragment. No release URL was invented. The page remains disabled until a real signed public release is configured. See the root `DESKTOP_RELEASE.md` for signing and publication requirements.

Build with `npm.cmd run build`; run with `npm.cmd run start -- --hostname 127.0.0.1 --port 3002`. The local verification preview uses port 3002. Existing Vercel environment settings, including `NEXT_PUBLIC_SITE_URL`, remain applicable. This work was not deployed or published.

## Verification record

Production build and TypeScript check passed. Existing `node --experimental-strip-types --test tests/analysis-security.test.mjs` passed both tests. Browser validation used the production build in headless Microsoft Edge at 1440×1000, 390×844, and 320-pixel widths, with screenshots inspected manually.

Verified real WebGL rendering, all six scroll stages, direct mobile stage selection, telemetry channel/scrubber updates, mobile navigation, the existing release gate, motion pause, OS reduced motion, forced WebGL context loss, WebGL-unavailable behavior, and the visible no-JavaScript overview. The final browser run recorded no console/runtime errors or failed resource responses. The WCAG 2 A/AA and 2.1 AA axe checks on the home and download pages reported no violations after contrast corrections. Automated checks do not replace a complete manual accessibility audit or physical-device GPU testing.

## Existing dependency advisories

The production dependency audit reported five affected packages: Next.js (critical), sharp and source-map-js (high), fflate (moderate), and dompurify (low). Three.js itself was not listed. These advisories concern the existing dependency graph and were not addressed with a broad upgrade during this visual task. Resolve and revalidate them before public deployment; the local production preview is bound to loopback. The audit details and browser evidence are in the ignored local `main/data/web_validation` directory.

## Illustrated pipeline cards (2026-10-09)

The hero helix has been removed; the existing CT portrait remains. The six-stage scroll sequence now uses perspective-transformed HTML cards so video controls, tables, and diagrams remain accessible and sharp. Native scrolling and the existing stage navigation remain. Inactive cards are inert; reduced motion disables transitions and diagram animation. No ML code or result semantics changed.

Card sources:

1. Demo: user-supplied `NullCS BRoll.mov`, converted to local `nullcs-broll.mp4` (H.264, 1280x720, fast-start, audio track removed). Original MOV is unchanged. Native video is muted, loops, plays inline, and hides playback controls. Autoplay follows motion preference; the video unmounts offscreen, on stage change, or while the tab is hidden. There are no third-party video requests. The original MOV is excluded from git and Vercel upload; only the optimized copy and poster are needed for the website.
2. Telemetry: seven actual encounter-summary rows from the existing `encounter-sample.json`, with feature units; these are not raw tick rows.
3. Windows: existing `real-visibility-context-timeline.png`, compressed to WebP. Actual encounter summaries from `TEST_20260407_130853_1f420890`, explicitly distinguished from a raw 32-tick sequence.
4. Temporal model: a conceptual neural network with curved, flowing connections and subtly drifting nodes. Layer labels retain the verified 64/96/128 channel progression and pooling/head stage; displayed node counts and motion are illustrative, not measured activations or literal model topology. Animation runs only for the active card and respects reduced motion.
5. Aggregation: existing real within-lobby multi-lens percentile chart, compressed to WebP; not a cheating probability or a new ranking formula. Source generator: `main/scripts/generate_real_trailer_graphs.py`.
6. Review: existing real desktop results screenshot from local validation. The footage and individual evidence samples are not presented as a single linked demo run.

Production build, six-stage desktop scroll, mobile stage selection, no horizontal overflow, reduced-motion behavior, and home axe checks were exercised using local validation scripts under `main/data/web_validation`. On October 10 the rebuilt site passed these checks again, plus About navigation and the unavailable-release download state, at http://127.0.0.1:3004. The current video is local and silent. Not deployed.
