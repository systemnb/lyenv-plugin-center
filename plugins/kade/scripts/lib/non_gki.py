# scripts/lib/non_gki.py
import os
import shutil
from typing import Any, Dict, List, Optional

from lyenv_sdk import log
from scripts.lib.common import (
    cfg, set_derived, abspath_expand, ensure_dir, ensure_file, which,
    parse_list_value, run_cmd, extract_zip_with_progress, to_bool, to_int
)

def _list_dir_clean(path: str) -> List[str]:
    """List directory entries ignoring common junk files."""
    items = []
    for n in os.listdir(path):
        if n in {".DS_Store", "__MACOSX"}:
            continue
        items.append(n)
    return items

def postprocess_zip_root(dest_dir: str) -> str:
    """
    If dest_dir contains exactly one subdirectory and nothing else,
    either:
      - strip root (move children up) if non_gki.source.zip_strip_root=true
      - or return inner folder as source_dir if strip_root=false
    Returns final kernel root dir.
    """
    dest_dir = abspath_expand(dest_dir)
    if not os.path.isdir(dest_dir):
        return dest_dir

    items = _list_dir_clean(dest_dir)
    if len(items) != 1:
        return dest_dir

    only = os.path.join(dest_dir, items[0])
    if not os.path.isdir(only):
        return dest_dir

    strip_root = to_bool(cfg("non_gki.source.zip_strip_root", "true"), True)
    if not strip_root:
        log(f"[non_gki][zip] single root dir detected, using inner as source_dir: {only}")
        return only

    # Move contents up and remove the root dir
    log(f"[non_gki][zip] stripping single root dir: {only} -> {dest_dir}")
    for name in _list_dir_clean(only):
        shutil.move(os.path.join(only, name), os.path.join(dest_dir, name))
    shutil.rmtree(only, ignore_errors=True)
    return dest_dir

def infer_dest_dir(workspace: str) -> str:
    dest_path = str(cfg("non_gki.source.dest_path", "") or "").strip()
    if dest_path:
        if not os.path.isabs(dest_path):
            dest_path = os.path.join(workspace, dest_path)
        return abspath_expand(dest_path)
    name = str(cfg("non_gki.source.dest_dir_name", "non-gki-kernel") or "non-gki-kernel").strip()
    return abspath_expand(os.path.join(workspace, name))

def sync(workspace: str, heartbeat_sec: int) -> Dict[str, Any]:
    stype = str(cfg("non_gki.source.type", "") or "").strip()
    if stype not in ("repo", "local", "zip"):
        raise RuntimeError("non_gki.source.type must be repo|local|zip")

    dest_dir = infer_dest_dir(workspace)
    log(f"[non_gki] sync type={stype} dest_dir={dest_dir}")

    if stype == "repo":
        git = which("git")
        if not git:
            raise RuntimeError("git not found in PATH")

        url = str(cfg("non_gki.source.repo_url", "") or "").strip()
        if not url:
            raise RuntimeError("non_gki.source.repo_url is empty")
        branch = str(cfg("non_gki.source.branch", "") or "").strip()

        git_dir = os.path.join(dest_dir, ".git")
        if os.path.isdir(git_dir):
            run_cmd([git, "fetch", "--all", "--prune"], cwd=dest_dir, stage="non_gki:fetch", heartbeat_sec=heartbeat_sec)
        else:
            if os.path.exists(dest_dir) and os.path.isdir(dest_dir) and os.listdir(dest_dir):
                raise RuntimeError(f"destination exists and not empty: {dest_dir}")
            ensure_dir(os.path.dirname(dest_dir))
            clone = [git, "clone", "--progress", url, dest_dir]
            if branch:
                clone = [git, "clone", "--progress", "-b", branch, url, dest_dir]
            run_cmd(clone, cwd=None, stage="non_gki:clone", heartbeat_sec=heartbeat_sec)

        if branch:
            run_cmd([git, "checkout", branch], cwd=dest_dir, stage="non_gki:checkout", heartbeat_sec=heartbeat_sec)
            run_cmd([git, "pull", "--ff-only"], cwd=dest_dir, stage="non_gki:pull", heartbeat_sec=heartbeat_sec)
        else:
            run_cmd([git, "pull", "--ff-only"], cwd=dest_dir, stage="non_gki:pull", heartbeat_sec=heartbeat_sec)

        final_root = postprocess_zip_root(dest_dir)
        set_derived("derived.non_gki.source_dir", final_root)
        return {"type": "zip", "source_dir": final_root, "zip_path": zpath}

    if stype == "local":
        local_path = str(cfg("non_gki.source.local_path", "") or "").strip()
        if not local_path:
            raise RuntimeError("non_gki.source.local_path is empty")
        local_path = abspath_expand(local_path)
        if not os.path.isdir(local_path):
            raise RuntimeError(f"local_path not found: {local_path}")

        set_derived("derived.non_gki.source_dir", local_path)
        return {"type": "local", "source_dir": local_path}

    # zip
    zpath = str(cfg("non_gki.source.zip_path", "") or "").strip()
    if not zpath:
        raise RuntimeError("non_gki.source.zip_path is empty")
    zpath = abspath_expand(zpath)
    if not os.path.isfile(zpath):
        raise RuntimeError(f"zip not found: {zpath}")

    clean = to_bool(cfg("non_gki.source.clean_extract", "false"), False)
    if clean and os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)

    prog_every = to_int(cfg("non_gki.source.zip_progress_every", ""), 200) or 200
    extract_zip_with_progress(zpath, dest_dir, heartbeat_sec=heartbeat_sec, progress_every=prog_every)

    set_derived("derived.non_gki.source_dir", dest_dir)
    return {"type": "zip", "source_dir": dest_dir, "zip_path": zpath}

