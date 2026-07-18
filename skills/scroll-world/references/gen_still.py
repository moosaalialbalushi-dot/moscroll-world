#!/usr/bin/env python3
"""
gen_still.py — free-provider still generator for the scroll-world skill.

Routes a scene-still prompt to Moosa's verified free image providers instead of
spending Higgsfield credits. Stills are plain PNGs handed to the video step
(`--start-image`), so the chain is indifferent to their source — this swaps the
paid `gpt_image_2` stills path for free ones. Video legs/connectors still need
Higgsfield (only Seedance/Kling frame-lock seams); this script covers stills only.

Providers (checked in this order under --provider auto):
  forge  Local Stable Diffusion WebUI Forge, CPU mode, http://127.0.0.1:7860
         Start it with Desktop\Start-SD-Forge.bat. Private/offline, but SLOW
         (~2-6 min per image) and SD1.5-class quality (dreamshaper_8).
  flux   FLUX.1-schnell via the HF router token pool (HF_IMAGE_TOKENS).
         ~5 s per image, free, up to ~1440px, much stronger prompt following.
         Default choice for real builds; forge is for private/offline work.

Token pool: env HF_IMAGE_TOKENS ("tok1,tok2") or ~/.claude/secrets/hf_image_tokens.txt.
Tokens rotate automatically on quota/auth errors.

Usage:
  python gen_still.py "PROMPT" -o scene_1.png                    # auto: flux, forge fallback
  python gen_still.py "PROMPT" -o scene_1.png --provider forge   # force local (slow)
  python gen_still.py --prompt-file still_1.txt -o scene_1.png --width 1152 --height 768
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FORGE_URL = os.environ.get("FORGE_BASE_URL", "http://127.0.0.1:7860")
FLUX_URL = "https://router.huggingface.co/together/v1/images/generations"
FLUX_MODEL = "black-forest-labs/FLUX.1-schnell"
TOKENS_FILE = Path.home() / ".claude" / "secrets" / "hf_image_tokens.txt"


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "curl/8.9", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _save_b64(b64: str, out: Path) -> Path:
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    return out


def _hf_tokens() -> list[str]:
    raw = os.environ.get("HF_IMAGE_TOKENS", "")
    if not raw and TOKENS_FILE.exists():
        raw = TOKENS_FILE.read_text().strip()
    return [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]


def forge_alive(timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(f"{FORGE_URL}/sdapi/v1/sd-models", timeout=timeout):
            return True
    except Exception:
        return False


def gen_forge(prompt: str, negative: str, width: int, height: int, out: Path,
              steps: int, timeout: float) -> Path:
    # SD1.5 checkpoints degrade past ~768px on a side; clamp and warn.
    w, h = min(width, 768), min(height, 768)
    if (w, h) != (width, height):
        print(f"[forge] clamped {width}x{height} -> {w}x{h} (SD1.5 ceiling)", file=sys.stderr)
    payload = {
        "prompt": prompt, "negative_prompt": negative,
        "width": w, "height": h, "steps": steps,
        "cfg_scale": 7.0, "sampler_name": "Euler a", "seed": -1,
        "batch_size": 1, "n_iter": 1,
    }
    t0 = time.time()
    data = _post_json(f"{FORGE_URL}/sdapi/v1/txt2img", payload, {}, timeout)
    images = data.get("images") or []
    if not images:
        raise RuntimeError(f"Forge returned no image: {str(data)[:300]}")
    print(f"[forge] generated in {time.time()-t0:.0f}s", file=sys.stderr)
    return _save_b64(images[0], out)


def gen_flux(prompt: str, width: int, height: int, out: Path, timeout: float) -> Path:
    tokens = _hf_tokens()
    if not tokens:
        raise RuntimeError(
            "No HF tokens: set HF_IMAGE_TOKENS or create ~/.claude/secrets/hf_image_tokens.txt"
        )
    last_err: Exception | None = None
    for tok in tokens:
        try:
            t0 = time.time()
            data = _post_json(
                FLUX_URL,
                {"model": FLUX_MODEL, "prompt": prompt, "width": width,
                 "height": height, "n": 1, "response_format": "b64_json"},
                {"Authorization": f"Bearer {tok}"},
                timeout,
            )
            if "data" not in data:
                raise RuntimeError(f"FLUX response without data: {str(data)[:300]}")
            print(f"[flux] generated in {time.time()-t0:.1f}s", file=sys.stderr)
            return _save_b64(data["data"][0]["b64_json"], out)
        except urllib.error.HTTPError as exc:
            # 401/402/429 → this token is dead or drained; try the next one.
            if exc.code in (401, 402, 403, 429):
                print(f"[flux] token …{tok[-6:]} rejected ({exc.code}), rotating", file=sys.stderr)
                last_err = exc
                continue
            raise
    raise RuntimeError(f"All HF tokens exhausted: {last_err}")


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a scroll-world scene still via free providers")
    p.add_argument("prompt", nargs="?", help="prompt text (or use --prompt-file)")
    p.add_argument("--prompt-file", help="read the prompt from a file")
    p.add_argument("-o", "--out", required=True, help="output PNG path")
    p.add_argument("--provider", choices=["auto", "forge", "flux"], default="auto")
    p.add_argument("-n", "--negative", default="text, letters, watermark, logo, people",
                   help="negative prompt (forge only)")
    p.add_argument("--width", type=int, default=1152, help="default 1152 (3:2 with 768)")
    p.add_argument("--height", type=int, default=768)
    p.add_argument("--steps", type=int, default=20, help="forge only")
    p.add_argument("--timeout", type=float, default=900.0)
    args = p.parse_args()

    prompt = Path(args.prompt_file).read_text().strip() if args.prompt_file else args.prompt
    if not prompt:
        p.error("a prompt or --prompt-file is required")
    out = Path(args.out)

    try:
        if args.provider == "forge":
            path = gen_forge(prompt, args.negative, args.width, args.height, out,
                             args.steps, args.timeout)
        elif args.provider == "flux":
            path = gen_flux(prompt, args.width, args.height, out, args.timeout)
        else:  # auto: flux is the workhorse; forge is the offline fallback
            try:
                path = gen_flux(prompt, args.width, args.height, out, min(args.timeout, 120))
            except Exception as exc:
                print(f"[auto] flux failed ({exc}); trying local forge", file=sys.stderr)
                if not forge_alive():
                    raise RuntimeError(
                        "flux failed and Forge is not running (Desktop\\Start-SD-Forge.bat)"
                    )
                path = gen_forge(prompt, args.negative, args.width, args.height, out,
                                 args.steps, args.timeout)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
