# NullCS desktop beta

**Community beta distribution (October 10, 2026):** this GPLv3 GitHub prerelease is unsigned. The site and release notes disclose the unknown-publisher status and manual updates. This community-beta path supersedes the earlier blanket hold on unsigned downloads; the fully signed release procedure remains available for future releases. Automatic updates stay disabled until signing keys/feed are configured; no verification bypass is permitted. Clean-machine certification remains unverified. LICENSE, NOTICE.md and collected third-party notices accompany the distribution.

The release candidate is `NullCS_0.1.0-beta.1_x64-setup.exe`, **389,857,409 bytes**, SHA-256 `0f45bba38cd497f03e30c945b120a358ccfec6165c667c92d69950d94b3ac326`. It includes GPLv3 and third-party notices (593 dependency inventory records). All 61 backend manifest hashes passed; the final frozen engine processed the validation demo into ten ranked players in **37.27 seconds** on the developer workstation. Defender completed a targeted scan with no detection event observed during that scan. These checks do not establish clean-machine compatibility or eliminate all security risks.

Release location: https://github.com/gjones01/NullCS/releases/tag/v0.1.0-beta.1. The installer contains the runtime/models; the separate model ZIP is for developers rebuilding the corresponding source tag. Verify assets against the release's `SHA256SUMS.txt`. Earlier dated entries below are historical validation records: their installer hashes, unpublished status and blanket signing gates are superseded by this explicitly unsigned beta policy. The signed-update procedure and unresolved parser, calibration, maintenance, build-tool and clean-machine limitations still apply.

The active desktop entry point is `main/ui/web/src/DesktopApp.tsx`. It replaces the old multi-page UI at startup; the previous `App.tsx` and research explanation components remain in the repository but are not imported into the client bundle. `/analyze` on the Next.js site is now the Windows download page. No hosted inference server is required for this product path.

## Local workflow

Windows x64: choose or drop one CS2 `.dem` (maximum 1 GiB), run local analysis, read ranked players, and save a plain-text report through the native Save dialog. The score guide defines each displayed value. Explanations are not generated. Research warnings remain visible under report limitations and are included in the saved report. Scores are not cheating verdicts.

The Tauri shell starts an authenticated, loopback-only FastAPI sidecar with a random per-launch token held in memory. The UI uses native drag/drop and file selection. The engine checks the file header, size, and extension. The canonical boundary remains `main/scripts/run_infer_pipeline.py`, invoked through the packaged `run-infer` command. `/api/desktop/demo/{id}/result` reads the canonical per-demo CSV, manifest, and score trace without re-sorting, recomputing scores, generating explanations, or loading interpretation dataframes. Null calibration stays null. Features, model weights, calibration, sequence construction, and ranking formulas are unchanged.

States follow actual pipeline logs: queued, parsing, feature processing, temporal inference, scoring, results ready; failures remain explicit. A serial executor lock protects shared ranking writes. A native single-instance lock prevents two clients sharing the same data directory. Interrupted jobs fail on startup; the child watches its parent pipe and exits if the API dies. Normal application exit and update installation stop the API process tree. In packaged builds, the API also watches a pipe owned by the desktop shell and exits if that shell crashes. Polling is every 2.5 seconds, below the default request refill rate.

Local storage is `%APPDATA%/app.nullcs.desktop/backend-data/`: `raw_uploads`, `processed`, and `state`. Demos/reports persist locally. There is no automatic deletion policy yet; users can remove this directory after closing NullCS, which also removes their analysis history. No telemetry is added. Updates are the intended external network access; they do not upload demos. Input files are untrusted: run the app without administrator privileges. A local parser process is not a hardened OS sandbox.

## Visuals and performance

Black/blue glass panels, pointer-reactive orbital particles, and quiet opt-in synthesized interaction tones. Sound defaults off. Motion can be disabled and respects OS reduced-motion settings; the canvas is capped at approximately 30 redraws/second and DPR 1.5, pauses when hidden or analyzing, and does not rerender React per animation frame. The frontend excludes the former Three.js scene, marketing videos, bundled samples, and explanation UI. `publicDir: false` prevents unused public assets being copied into the desktop bundle.

No inference feature or numerical optimization was introduced. The existing CLI still loads its models and parses the demo using the established methodology. Packaging currently uses the existing PyInstaller one-file approach, which adds extraction/startup overhead. Keep that overhead in capacity/runtime measurements; do not call browser bundle size an inference speedup.

## Artifact integrity and updates