def build(heartbeat_sec: int) -> Dict[str, Any]:
    source_dir = str(cfg("derived.non_gki.source_dir", "") or "").strip()
    if not source_dir:
        raise RuntimeError("derived.non_gki.source_dir is empty. Run prepare + sync first.")
    source_dir = abspath_expand(source_dir)

    mode = str(cfg("non_gki.build.mode", "script") or "script").strip().lower()

    if mode == "script":
        script = str(cfg("non_gki.build.script", "") or "").strip()
        if not script:
            raise RuntimeError("non_gki.build.script is empty (user must provide build script).")

        script_path = script if os.path.isabs(script) else os.path.join(source_dir, script)
        ensure_file(script_path, "non-gki build script")

        args = parse_list_value(cfg("non_gki.build.args", []))

        if os.access(script_path, os.X_OK):
            cmd = [script_path] + args
        else:
            cmd = ["bash", script_path] + args

        run_cmd(cmd, cwd=source_dir, stage="non_gki:build_script", heartbeat_sec=heartbeat_sec)

        artifacts_dir = str(cfg("non_gki.build.artifacts_dir", "") or "").strip() or "out"
        artifacts_abs = artifacts_dir if os.path.isabs(artifacts_dir) else os.path.join(source_dir, artifacts_dir)
        return {"mode": "script", "source_dir": source_dir, "script": script_path, "args": args, "artifacts_dir": artifacts_abs}

    if mode == "make":
        mk = cfg("non_gki.build.make", {}) or {}
        out_dir = str(mk.get("out_dir") or "out").strip()
        defconfig = str(mk.get("defconfig") or "").strip()
        if not defconfig:
            raise RuntimeError("non_gki.build.make.defconfig is empty (e.g. vendor_defconfig).")

        # Determine jobs
        jobs = mk.get("jobs")
        jobs_i = to_int(jobs, None) or cpu_count()

        kernel_series = str(mk.get("kernel_series") or "4.9_plus").strip()

        arch = str(mk.get("arch") or "arm64").strip()
        subarch = str(mk.get("subarch") or "arm64").strip()
        cc = str(mk.get("cc") or "clang").strip()

        toolchain_prefix = str(mk.get("toolchain_path_prefix") or "").strip()
        if not toolchain_prefix:
            raise RuntimeError("non_gki.build.make.toolchain_path_prefix is empty.")

        if kernel_series == "4.4":
            cross = str(mk.get("cross_compile_44") or "aarch64-linux-android-").strip()
            cross32 = str(mk.get("cross_compile_arm32_44") or "arm-linux-androideabi-").strip()
            triple = str(mk.get("triple_44") or "aarch64-linux-android-").strip()
        else:
            cross = str(mk.get("cross_compile") or "aarch64-linux-gnu-").strip()
            cross32 = str(mk.get("cross_compile_arm32") or "arm-linux-gnueabi-").strip()
            triple = str(mk.get("triple") or "aarch64-linux-gnu-").strip()

        # Note: defconfig file lives under arch/arm64/configs/
        # We only pass the name to make, which is standard.
        export_lines = [
            f'export ARCH="{arch}"',
            f'export SUBARCH="{subarch}"',
            f'export PATH="{toolchain_prefix}:$PATH"',
            f'export CC="{cc}"',
            f'export CROSS_COMPILE="{cross}"',
            f'export CROSS_COMPILE_ARM32="{cross32}"',
            f'export TRIPLE="{triple}"',
        ]
        cmd1 = f"make O={out_dir} {defconfig}"
        cmd2 = f"make -j{jobs_i} O={out_dir}"

        # Run in kernel root
        shell_cmd = "\n".join(export_lines + [cmd1, cmd2])
        run_cmd(["bash", "-lc", shell_cmd], cwd=source_dir, stage="non_gki:make_build", heartbeat_sec=heartbeat_sec)

        artifacts_abs = os.path.join(source_dir, out_dir)
        return {"mode": "make", "source_dir": source_dir, "out_dir": artifacts_abs, "defconfig": defconfig, "jobs": jobs_i, "kernel_series": kernel_series}

    raise RuntimeError("non_gki.build.mode must be 'script' or 'make'")

