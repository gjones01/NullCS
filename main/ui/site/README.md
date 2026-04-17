# NullCS Site

Public-facing Next.js marketing site for NullCS.

## Run locally

1. Install dependencies:

```powershell
npm install
```

2. Copy env placeholders:

```powershell
Copy-Item .env.example .env.local
```

3. Start the dev server:

```powershell
npm run dev
```

## Required environment variables

- `NEXT_PUBLIC_SITE_URL`
  Base URL for metadata and deployment.
- `NEXT_PUBLIC_GITHUB_URL`
  GitHub CTA target. Replace this first.
- `NEXT_PUBLIC_POSTHOG_KEY`
  Optional PostHog project key.
- `NEXT_PUBLIC_POSTHOG_HOST`
  Usually `https://us.i.posthog.com` unless your PostHog project uses a different region.
- `NEXT_PUBLIC_SUPABASE_URL`
  Optional for future backend wiring.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  Optional public anon key for future frontend Supabase usage.

If PostHog or Supabase env vars are missing, the site still runs and simply skips initialization.

## Deploy to Vercel

1. Import `main/ui/site` as the project root in Vercel.
2. Add the environment variables from `.env.example`.
3. Use the default commands:
   `npm install`
   `npm run build`
4. Set the production domain in `NEXT_PUBLIC_SITE_URL`.

## First files to customize

- `src/lib/site-content.ts`
  Primary copy, nav items, GitHub URL fallback, metrics, and section content.
- `src/app/page.tsx`
  Homepage section ordering.
- `src/app/about/page.tsx`
  About page structure and long-form project framing.
- `public/assets/hero-cs-bg.png`
  Main hero visual.
- `public/assets/aboutpagebg.png`
  About page background visual.
- `public/assets/UIPopUp.PNG`
  Screenshot/mockup card currently used in the product visual section.
- `public/assets/nullcs-logo-cropped.png`
  Brand mark.

## Where to change links

- GitHub link:
  `src/lib/site-content.ts`
- Future desktop download link:
  `src/components/home/desktop-soon.tsx`
- Footer links:
  `src/components/layout/site-footer.tsx`

## Supabase and PostHog scaffolding

- Supabase client helpers:
  `src/lib/supabase/client.ts`
- PostHog browser init:
  `src/lib/posthog.ts`
- Analytics provider:
  `src/components/providers.tsx`

## Notes

- The app uses a shadcn-compatible component structure without over-installing unnecessary primitives.
- The desktop app in `main/ui/web` is untouched. This site lives separately so you can deploy it without affecting the Tauri client.