Local models cannot be kept secret from the machine owner. This design protects distribution integrity, not confidentiality or resistance to an administrator modifying the application.

- Release builds only resolve the verified packaged backend; they cannot fall back to `C:/NullCS` or another source checkout.
- The application embeds the backend manifest SHA-256. Native streaming SHA-256 verifies listed files before launching the sidecar. Changed cached model files are refreshed from the verified package at launch; canonical model files are required during packaging.
- Only the eight verified default model artifacts are copied into the release payload. Experimental model variants, secrets, demo datasets, and training caches are not part of that selection. Research CLI override behavior is unchanged; the distribution intentionally ships the canonical bundle.
- Do not edit generated resources after building the application. Re-run `scripts/prepare-desktop-backend.ps1` whenever Python, parser, model, or dependency content changes.
- The updater uses Tauri's signature verification, HTTPS, a build-pinned public key and endpoint, and signed-version enforcement. There is no unsigned fallback or URL supplied by browser content. Checks run at launch, every six hours while visible/idle, and on demand. Installation requires a click and is disabled while analysis is running. An offline check failure does not disable local analysis.
- Updates ship the whole tested app/backend/model bundle. No client-side `pip install` or independent parser/model replacement occurs. CS2 schema mismatches fail rather than filling missing model inputs.

The PyInstaller hooks explicitly collect SciPy array-API compatibility modules, XGBoost native libraries and its VERSION file, and parser/XGBoost/pandas distribution metadata. Each package must pass a `check-runtime` import and provenance smoke test before its manifest is generated.

Dependencies added: Rust `sha2` for native hashing (replacing per-file certutil subprocesses), and `tauri-plugin-updater` pinned to 2.12.0 for signed updates. Cargo.lock includes its required transitives. Rust minimum is 1.90; validation used 1.94.1. No Python or ML dependency versions were upgraded. Standard release builds must have the same tested Python 3.13 environment/artifacts used to rebuild the sidecar.

## Release setup (not yet provisioned)

Use the isolated desktop release runtime, not the research virtual environment. On Windows x64 with Python 3.13, create a fresh virtual environment and install `main/ui/web/scripts/requirements-desktop.lock.txt` with `pip install --only-binary=:all: -r ...`. Set `NULLCS_RELEASE_PYTHON` to its absolute `Scripts/python.exe` path. This build-only setting selects the same interpreter for audit, tests, and packaging. The runtime verifier rejects missing, changed, or extra packages. The current local validated environment is `C:\ClarityCS\main\data\web_validation\release-venv`; it is generated and must not be committed. Keep audit tooling in a separate environment selected by `NULLCS_AUDIT_PYTHON`.

GitHub release repository: https://github.com/gjones01/NullCS. No release has been published by this change. GitHub write access can be granted with the GitHub connector or `gh auth login`; never paste a token into chat or the repository.

