# scripts/cmd_build.py
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, to_int
from scripts.lib.gki import infer_workspace, infer_source_dir, integrate_drivers, build as gki_build
from scripts.lib.non_gki import build as non_gki_build
from scripts.lib.non_gki import integrate_non_gki_drivers

def main():
    read_request()
    heartbeat = to_int(cfg("sync.heartbeat_sec", ""), 30) or 30
    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    if flavor == "non_gki":
        # Integrate all configured drivers before building
        prep = integrate_non_gki_drivers(source_dir)  # source_dir 需已定义
        info = non_gki_build(heartbeat)
        outputs = [f"{k}={v}" for k, v in info.items()]
        outputs.append(f"num_drivers={len(prep.get('drivers',[]))}")
        respond_ok("build ok (non_gki)", extra={"outputs": outputs})
        return

    # GKI
    source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
    if not source_dir:
        ws = infer_workspace()
        source_dir = infer_source_dir(ws)

    android_ver = to_int(cfg("gki.android_version", ""), None)
    kernel_ver = str(cfg("gki.kernel_version", "") or "").strip()
    if android_ver is None or not kernel_ver:
        respond_error("Missing gki.android_version or gki.kernel_version", code=2)

    arch = str(cfg("gki.target_arch", "aarch64") or "aarch64").strip()

    # Pre-steps: integrate driver + update module lists
    prep = integrate_drivers(source_dir, android_ver, arch)

    # Build
    binfo = gki_build(source_dir, android_ver, kernel_ver, arch, heartbeat)

    outputs = [
        "flavor=gki",
        f"source_dir={source_dir}",
        f"android_version={android_ver}",
        f"kernel_version={kernel_ver}",
        f"arch={arch}",
        f"output_path_abs={binfo.get('output_path_abs','')}",
        f"output_path_rel={binfo.get('output_path_rel','')}",
        f"driver_project={prep.get('project','')}",
        f"driver_dest_dir={prep.get('driver_dest_dir','')}",
        f"driver_copied={prep.get('copied','')}",
        f"module_rel={prep.get('module_rel','')}",
        f"module_list_path={prep.get('module_list_path','')}",
        f"module_list_modified={prep.get('module_list_modified','')}",
    ]

    for d in prep.get("drivers", []):
        outputs.append(f"driver:{d.get('project','?')}={d.get('dest_dir','?')}")

    respond_ok("build ok (gki)", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[build] error: {e}")
        respond_error(str(e), code=3)
