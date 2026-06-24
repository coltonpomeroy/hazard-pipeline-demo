# HANDOFF — ship this repo to GitHub + Vercel

You are a coding agent running in Colton's local environment with his
authenticated CLIs. This repo is a finished static demo (a wind-gust hazard
pipeline with a MapLibre console at `index.html`). Your job is to get it onto
GitHub and live on Vercel, then report the URLs. Work top to bottom; each step
is verifiable. Stop and ask if a step fails in a way these notes don't cover.

## Preconditions (verify first, don't assume)
- `git`, `gh` (GitHub CLI, authenticated: `gh auth status`), and `vercel`
  (authenticated: `vercel whoami`) are available. If `gh` or `vercel` isn't
  installed or authed, tell Colton and stop — those need his login.
- Python 3.11+ and the deps in `requirements.txt` are only needed to *regenerate*
  data (Step 1). The committed `index.html` already works without them.

## Step 0 — Put the repo in the right place
Colton keeps his projects together in one developer folder (the same parent that
holds Free Flick Football, MotsActu, etc.). Detect that folder — list the
likely parents and pick the one containing his existing repos:
```bash
ls -d ~/Developer ~/dev ~/Projects ~/code ~/repos 2>/dev/null
```
Move the unzipped `hazard-pipeline-demo` directory into that folder if it isn't
already there, then `cd` into it. If you can't confidently identify the folder,
ask Colton for the path rather than guessing. The committed `.git` history is
already in place — don't re-init unless Colton asks.

## Step 1 — Sanity-check the build (optional but preferred)
```bash
pip install -r requirements.txt        # eccodes/rasterio wheels; skip if heavy
./run.sh
```
Confirm it prints "33 polygons" and regenerates `index.html`, `warnings.geojson`,
`hazard_preview.png` with no errors. `git status` should show no unexpected diffs
(generated `data/` is gitignored). If `pip install` fails on eccodes/rasterio,
skip this step — the committed artifacts are valid and Vercel doesn't run Python.

## Step 2 — Fix git identity + branch
The existing commits are authored as `Colton Pomeroy <me@coltonpomeroy.com>`.
Confirm that matches the GitHub account `gh` is logged into (`gh api user -q .login`).
If it doesn't, ask Colton which identity to use rather than guessing.
Rename the branch to `main` (GitHub default):
```bash
git branch -M main
```

## Step 3 — Create the GitHub repo and push
```bash
gh repo create hazard-pipeline-demo --public --source=. --remote=origin --push
```
Capture the repo URL from the output.

## Step 4 — Deploy to Vercel
Static site, no framework, no build step, output = repo root. `vercel.json` is
already present (cleanUrls + a content-type header for the GeoJSON).
```bash
vercel link --yes        # creates/links the project non-interactively
vercel --prod --yes      # production deploy
```
If prompted for settings, accept defaults: Framework = Other, Build Command =
(none), Output Directory = (root). Capture the production URL it prints.

## Step 5 — Verify the deploy
```bash
curl -sS -o /dev/null -w "%{http_code}\n" <PROD_URL>            # expect 200
curl -sS <PROD_URL>/warnings.geojson | head -c 200             # expect GeoJSON
```
The page pulls MapLibre from unpkg and basemap tiles from CARTO at runtime, so a
204/200 on the HTML is success; the map only renders in a browser with internet.

## Step 6 — Record the live URL and push
Edit `README.md`: replace `_(add your Vercel URL here once deployed)_` with the
production URL. Then:
```bash
git add README.md && git commit -m "docs: add live Vercel URL" && git push
```

## Step 7 — Report back
Output exactly:
- GitHub repo URL
- Vercel production URL
- Whether Step 1 ran clean or was skipped
- Any deviation from this brief

## Guardrails
- Do NOT modify pipeline logic or the hazard thresholds.
- Do NOT remove or soften the "synthetic data" caveats in `index.html` or
  `README.md` — the honesty is intentional.
- Do NOT commit any secret, token, or `.env`. Repo is public.
- Do NOT delete files or force-push. If something needs removing, ask.