1. Generate a Tauri signing key with the installed Tauri CLI signer, keep the private key/password in secure release secrets, and back it up. Set `NULLCS_UPDATE_PUBLIC_KEY` to the public key contents. This is separate from Windows signing.
2. Configure a Windows code-signing certificate/service and timestamp service. The provided release script supports a certificate thumbprint in the Windows certificate store. Other signing services need their documented sign-command integration.
3. Set `NULLCS_UPDATE_ENDPOINT` to a public HTTPS `latest.json` release feed. For GitHub, a latest-release asset URL can serve it; use a deliberate channel for prereleases because GitHub's latest-release alias does not select prereleases. The URL must be reachable without embedding a repository access token in the client.
4. Supply `TAURI_SIGNING_PRIVATE_KEY`, optional `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`, `NULLCS_WINDOWS_CERT_THUMBPRINT`, and `NULLCS_WINDOWS_TIMESTAMP_URL` in the release shell/secret store. `NULLCS_UPDATE_ENDPOINT` and `NULLCS_UPDATE_PUBLIC_KEY` are public build inputs embedded into Rust; all signing private credentials stay outside the application.
5. Install `cargo-audit` on the release runner's PATH, and install `pip-audit` in a separate tooling virtual environment (not the model environment). Set server/operator-only `NULLCS_AUDIT_PYTHON` to that environment's Python executable. Put Windows SDK `signtool.exe` on PATH. Dependency audits require access to their advisory services; failures block release. Bump the version in `src-tauri/tauri.conf.json` and `Cargo.toml`. From `main/ui/web`, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-signed-release.ps1 -InstallerUrl 'https://github.com/gjones01/NullCS/releases/download/<tag>/<actual-installer-name>.exe'
```

The script runs Python/Rust/frontend dependency audits and backend/native regression tests before building. It rebuilds the backend and frontend, generates Tauri update artifacts, and requires valid timestamped Windows signatures on the installer, native application, and backend executable. The backend is signed before its integrity manifest is generated. Stale installers are rejected. It writes `latest.json` but does not upload or publish anything. The update signature must contain a signed version matching the feed; use a Tauri CLI that supports version-bound signatures and verify the update from the previous installed release before publication. Missing configuration fails the release preparation explicitly.

6. Test a clean Windows machine without Python: install, startup, actual demo, report save, corrupt file, second instance, restart, and update from the previous version. Verify a tampered updater payload is rejected, TLS errors do not bypass validation, and model hashes match the published bundle. This is a release gate, not replaced by unit tests.
7. Publish the verified installer, its `.sig`, and `latest.json` as public release assets. Preserve old releases for rollback investigation; the updater does not enable downgrades.
8. Set Vercel's server-side `NULLCS_DESKTOP_DOWNLOAD_URL` to the exact verified GitHub installer asset URL and redeploy the website. The page only accepts HTTPS `.exe` release URLs under `gjones01/NullCS`. Until configured, it displays an unavailable download button, not a stale installer.

## Development and validation

From `main/ui/web`: `npm.cmd run desktop:dev`, `npm.cmd run build`, and `npm.cmd run desktop:check`. Rust tests: `cargo test --manifest-path src-tauri/Cargo.toml --lib`. The browser preview shows the interface but intentionally cannot start local inference; use the native application.

Backend tests: `NewAnubisTri/.venv/Scripts/python.exe -B -m pytest main/ui/api/tests/test_desktop_result.py main/ui/api/tests/test_security.py main/ui/api/tests/test_analysis.py main/ui/api/tests/test_parser_required_columns.py main/ui/api/tests/test_pipeline_child.py main/ui/api/tests/test_config.py -q -p no:cacheprovider`.

Known research limitations remain: demoparser2 0.41.4 stale user-command values, the saved sklearn calibration version warning, and no guarantee that calibrated estimates generalize to a particular match. The passing parser sentinel verifies the column contract, not the freshness of all input values. Those behaviors were not changed for desktop integration.

### Recorded local checks (2026-10-08)

- The six-file Python suite above passed: 62 tests, including API security, required-column rejection, report ordering/calibration, invalid/oversized local demos, and pipeline child failure behavior. The focused desktop/child subset passed again after watchdog changes (11 tests).
- Rust library tests passed: 3 tests covering SHA-256, refreshing changed cached models, and the external URL allowlist.
- The frozen API parent-watchdog test passed: closing the parent pipe stopped the service with the intended exit code 75 in 2.01 seconds.
- Closing the final native window stopped both of its owned backend processes. The app was then reopened without the validation-only browser debugging port.
- The full patch-14153 parser sentinel passed (1,089,620 tick rows). Decorative-field warnings and the existing sklearn calibration-version warning remain visible.
- Next.js and desktop production frontend builds passed. The active desktop JavaScript bundle is 178.37 kB (56.51 kB gzip); CSS is 6.65 kB (2.47 kB gzip).
- The real 232,415,622-byte sentinel demo completed through the source desktop API in 51.71 seconds and through the frozen backend in 56.29 seconds, each producing ten players. Player ranks and scores were exactly identical. These are single local observations under concurrent build activity, not a controlled benchmark or a general determinism guarantee. A missing frozen parser-version field discovered in the comparison was corrected by packaging its distribution metadata.
- The final native release application processed `TEST_20260501_102349_02b8afde.dem` through its drop handler and Analyze button, rendered ten real players in 82.45 seconds, and saved a 2,633-byte report through the Windows Save dialog. Its ranks and scores exactly matched the source run; parser provenance reported 0.41.4 and both research warnings were visible. No frontend errors were recorded. This also verified the corrected sidecar bootstrap order: the bundled module paths are established before importing the inference watchdog.
- The local NSIS installer built successfully (378,508,232 bytes), but is deliberately unsigned and unpublished. SHA-256: `90731012a1cf77a4c9ac0a93580cea6668677de2885e167e3dfb5f0755e01045`. It is a workstation test artifact, not an approved public release.

Public release remains gated on Windows and updater signing, an actual release feed, clean-machine installation testing, and an update from a previous signed version. This workstation has development tools installed, so its passing packaged run is not a substitute for a clean-machine test.

### Release review (2026-10-09)

**Release blocked: dependency advisories remain unresolved. Do not distribute the unsigned workstation candidate as an approved release.** The full installed Python environment audit reported advisory matches in ten packages: aiohttp 3.13.3, datasets 4.6.0, fsspec 2026.2.0, multidict 6.7.1, Pillow 12.1.0, pytest 9.0.2, requests 2.32.5, setuptools 81.0.0, torch 2.11.0, and urllib3 2.6.3. Its 102 advisory records include aliases/duplicates and tooling packages; this is not a finding that 102 distinct vulnerabilities are reachable through demo analysis. The PyTorch advisory is PYSEC-2025-194, with 2.13.0 listed as fixed. Do not upgrade that runtime in place: prepare a separate candidate environment, resolve advisories, rebuild, and validate model loading, calibration, parser contract, and real-demo parity before promoting it. No Python/model dependencies or research behavior were changed in this review.

The desktop production npm audit reported zero vulnerabilities. Cargo audit reported zero vulnerability entries but maintenance warnings for proc-macro-error and five unic crates, plus the glib soundness advisory RUSTSEC-2024-0429. Review target applicability and remediation; a zero vulnerability count is not a clean bill of health. Raw reports are local validation artifacts under `main/data/web_validation/desktop-{python,rust,audit}*`, not distributable application content.

Application fixes:

- Local demo requests now require a strict schema, local-drive paths, and server-generated job IDs. UNC/device paths, malformed payloads, and client-supplied IDs are rejected. Desktop server exceptions no longer return internal diagnostics.
- Queued status safely handles the period before a log exists. Log reads are bounded to the last 128 KiB. This fixes a reproduced HTTP 500 immediately after queuing a real demo.
- Starting a second analysis clears the previous job before polling begins. Frontend API/result requests have a 30-second timeout. OS reduced-motion changes are honored, and drag-handler registration failures provide a usable fallback message.
- Native engine startup is serialized to prevent concurrent IPC requests from launching duplicate sidecars. Generated resource cleanup excludes `.env*` and private-key/certificate filename extensions. This filename filter supplements the explicit payload allowlist; it is not a content-level secret scanner.

Current validation:

- `python -B -m pytest main/ui/api/tests -q -p no:cacheprovider --basetemp main/data/web_validation/release-tests-final --tb=short`: **72 passed**, one FastAPI/httpx deprecation warning.
- `cargo test --manifest-path main/ui/web/src-tauri/Cargo.toml --lib`: **3 passed** after the startup serialization change.
- `python main/scripts/check_parser_contract.py`: passed the patch-14153 full parse, **1,089,620 rows**. Decorative-property and existing research limitations remain.
- Desktop frontend and native `npm run desktop:build -- --no-bundle` builds passed; packaged `check-runtime` passed. Current JavaScript: 178.71 kB, 56.60 kB gzip. This built an unsigned executable, not a new release installer; the October 8 installer above is stale relative to these fixes.
- A real 232,415,622-byte demo completed via the source desktop API in **74.40 s** and the rebuilt frozen API in **62.85 s**, each producing ten players and reporting Queued, Parsing, Feature processing, Temporal inference, Scoring, Results ready. These are individual local observations, not controlled performance benchmarks.
- Source and rebuilt frozen runs had exactly identical player IDs, ranks, model scores, review scores, and calibrated probabilities. All **61** packaged manifest hashes independently verified, with no prohibited secret filenames found.
- The rebuilt native app's actual drop-event handler and Analyze button produced and rendered ten players in **64.01 s**. Browser automation recorded no page errors and verified OS reduced-motion handling; the resulting native screenshot was inspected. This used a temporary loopback WebView debugging port for validation, not a shipped debugging setting.
- A second analysis in the same native session cleared the old results correctly and again rendered ten players. Exact ranks and numerical scores matched the source/frozen runs. This repeatability observation covers this demo and machine only.
- Targeted Windows Defender scans of both rebuilt executables completed (Operational events 1000/1001), with no detection event in the scan interval. Signatures were dated October 9. This does not establish reputation or behavior on other antivirus products; the native candidate remains `NotSigned`.
- The website production build and browser checks passed for all six rolling cards and mobile layout; desktop/mobile screenshots of the new temporal network were inspected. The graphic is explicitly conceptual and does not fabricate model activations.

Before publishing, also complete clean-machine install/uninstall, real signed update and tamper tests, supported Windows/WebView2 checks, and antivirus/reputation review of the final signed binaries. None of those is established by a successful developer-workstation run. Local artifact confidentiality, a hardened parser sandbox, automatic retention, and broad production capacity guarantees remain outside what this client currently provides.

### Security remediation (2026-10-10; supersedes the dependency blocker above)

An isolated Windows/Python 3.13 runtime now passes `pip check` and `pip-audit` with **no known vulnerabilities reported**. Exact versions, including build tools, are recorded in `main/ui/web/scripts/requirements-desktop.lock.txt` (95 packages). Security updates were limited to aiohttp 3.14.3, datasets 5.0.1, fsspec 2026.6.0, multidict 6.9.1, Pillow 12.3.0, pytest 9.0.3, requests 2.33.0, setuptools 83.0.0, torch 2.13.0, urllib3 2.8.0, and the new virtual environment's pip 26.2. These address the scanner findings, not feature requests. PyPI and the raw upstream PyTorch advisory differed on affected versions; the release candidate uses the PyPI-listed fixed version rather than suppressing the finding.

The existing research environment and worker requirements remain unchanged. Model weights, architectures, feature contracts, parser version, sklearn version, calibration, and ranking formulas remain unchanged. In the candidate environment all **72 backend tests passed**; the full patch-14153 sentinel passed; a real 232,415,622-byte demo produced ten players in **37.09 seconds** through the desktop API. Player identities, ranks, raw scores, calibrated probabilities, and review scores matched the original runtime exactly. This is evidence for the tested demo, not proof of parity on every possible input or a performance benchmark. An integration bootstrap bug was fixed: `run_infer_pipeline.py` no longer removes virtual-environment paths merely because their name contains `ClarityCS\main`.

The Windows Cargo dependency tree excludes `glib` and `proc-macro-error`, so those advisory warnings do not describe the Windows shipped runtime. The five `unic` maintenance warnings do apply transitively through Tauri's URL parser and remain tracked; no vulnerable code finding was reported by Cargo audit. No advisory suppression was added.

The website's compatible security updates removed all **production** npm audit findings (including the Next.js update to 16.4.0). Three Node tests, the production build, desktop/mobile browser checks, About navigation, and safe unavailable-download handling passed. Seven build/development graph findings remain through Tailwind 3 (`braces`/`postcss-selector-parser` and their dependents). Their input is repository-controlled build configuration/styles; do not run untrusted contributions on a release runner holding signing secrets. A Tailwind 4 migration is separate work; `npm audit fix --force` was deliberately not used. The website download validator now rejects nonstandard ports, credentials, queries, fragments, extra path segments, malformed escapes, encoded separators, and control characters.

Publication still requires a Windows code-signing certificate, Tauri update-signing credentials, the real release feed, and signed clean-machine installation/update testing. No code-signing certificate was found in the current-user or machine certificate stores. The website can be deployed with downloads disabled while these are arranged. Do not point its download setting at an unsigned local installer or push generated executables/model caches into Git. Respect the repository's documented unrelated public `main` history when preparing a reviewed publication branch.

Final October 10 artifacts and checks:

- Rebuilt frozen API: ten real players in **33.89 s**, exact score/rank parity with the original runtime; all 61 package hashes verified. Native app: ten players rendered in **54.03 s**, no recorded page errors. These are individual workstation observations under concurrent build activity.
- Frozen service rejects unauthenticated requests (401), UNC paths (400), client-injected job IDs (422), and nonexistent local files (400). Unavailable desktop results retain the existing 409 response contract. A deliberately corrupt replay failed with a high-level parser message in the native UI, removed old results, and allowed retry. Normal window close left no backend processes running.
- Direct local launch: `main/ui/web/src-tauri/target/release/nullcs-desktop.exe`. Keep its generated resource directories alongside it; the executable alone is not a portable distribution.
- Fresh local installer: `main/ui/web/src-tauri/target/release/bundle/nsis/NullCS_0.1.0-beta.1_x64-setup.exe`, **389,440,214 bytes**, SHA-256 `3fed147c979057e78ef0f25e8339caa656e8a8709faa828e5034c86f0bb2debc`. Authenticode status: **NotSigned**. Targeted Defender scan completed with no detection event observed in the scan interval. This supersedes the stale October 8 installer, but remains a local test candidate, not a public release.

To publish: prepare a scoped publication branch preserving the public repository history; deploy `main/ui/site` with its tested lockfile and the download unset; provision signing credentials/feed; run `build-signed-release.ps1` with the locked release interpreter; test that signed installer and update on a clean Windows machine; publish verified release assets; then set `NULLCS_DESKTOP_DOWNLOAD_URL` to that exact GitHub installer and rebuild/redeploy the website. No push, release publication, or deployment was performed in this review.
