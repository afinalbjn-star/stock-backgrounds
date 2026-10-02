# HyperFrames Composition Project

## Skills — USE THESE FIRST

**Always invoke the relevant skill before writing or modifying compositions.** Skills encode framework-specific patterns (e.g., `window.__timelines` registration, `data-*` attribute semantics, shader-compatible CSS rules) that are NOT in generic web docs. Skipping them produces broken compositions.

**Doing anything with HyperFrames?** Start at `/hyperframes` — it tells you what HyperFrames can do and which skill or workflow handles your intent (make a video, TTS / BGM, prep footage, author / animate, render, install blocks), confirms your brief up front (the intent layer), and routes every "make me a…" request (a video, a deck, a composition port) to the right workflow. Read it first, especially when there's no project context to orient you. The workflows it routes to:

- `/product-launch-video` — any **website** URL or brief / script → a product launch / SaaS / promo video, or a site tour / showcase featuring the site's own captured visuals.
- `/faceless-explainer` — arbitrary text (topic / article / notes), **no URL, no website capture** → 60-90s faceless explainer.
- `/embedded-captions` — an existing talking-head video (MP4) → the same footage with captions / subtitles added (rail + embed, or pure-cinematic embed); the footage itself is untouched.
- `/talking-head-recut` — an existing talking-head / interview / podcast video (MP4) → the same footage **packaged with designed graphic overlays** (kinetic titles, lower-thirds, data callouts, pull-quotes, side panels, pip) synced to the transcript; the clip plays unchanged underneath. (Plain captions/subtitles → `/embedded-captions`.)
- `/pr-to-video` — a GitHub PR (URL / `owner/repo#N` / "this PR") → 30-90s code-change explainer (changelog / feature reveal / fix / refactor).
- `/motion-graphics` — a short (typically under 10s) design-led **motion graphic**, motion-is-the-message, no narration: kinetic type, a stat / number count-up, a chart, a logo sting, a lower-third / overlay, or an animated tweet / headline / captured-page highlight; rendered to MP4 or a transparent overlay. Longer / narrated / custom → `/general-video`.
- `/music-to-video` — a **music track** (audio file, video to pull audio from, or one generated from a mood brief) → beat-synced video (lyric / slideshow / kinetic promo). Music drives pacing; user-supplied images / videos are cut onto the same beat grid.
- `/slideshow` — a **presentation / pitch deck / interactive deck** — discrete slides, fragment reveals, branching, hotspot navigation, presenter mode. Output is a navigable deck, not a rendered video.
- `/general-video` — fallback for any other video (title card, longer brand / sizzle reel, multi-scene montage, static loop, custom composition) and the home of **companion mode** — co-create with the full HyperFrames toolbox; the original hyperframes authoring flow, any length.

**Porting an existing composition?** `/remotion-to-hyperframes` translates a Remotion (React) composition into HyperFrames HTML — a source migration, separate from the creation workflows above.

The domain skills (`/hyperframes-core`, `/hyperframes-animation`, `/hyperframes-keyframes`, `/hyperframes-creative`, `/hyperframes-cli`, `/media-use`, `/hyperframes-audio`, `/hyperframes-registry`, `/figma`) and the full capability map live inside `/hyperframes` — it is the single source of truth for which skill handles which intent.

**Changing how real footage or images look or reveal?** Load `/media-use` and read its `references/media-treatments.md` before editing, even when the request only says dark, flat, boring, retro, private, or “make the reveal cooler.” It governs how footage is treated, never whether media may be used. Use canonical media treatments and seek-safe motion; do not improvise equivalent CSS/SVG filters or overlays.

> **Tailwind v4 projects** (`hyperframes init --tailwind`): see `/hyperframes-core` → `references/tailwind.md`.

> **Skill missing or stale?** Run `npx hyperframes skills update <name>` to install/refresh
> the specific skill you need (the `/hyperframes` router does this automatically before
> entering a workflow), or bare `npx hyperframes skills update` to refresh the core set plus
> everything already installed — neither pulls the full set. Restart the agent session so
> newly installed skills load.

## Commands

```bash
npm run dev          # start the preview server (long-running — keep it alive in background)
npm run check        # lint + runtime + layout + motion + contrast (one command)
npm run render       # render to MP4
npm run publish      # publish and get a shareable link
npx hyperframes lint --verbose  # include info-level findings
npx hyperframes lint --json     # machine-readable output for CI
npx hyperframes docs <topic> # reference docs in terminal
```

> **`npm run dev` is a long-running server, not a one-shot command.** It blocks until stopped.
> In Claude Code, always run it with `run_in_background: true`. Never run it as a foreground
> command — it will time out and the server will die, breaking the browser preview.

