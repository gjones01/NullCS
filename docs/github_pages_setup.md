# GitHub Pages Setup

Use this repo's `docs/` folder as the publishing source.

## Recommended Settings

On GitHub:

1. Open the repository.
2. Click `Settings`.
3. In the left sidebar, click `Pages`.
4. Under `Build and deployment`, set `Source` to `Deploy from a branch`.
5. Set the branch to `main`.
6. Set the folder to `/docs`.
7. Save.

After GitHub finishes publishing, the site should be available at a URL shaped like:

`https://<your-github-username>.github.io/<repo-name>/`

## Main Files

- `docs/index.md`
  Main landing page for the project site.
- `docs/_config.yml`
  Minimal Jekyll / GitHub Pages configuration.
- `docs/assets/`
  Existing images and plots used by the site.

## Suggested Next Edits

Replace the placeholder sections in `docs/index.md`:

- `Why I Built This`
- `Personal Framing`
- `What I Learned`

Then decide whether you want to:

- keep the page simple and personal
- add more benchmark images
- add a separate page just for your project story
