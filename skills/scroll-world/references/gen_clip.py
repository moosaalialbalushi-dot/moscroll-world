#!/usr/bin/env python3
"""
gen_clip.py — FREE video legs/connectors for scroll-world via HF ZeroGPU Spaces.

Verified 2026-07-19: Wan 2.2 14B I2V (Lightning LoRA) frame-locks its start
image (sampled-MSE ~30 vs input still — seam-safe), so it can drive the skill's
architecture-A chain (Step 4) at zero cost:

  leg 0:  gen_clip.py leg  --image scene_0.png  --prompt "glide forward into ..."
  ffmpeg -sseof -0.15 -i leg_0.mp4 -frames:v 1 leg_0_last.png
  leg 1:  gen_clip.py leg  --image leg_0_last.png --prompt "continue gliding FORWARD ..."
  ...

Connectors (architecture B) use a first+last-frame Space (experimental).

Honest limits vs Higgsfield Seedance/Kling:
  - Output ~832x560 @ ~16fps, 3.5-5 s (Higgsfield: 1080p/24). Fine for
    draft/previz and low-cost builds; upscale later if needed.
  - ZeroGPU quota: free HF accounts get limited GPU minutes/day; jobs queue.
    Expect ~1-4 min/clip when a GPU is free. Tokens rotate on quota errors.
  - Community Spaces can go down (the mcp-tools first-last Space was in
    RUNTIME_ERROR on 2026-07-19; the dream2589632147 one worked).

Requires: pip install gradio_client   (tokens: ~/.claude/secrets/hf_image_tokens.txt)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from gradio_client import Client, handle_file

I2V_SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"          # start-image only (legs)
FLF_SPACE = "dream2589632147/Dream-wan2-2-fp8da-aoti-preview-2"  # first+last frame (connectors)
TOKENS_FILE = Path.home() / ".claude" / "secrets" / "hf_image_tokens.txt"


def _tokens() -> list[str]:
    if TOKENS_FILE.exists():
        raw = TOKENS_FILE.read_text().strip()
        return [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    return []


def _extract_video(result):
    video = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(video, dict):
        video = video.get("video") or video.get("path")
    return video


def _with_token_rotation(fn):
    last = None
    for tok in _tokens() or [None]:
        try:
            return fn(tok)
        except Exception as exc:  # quota / auth → try next token
            msg = str(exc)
            if any(k in msg.lower() for k in ("quota", "429", "401", "rate", "exceeded")):
                print(f"[gen_clip] token rejected ({msg[:80]}), rotating", file=sys.stderr)
                last = exc
                continue
            raise
    raise RuntimeError(f"all tokens failed: {last}")


def gen_leg(image: str, prompt: str, out: Path, duration: float, steps: int) -> Path:
    def run(tok):
        client = Client(I2V_SPACE, token=tok)
        result = client.predict(
            input_image=handle_file(image),
            prompt=prompt,
            duration_seconds=duration,
            steps=steps,
            randomize_seed=True,
            api_name="/generate_video",
        )
        return _extract_video(result)

    video = _with_token_rotation(run)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, out)
    return out


def gen_connector(first: str, last: str, prompt: str, out: Path, duration: float,
                  steps: int) -> Path:
    def run(tok):
        client = Client(FLF_SPACE, token=tok)
        result = client.predict(
            first_image=handle_file(first),
            last_image=handle_file(last),
            prompt=prompt,
            duration_seconds=duration,
            steps=steps,
            randomize_seed=True,
            api_name="/generate_video",
        )
        return _extract_video(result)

    video = _with_token_rotation(run)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, out)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Free scroll-world video clips via HF Spaces")
    sub = p.add_subparsers(dest="mode", required=True)

    leg = sub.add_parser("leg", help="start-image → forward-glide clip (architecture A)")
    leg.add_argument("--image", required=True, help="start image (scene still or prev leg's last frame)")
    leg.add_argument("--prompt", required=True)
    leg.add_argument("-o", "--out", required=True)
    leg.add_argument("--duration", type=float, default=3.5)
    leg.add_argument("--steps", type=int, default=6)

    conn = sub.add_parser("connector", help="first+last frame interpolation (architecture B, experimental)")
    conn.add_argument("--first", required=True, help="prev dive's ACTUAL last frame")
    conn.add_argument("--last", required=True, help="next dive's ACTUAL first frame")
    conn.add_argument("--prompt", required=True)
    conn.add_argument("-o", "--out", required=True)
    conn.add_argument("--duration", type=float, default=3.5)
    conn.add_argument("--steps", type=int, default=6)

    args = p.parse_args()
    try:
        if args.mode == "leg":
            path = gen_leg(args.image, args.prompt, Path(args.out), args.duration, args.steps)
        else:
            path = gen_connector(args.first, args.last, args.prompt, Path(args.out),
                                 args.duration, args.steps)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