def _plugin_root() -> str:
    """
    Return plugin root directory (kade project root).
    This file is: kade/scripts/lib/non_gki.py
    -> plugin root is two levels up from scripts/lib.
    """
    return abspath_expand(os.path.join(os.path.dirname(__file__), "..", ".."))

def export_compile_commands(heartbeat_sec: int) -> Dict[str, Any]:
    source_dir = str(cfg("derived.non_gki.source_dir", "") or "").strip()
    if not source_dir:
        raise RuntimeError("derived.non_gki.source_dir is empty. Run prepare + sync first.")
    source_dir = abspath_expand(source_dir)

    # Primary script location in kernel tree (may be missing on some non-GKI trees)
    kernel_script = os.path.join(source_dir, "common", "scripts", "clang-tools", "gen_compile_commands.py")

    # Fallback script shipped with kade (configurable)
    fallback_rel = str(cfg("non_gki.compile_commands.fallback_script", "") or "").strip()
    if not fallback_rel:
        # Default convention: kade/tools/gen_compile_commands.py
        fallback_rel = "tools/gen_compile_commands.py"

    fallback_path = fallback_rel
    if not os.path.isabs(fallback_path):
        fallback_path = os.path.join(_plugin_root(), fallback_rel)
    fallback_path = abspath_expand(fallback_path)

    # Decide which script to use
    if os.path.isfile(kernel_script):
        script = kernel_script
        log(f"[non_gki][compile_commands] using kernel script: {script}")
    else:
        # Use your kade-shipped script
        ensure_file(fallback_path, "fallback gen_compile_commands.py (kade)")
        script = fallback_path
        log(f"[non_gki][compile_commands] kernel script missing, using fallback: {script}")

    py = str(cfg("non_gki.compile_commands.python", "python3") or "python3").strip()

    out_dir = str(cfg("non_gki.compile_commands.out_dir", "") or "").strip()

    # Optional global override
    global_out = str(cfg("compile_commands.non_gki_out_dir", "") or "").strip()
    if global_out:
        out_dir = global_out

    if out_dir:
        if not os.path.isabs(out_dir):
            out_dir = os.path.join(source_dir, out_dir)
        out_dir = abspath_expand(out_dir)
    else:
        # Best-effort inference: out/android{A}-{K}/common if possible
        av = str(cfg("gki.android_version", "") or "").strip()
        kv = str(cfg("gki.kernel_version", "") or "").strip()
        if av and kv:
            out_dir = abspath_expand(os.path.join(source_dir, "out", f"android{av}-{kv}", "common"))
        else:
            out_dir = abspath_expand(os.path.join(source_dir, "out"))

    # Run from kernel root so relative paths behave as expected
    run_cmd([py, script, "-d", out_dir], cwd=source_dir, stage="non_gki:compile_commands", heartbeat_sec=heartbeat_sec)

    # Best-effort locate compile_commands.json
    cc = ""
    candidates = [
        os.path.join(source_dir, "compile_commands.json"),
        os.path.join(source_dir, "common", "compile_commands.json"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            cc = c
            break

    return {"source_dir": source_dir, "out_dir": out_dir, "script": script, "compile_commands": cc}

def get_non_gki_drivers_config() -> list:
    """Return non-GKI driver config list, falling back to legacy single driver if needed."""
    drivers_cfg = cfg("non_gki.drivers", None)
    if drivers_cfg and isinstance(drivers_cfg, list) and len(drivers_cfg) > 0:
        return drivers_cfg
    # Legacy single driver (if already defined by user, unlikely but for compatibility)
    single = cfg("non_gki.driver", {})
    if single and single.get("project_name"):
        return [single]
    return []


def _integrate_non_gki_driver(source_dir: str, drv_cfg: dict) -> dict:
    """
    Integrate a single driver into the non-GKI tree:
      - Copy external source to drivers/{project_name} if needed.
      - Ensure drivers/Makefile contains appropriate obj- line.
    """
    project = str(drv_cfg.get("project_name", "")).strip()
    if not project:
        raise ValueError("Driver project_name is empty")

    module_name = str(drv_cfg.get("module_name", "")).strip()
    in_tree = to_bool(drv_cfg.get("in_tree", True), True)
    overwrite = to_bool(drv_cfg.get("overwrite", True), True)
    makefile_target = str(drv_cfg.get("makefile_target", "obj-y")).strip()
    if makefile_target not in ("obj-y", "obj-m"):
        makefile_target = "obj-y"   # safe default

    drivers_subdir = os.path.join(source_dir, "drivers")
    dest_dir = os.path.join(drivers_subdir, project)

    if not in_tree:
        ext_src = str(drv_cfg.get("external_src_dir", "")).strip()
        if not ext_src:
            raise ValueError("external_src_dir required when in_tree=false")
        ext_src = abspath_expand(ext_src)
        if not os.path.isdir(ext_src):
            raise RuntimeError(f"External driver source not found: {ext_src}")

        # copy driver tree
        if overwrite and os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir)
        ensure_dir(os.path.dirname(dest_dir))
        shutil.copytree(ext_src, dest_dir)
        copied = True
    else:
        # in_tree expects source already under drivers/{project}
        if not os.path.isdir(dest_dir):
            raise RuntimeError(f"in_tree driver directory not found: {dest_dir}")
        copied = False

    # Modify drivers/Makefile
    makefile_path = os.path.join(drivers_subdir, "Makefile")
    line = f"{makefile_target} += {project}/"
    makefile_modified = ensure_line_in_file(makefile_path, line)

    return {
        "project": project,
        "dest_dir": dest_dir,
        "copied": copied,
        "makefile_modified": makefile_modified,
    }


def integrate_non_gki_drivers(source_dir: str) -> dict:
    """Integrate all non-GKI drivers into the kernel tree."""
    drivers_cfg = get_non_gki_drivers_config()
    if not drivers_cfg:
        log("[non_gki] No drivers configured, skip integration")
        return {"drivers": []}

    results = []
    for drv in drivers_cfg:
        try:
            res = _integrate_non_gki_driver(source_dir, drv)
            results.append(res)
        except Exception as e:
            log(f"[non_gki] Failed to integrate driver {drv.get('project_name','?')}: {e}")
            results.append({"error": str(e), "project": drv.get("project_name", "")})

    return {"drivers": results}