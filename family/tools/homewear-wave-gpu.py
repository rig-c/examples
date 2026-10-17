#!/usr/bin/env python3
"""Sequential Windows GPU runner for the remaining Family homewear characters (roa, luna, jinni, nova).

Calls the exact existing homewear-naru-upscale.py and homewear-naru-seethrough.py tools
per character so each character gets identical provenance, admission guards and layer outputs.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
from PIL import Image


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_seethrough_inputs(char_dir: pathlib.Path) -> dict:
    reg_path = char_dir / "upscale-run/registered-upscaled.png"
    reg = Image.open(reg_path).convert("RGBA")
    if reg.size != (800, 2284):
        raise RuntimeError(f"Expected 800x2284 registered-upscaled.png, got {reg.size}")

    white = Image.new("RGBA", (800, 2284), (255, 255, 255, 255))
    white.alpha_composite(reg)
    pcs_path = char_dir / "painting-clothing-source.png"
    white.convert("RGB").save(pcs_path)

    st_dir = char_dir / "seethrough-input"
    st_dir.mkdir(parents=True, exist_ok=True)
    st_full = Image.new("RGBA", (2284, 2284), (255, 255, 255, 255))
    st_full.paste(white, (742, 0))
    st_path = st_dir / "st_input_full.png"
    st_full.save(st_path)
    return {
        "paintingClothingSourceSHA256": sha256(pcs_path),
        "stInputFullSHA256": sha256(st_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=pathlib.Path, required=True)
    parser.add_argument("--comfy-root", type=pathlib.Path, default=pathlib.Path(r"C:\ComfyUI\ComfyUI"))
    parser.add_argument("--models-root", type=pathlib.Path, default=pathlib.Path(r"C:\Models"))
    parser.add_argument("--characters", nargs="*", default=["roa", "luna", "jinni", "nova"])
    args = parser.parse_args()

    work = args.work_root
    comfy = args.comfy_root
    models = args.models_root
    py = sys.executable
    upscale_script = work / "homewear-naru-upscale.py"
    seethrough_script = work / "homewear-naru-seethrough.py"
    model_path = models / "upscale_models/4x-AnimeSharp.pth"
    rmbg_cache = models / "RMBG"
    st_models = models / "SeeThrough"

    for ch in args.characters:
        t0 = time.monotonic()
        char_dir = work / "out" / ch
        char_dir.mkdir(parents=True, exist_ok=True)
        crop_path = work / "crops" / f"{ch}-source-crop.png"
        upscale_out = char_dir / "upscale-run"
        if not (upscale_out / "upscale.json").is_file():
            if upscale_out.exists():
                import shutil
                shutil.rmtree(upscale_out)
            print(f"[{ch}] Starting RMBG-2.0 + 4x-AnimeSharp upscale...", flush=True)
            subprocess.run(
                [
                    py,
                    str(upscale_script),
                    "--input",
                    str(crop_path),
                    "--out",
                    str(upscale_out),
                    "--model",
                    str(model_path),
                    "--comfy-root",
                    str(comfy),
                    "--rmbg-cache",
                    str(rmbg_cache),
                    "--target-width",
                    "800",
                    "--target-height",
                    "2284",
                ],
                check=True,
            )
        st_info = build_seethrough_inputs(char_dir)
        st_out = char_dir / "full_orig"
        if not (st_out / "meta.json").is_file():
            if st_out.exists():
                import shutil
                shutil.rmtree(st_out)
            print(f"[{ch}] Starting See-through v3 1024px 30-step decomposition...", flush=True)
            subprocess.run(
                [
                    py,
                    str(seethrough_script),
                    "--input",
                    str(char_dir / "seethrough-input/st_input_full.png"),
                    "--out",
                    str(st_out),
                    "--comfy-root",
                    str(comfy),
                    "--model-root",
                    str(st_models),
                    "--rss-limit-gib",
                    "20",
                    "--initial-bf16",
                    "--cuda-device-name",
                    "NVIDIA GeForce RTX 5070 Ti",
                ],
                check=True,
            )
            # Update prefix in layers.json to match character
            layers_path = st_out / "layers.json"
            layers_data = json.loads(layers_path.read_text(encoding="utf-8"))
            layers_data["prefix"] = f"homewear_{ch}"
            layers_path.write_text(json.dumps(layers_data, indent=2) + "\n", encoding="utf-8")

        elapsed = time.monotonic() - t0
        summary = {
            "character": ch,
            "elapsedSeconds": round(elapsed, 2),
            **st_info,
            "upscaleLogSHA256": {
                "stdout": sha256(upscale_out / "stdout.log"),
                "stderr": sha256(upscale_out / "stderr.log"),
            },
            "seethroughLogSHA256": {
                "stdout": sha256(st_out / "stdout.log"),
                "stderr": sha256(st_out / "stderr.log"),
            },
        }
        (char_dir / "gpu-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"[{ch}] DONE in {elapsed:.1f}s", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