> **Pinned CLI version.** These scripts pin an exact `hyperframes@X.Y.Z` so this project re-renders identically over time. Weeks later that pin lags fixes shipped since. To move up: `npx hyperframes@latest upgrade --project . --check` (shows the delta), then `npx hyperframes@latest upgrade --project .` to rewrite the pins. Always unpinned — the pinned script re-runs the old version against itself.

## Documentation

**For quick reference**, use the local CLI docs command (no network required):

```bash
npx hyperframes docs <topic>
```

Topics: `data-attributes`, `gsap`, `compositions`, `rendering`, `examples`, `troubleshooting`

**For full documentation**, discover pages via the machine-readable index — do NOT guess URLs:

```
https://hyperframes.heygen.com/llms.txt
```

## Project Structure

- `index.html` — main composition (root timeline)
- `compositions/` — sub-compositions referenced via `data-composition-src`
- `meta.json` — project metadata (id, name)
- `transcript.json` — whisper word-level transcript (if generated)

## Linting — ALWAYS RUN AFTER CHANGES

After creating or editing any `.html` composition, **always** run the full check before considering the task complete:

```bash
npm run check
```

Fix all errors before presenting the result. Warnings should be reviewed before rendering.

## Key Rules

1. Every timed element needs `data-start`, `data-duration`, and `data-track-index`
2. Elements with timing **MUST** have `class="clip"` — the framework uses this for visibility control
3. Timelines must be paused and registered on `window.__timelines`:
   ```js
   window.__timelines = window.__timelines || {};
   window.__timelines["composition-id"] = gsap.timeline({ paused: true });
   ```
4. Videos use `muted` with a separate `<audio>` element for the audio track
5. Sub-compositions use `data-composition-src="compositions/file.html"` to reference other HTML files
6. Only deterministic logic — no `Date.now()`, no `Math.random()`, no network fetches

---

# Blender clips

Cycles scenes live in `blender/scenes/<NNN_slug>/` and are rendered by
`.github/workflows/render-blender-loop.yml`, which is `workflow_dispatch`
**only**. The HyperFrames pipeline above is untouched by this.

```powershell
gh workflow run render-blender-loop.yml -f scene=003_pcb-ai-chip-loop
```

| file | role |
| --- | --- |
| `blender/scenes/<slug>/scene.blend` | the scene — tracked, it is the source of truth |
| `blender/scenes/<slug>/metadata.json` | delivery spec, keywords, marketplaces |
| `blender/scenes/<slug>/renders/` | gitignored output |
| `blender/scripts/ci_settings.py` | env-driven render overrides, runs before `-a` |
| `blender/scripts/encode.py` | PNG sequence into H.264 + ProRes + market sheet |
| `blender/scripts/qc_loop.py` | structural + PSNR seam gate |
| `blender/scripts/inspect_scene.py` | headless inventory, proves the loop closes |

## How the loop is guaranteed

Prove it **before** rendering, not after. Every animated value in a Blender
scene must be a driver of the form

```
sin((frame - 1) * 2*pi/720)      # at integer harmonics only
```

so frame 721 evaluates to frame 1 to within float precision.

```powershell
blender -b blender\scenes\<slug>\scene.blend -P blender\scripts\inspect_scene.py
```

It prints `LOOP CLOSES` or `LOOP DOES NOT CLOSE` together with the measured
camera and aim-target difference. If it says the latter, stop — do not spend
GPU time.

**The trap that already bit this scene once:** a particle driver of
`sin(frame * 2*pi/720 * 1.3)` looks periodic and is not. 1.3 cycles do not fit
720 frames, so it drifted 0.68 units across the wrap. Only integer harmonics
close the loop.

`qc_loop.py` is the second line of defence, on real pixels: it measures the
PSNR between the last and first frame and holds it to a 25 dB floor.

## Blender specifics

- Cycles runs CPU-only on GitHub runners; `ci_settings.py` enables auto-tiling
  and disables caustics. Do not push samples past 512 without saying so — 720
  frames is already a long job.
- `scene.render.filepath` is set by `ci_settings.py`, so never hard-code an
  output path in the `.blend`.
- Compositor glare needs a `CompositorNodeRLayers` **inside** the group. A
  `NodeGroupInput` on `scene.compositing_node_group` renders pure white — it
  receives no render result in Blender 5.x.

## Blender clip caveats

- `003_pcb-ai-chip-loop` carries visible text (an "AI" mark etched into the
  chip). It was explicitly requested and is recorded as
  `"no visible text or logo": false` in that clip's `delivery_checklist`. It
  does not satisfy the wordless-background rule above and is not a drop-in
  match for those collections.
