#!/usr/bin/env python3
"""Nova-only 4 CPU / aggregate 4 GiB guard for this asset authoring unit."""
import json
import os
import pathlib
import signal
import subprocess
import time
import sys

root = pathlib.Path.cwd()
if not hasattr(os, "sched_setaffinity") or not pathlib.Path("/proc").is_dir():
    raise RuntimeError("HOMEWEAR_LINUX_RESOURCE_GUARD_REQUIRED")
cpus = sorted(os.sched_getaffinity(0))[:4]
os.sched_setaffinity(0, set(cpus))
os.environ.update(UV_THREADPOOL_SIZE="4", GOMAXPROCS="4", BUN_CONFIG_MAX_HTTP_REQUESTS="4",
                  NODE_OPTIONS="--max-old-space-size=2048", OMP_NUM_THREADS="4",
                  OPENBLAS_NUM_THREADS="4", MKL_NUM_THREADS="4")
out = root.parent / "evidence/homewear-budget"
out.mkdir(parents=True, exist_ok=True)
budget = {"cpuAffinity": cpus, "rssLimitBytes": 4 * 1024 ** 3,
          "sampleSeconds": .05, "peakTreeRssBytes": 0, "commands": []}
active = None

def rss(group):
    table = {}
    for path in pathlib.Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            f = (path / "stat").read_text().rsplit(")", 1)[1].split()
            table[int(path.name)] = (int(f[1]), int(f[2]), int(f[21]) * os.sysconf("SC_PAGE_SIZE"))
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError):
            pass
    chosen = {pid for pid, (_, pgid, _) in table.items() if pgid == group} | {os.getpid()}
    while True:
        more = {pid for pid, (parent, _, _) in table.items() if parent in chosen}
        if more <= chosen:
            break
        chosen |= more
    return sum(table[pid][2] for pid in chosen if pid in table)

def stop(signum, frame):
    if active is not None and active.poll() is None:
        os.killpg(active.pid, signal.SIGKILL)
        active.wait()
    raise RuntimeError("HOMEWEAR_INTERRUPTED " + str(signum))

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def run(args, name):
    global active
    print("RUN", name, json.dumps(args), flush=True)
    peak = 0
    rejected = False
    with (out / (name + ".stdout")).open("wb") as stdout, (out / (name + ".stderr")).open("wb") as stderr:
        active = subprocess.Popen(args, stdout=stdout, stderr=stderr, start_new_session=True)
        while active.poll() is None:
            peak = max(peak, rss(active.pid))
            if peak > budget["rssLimitBytes"]:
                rejected = True
                os.killpg(active.pid, signal.SIGKILL)
                break
            time.sleep(.05)
        code = active.wait()
        active = None
    budget["commands"].append({"argv": args, "exitCode": code, "peakTreeRssBytes": peak, "guardRejected": rejected})
    budget["peakTreeRssBytes"] = max(peak, budget["peakTreeRssBytes"])
    (out / "budget.json").write_text(json.dumps(budget, indent=2) + "\n")
    if code or rejected:
        print((out / (name + ".stdout")).read_text()[-6000:], flush=True)
        print((out / (name + ".stderr")).read_text()[-6000:], flush=True)
        raise RuntimeError("HOMEWEAR_COMMAND_FAILED " + name + " exit=" + str(code))
    print("PASS", name, "peakTreeRssBytes=" + str(peak), flush=True)

tools = "family/tools/homewear-naru-runtime"
home = "family/outfits/homewear/naru"
parts = tools + "/node_modules/.bin/rig-parts"
rigc = tools + "/node_modules/.bin/rigc"
run(["bun", "install", "--cwd", tools, "--frozen-lockfile"], "install")
if "--verify-only" in sys.argv:
    verify = str(root.parent / "evidence/homewear-reproduction")
    # Preserve the serving tree's relative rig/images spelling, which is part
    # of emitted JSON identity. All writes remain in this job's own evidence.
    import shutil
    shutil.copytree(home + "/out/rig", verify + "/rig")
    run(["python3", "family/tools/homewear-naru-protected-check.py", "--require-variant"], "preservation")
    run(["bun", tools + "/compare.ts", "--selftest"], "closure-controls")
    run(["bun", "run", rigc, "build", "--rig", verify + "/rig/rig.json", "--motion", verify + "/rig/motion.json", "--images", verify + "/rig/images", "--out", verify + "/compiler/build", "--profile", "rig-play", "--pack", "--page-edges", "free", "--pack-shape", "polygon"], "build")
    run(["bun", "run", parts, "check", "--rig", verify + "/rig", "--parts", home + "/out", "--source", home + "/inputs/painting.png", "--out", verify + "/check", "--page-edges", "free", "--pack-shape", "polygon", "--seam-pairs"], "check")
    run(["bun", tools + "/compare.ts", "--recorded", home + "/out/check/build", "--compiler", verify + "/compiler/build", "--check", verify + "/check/build", "--out", verify + "/closure-comparison.json"], "closure-identity")
    run(["bun", tools + "/probe.ts", "--candidate", verify + "/check/build", "--out", verify + "/physics", "--no-render"], "live-physics")
    print("HOMEWEAR_REPRODUCTION_COMPLETE", flush=True)
    raise SystemExit(0)
if "--physics-only" in sys.argv:
    run(["bun", tools + "/probe.ts"], "live-physics")
    print("HOMEWEAR_PHYSICS_COMPLETE", flush=True)
    raise SystemExit(0)
if "--stitch-check" not in sys.argv:
    run(["bun", "run", parts, "rig", "--config", home + "/authoring/config.json", "--parts", home + "/authoring/inputs", "--out", home + "/authoring/rig", "--page-edges", "free", "--pack-shape", "polygon"], "author")
    run(["python3", "family/tools/homewear-naru-merge.py"], "merge")
run(["python3", "family/tools/homewear-naru-stitch.py"], "neck-seam-stitch")
run(["python3", "family/tools/homewear-naru-protected-check.py", "--require-variant"], "preservation")
run(["bun", "run", rigc, "build", "--rig", home + "/out/rig/rig.json", "--motion", home + "/out/rig/motion.json", "--images", home + "/out/rig/images", "--out", home + "/out/compiler/build", "--profile", "rig-play", "--pack", "--page-edges", "free", "--pack-shape", "polygon"], "build")
run(["bun", "run", parts, "check", "--rig", home + "/out/rig", "--parts", home + "/out", "--source", home + "/inputs/painting.png", "--out", home + "/out/check", "--page-edges", "free", "--pack-shape", "polygon", "--seam-pairs", "--keep-stills"], "check")
if "--stitch-check" in sys.argv or "--final-check" in sys.argv:
    run(["bun", tools + "/probe.ts"], "live-physics")
print("HOMEWEAR_BUILD_CHECK_COMPLETE", flush=True)
