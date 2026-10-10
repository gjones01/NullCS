# NullCS licensing and attribution

Copyright 2026 NullCS contributors. Original NullCS source code and original project model artifacts are provided under GPL-3.0-only; see LICENSE. Third-party components remain under their own licenses. This does not relicense third-party datasets, game content, artwork, fonts, or dependencies.

## Research data

NullCS uses the CS2CD Counter-Strike 2 Cheat Detection dataset by Mille Mei Zhen Loo and Gert Lužkov, supervised by Paolo Burelli:
https://huggingface.co/datasets/CS2CD/CS2CD.Counter-Strike_2_Cheat_Detection
DOI: https://doi.org/10.57967/hf/5654
License: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/

NullCS transforms gameplay telemetry into encounter/player features and trains its own models. The authors do not endorse NullCS. Dataset labels and model outputs have limitations; the dataset card expressly notes uncertainty in negative labels. Raw datasets and demo files are not included in the desktop release.

## Game content and website assets

Counter-Strike, Counter-Strike 2, and related game artwork belong to Valve Corporation. NullCS is an independent project, not affiliated with or endorsed by Valve. Game footage is presented free of charge under Valve's video policy: https://store.steampowered.com/video_policy . User-supplied footage and existing game artwork are not offered under the source-code GPL license. Their inclusion does not grant rights to extract, relicense, or resell Valve assets.

## Bundled software

The installer includes a `resources/legal` directory containing the project license and collected third-party license texts. Python runtime/build dependencies are pinned in `main/ui/web/scripts/requirements-desktop.lock.txt`; Rust and frontend dependencies are pinned in their lockfiles. Upstream copyrights, notices, and license conditions remain applicable.

## Beta release

This community beta is unsigned by a Windows publisher certificate. Automatic updates are not configured; obtain new versions only from https://github.com/gjones01/NullCS/releases . Do not disable system security protections to install it. It is a research tool for review, not a cheating verdict or a basis for automatic bans. No warranty is provided; see LICENSE.
