# Free stills providers (Moosa's stack) — overrides Step 2's paid path

The scene stills are plain PNGs handed to the video chain via `--start-image`
(SKILL.md Step 1.6: "the video chain is indifferent to their source"). So the
stills can come from any generator. This file wires Moosa's verified free
providers in place of Higgsfield `gpt_image_2` (~15 credits/still) and the
Codex CLI (not installed here).

**Video now has a free draft-tier path too** (verified 2026-07-19): Wan 2.2 14B
I2V on HF ZeroGPU Spaces frame-locks its start image (first-frame MSE ~30 vs
input; chained-leg seam MSE ~54 — both crossfade-erasable), so it can drive the
full architecture-A chain via `references/gen_clip.py`. Quality is ~832×560 /
~16 fps / 3.5 s clips vs Higgsfield's 1080p/24 — treat it as the free
**draft/previz tier** (like `seedance_2_0_mini` but $0): approve the whole
journey free, then re-render final legs on Higgsfield credits if wanted.

## Provider roster (verified 2026-07-19)

| Priority | Provider | Speed | Quality | Cost | Status |
|---|---|---|---|---|---|
| 1 (default) | **FLUX.1-schnell** — HF router token pool | ~5 s | strong, up to ~1440px | free | ✅ live-tested |
| 2 (offline/private) | **Local SD Forge** — CPU, `127.0.0.1:7860`, dreamshaper_8 | 2–6 min | SD1.5-class, ≤768px | free | ✅ installed, launch via `Desktop\Start-SD-Forge.bat` |
| 3 | Higgsfield `generate_image` (MCP connector or CLI) | ~3–8 min | best (GPT Image 2) | credits | ⛔ 0 credits, free plan (checked 2026-07-19) |
| — | Server fallbacks: Leonardo (`LEONARDO_AI_KEY`), Baidu ERNIE (`erine-image` skill), Pexels (stock only) | — | — | free-tier | untested / stock-photo only |

## How to generate a still

Use `references/gen_still.py` (stdlib-only, no deps):

```bash
# default: FLUX (fast), falls back to local Forge if FLUX is down
python references/gen_still.py --prompt-file still_1.txt -o scene_1.png --width 1152 --height 768

# force the local private generator (slow — batch overnight)
python references/gen_still.py --prompt-file still_1.txt -o scene_1.png --provider forge
```

- 1152×768 is exactly 3:2 — the skill's still aspect. FLUX also takes 1440×960.
- Tokens: `~/.claude/secrets/hf_image_tokens.txt` (2-token pool, auto-rotates on
  401/402/429). Same values as `HF_IMAGE_TOKENS` in the server `~/.hermes/.env`.
  **Never commit tokens to this repo.**
- Forge must be running for the forge path: `Desktop\Start-SD-Forge.bat`
  (also brings up the reverse tunnel so the server's Open WebUI reaches it).
  If the .bat fails silently (observed 2026-07-19 when auto-launched), start it
  directly — verified working:
  `cd repos\stable-diffusion-webui-forge && venv\Scripts\python.exe launch.py --api --listen --use-cpu all --precision full --no-half --skip-torch-cuda-test --always-cpu`
  (~64 s per 448×320 @ 8 steps once warm.)
- Keep **one provider for all N stills of a build** — same rule as Step 2's
  "one source for all stills": mixing FLUX and SD1.5 renders reads as style drift.
- FLUX has no negative-prompt input — put "no text, no letters, no logos, plain
  solid background, soft contact shadow" inside the prompt itself (the Step 2
  prompt shape already does this).

## Free video (draft tier) — `gen_clip.py`

Needs `pip install gradio_client` + the same HF token pool. Verified spaces:
`zerogpu-aoti/wan2-2-fp8da-aoti-faster` (start-image legs — architecture A) and
`dream2589632147/Dream-wan2-2-fp8da-aoti-preview-2` (first+last frame —
connectors, experimental; the mcp-tools first-last Space was RUNTIME_ERROR).

```bash
# leg 0 from the scene still, then chain from ACTUAL last frames (Step 4 A rule)
python references/gen_clip.py leg --image scene_0.png --prompt "glide forward into ..." -o leg_0.mp4
ffmpeg -sseof -0.15 -i leg_0.mp4 -frames:v 1 leg_0_last.png
python references/gen_clip.py leg --image leg_0_last.png --prompt "continue gliding FORWARD ..." -o leg_1.mp4
```

ZeroGPU quota limits apply (free account, minutes/day; jobs queue ~1–4 min).
Claude.ai's HF connector has `gradio=none` so Space invocation from claude.ai
is disabled — call the Spaces from this machine via gradio_client as above
(or enable gradio spaces at huggingface.co/settings/mcp).

## Stills-first workflow (0-credit mode)

1. Run the interview (Step 1) as normal; at the budget step (1.6) state that
   stills are free via FLUX and only the 2N−1 videos cost Higgsfield credits.
2. Generate ALL stills with `gen_still.py` — free, seconds each. Review for
   cohesion, re-roll off-style scenes (free re-rolls!), knock out backgrounds
   (Step 3) as usual.
3. Stop before Step 4 if there are no Higgsfield credits. The approved stills
   are the storyboard; page can ship temporarily as a stills-only scroll page.
4. When credits arrive, resume at Step 4 unchanged — `--start-image scene_i.png`
   works identically with FLUX/Forge PNGs.
