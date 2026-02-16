# scripts/lib/gki.py
import os
import shutil
from typing import Any, Dict, List, Optional

from lyenv_sdk import log
from scripts.lib.common import (
    cfg, set_derived, to_int, to_bool, abspath_expand, ensure_dir, ensure_file,
    parse_list_value, cpu_count, run_cmd
)

def infer_workspace() -> str:
    ws = str(cfg("derived.workspace", "") or "").strip()
    if ws:
        return abspath_expand(ws)
    env_ws = str(cfg("env.workspace", "") or "").strip()
    if env_ws:
        return abspath_expand(env_ws)
    home = str(cfg("env.home", "") or "").strip() or os.environ.get("LYENV_HOME", "").strip()
    if not home:
        raise RuntimeError("env.home or env.workspace or env var LYENV_HOME is required")
    return abspath_expand(os.path.join(home, "workspace"))

def infer_source_dir(workspace: str) -> str:
    path = str(cfg("gki.source.path", "") or "").strip()
    if path:
        if not os.path.isabs(path):
            path = os.path.join(workspace, path)
        return abspath_expand(path)
    dir_name = str(cfg("gki.source.dir_name", "android-kernel") or "android-kernel").strip()
    subdir = str(cfg("gki.source.subdir", "") or "").strip()
    if subdir:
        return abspath_expand(os.path.join(workspace, subdir, dir_name))
    return abspath_expand(os.path.join(workspace, dir_name))

def _same_path(a: str, b: str) -> bool:
    a = abspath_expand(a)
    b = abspath_expand(b)
    try:
        return os.path.samefile(a, b)
    except Exception:
        return a == b

def ensure_line_in_file(file_path: str, line: str) -> bool:
    line = line.rstrip("\n")
    existing = ""
    if os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            existing = f.read()
    if line in existing:
        return False
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return True

def insert_module_into_modules_bzl(modules_bzl: str, module_path: str) -> bool:
    ensure_file(modules_bzl, "modules.bzl")
    with open(modules_bzl, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if any(f'"{module_path}"' in ln for ln in lines):
        return False

    in_list = False
    inserted = False
    modified = False
    module_line = f'    "{module_path}",\n'
    out: List[str] = []

    for ln in lines:
        out.append(ln)
        if "_COMMON_GKI_MODULES_LIST" in ln and "[" in ln:
            in_list = True
            continue
        if in_list and "]" in ln:
            if not inserted:
                out.insert(len(out) - 1, module_line)
                inserted = True
                modified = True
            in_list = False
            continue
        if in_list and not inserted:
            s = ln.strip()
            if s.startswith('"') and s.endswith('",'):
                cur = s.strip('",')
                if module_path < cur:
                    out.insert(len(out) - 1, module_line)
                    inserted = True
                    modified = True

    if modified:
        with open(modules_bzl, "w", encoding="utf-8") as f:
            f.writelines(out)
    return modified

def copy_driver_tree(src_dir: str, dest_dir: str, overwrite: bool) -> bool:
    src_dir = abspath_expand(src_dir)
    dest_dir = abspath_expand(dest_dir)

    if not os.path.isdir(src_dir):
        raise RuntimeError(f"driver src_dir not found: {src_dir}")

    if _same_path(src_dir, dest_dir):
        log(f"[gki] src_dir == dest_dir, skip copying: {src_dir}")
        return False

    if overwrite and os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)

    ensure_dir(os.path.dirname(dest_dir))
    shutil.copytree(src_dir, dest_dir)
    return True

def integrate_driver(source_dir: str, android_ver: int, arch: str) -> Dict[str, Any]:
    project = str(cfg("gki.driver.project_name", "") or "").strip() or "kerneldriver"
    module_name = str(cfg("gki.driver.module_name", "") or "").strip()

    in_tree = to_bool(cfg("gki.driver.in_tree", "true"), True)
    in_tree_path = str(cfg("gki.driver.in_tree_path", "") or "").strip()
    if not in_tree_path:
        in_tree_path = os.path.join("common", "drivers", project)

    driver_dest_dir = abspath_expand(os.path.join(source_dir, in_tree_path))

    if in_tree:
        driver_src_dir = driver_dest_dir
    else:
        ext = str(cfg("gki.driver.external_src_dir", "") or "").strip()
        if not ext:
            ws = infer_workspace()
            ext = os.path.join(ws, project)
        if not os.path.isabs(ext):
            ws = infer_workspace()
            ext = os.path.join(ws, ext)
        driver_src_dir = abspath_expand(ext)

    overwrite = to_bool(cfg("gki.driver.overwrite", "true"), True)

    log(f"[gki] integrate project={project}")
    log(f"[gki] driver_src_dir={driver_src_dir}")
    log(f"[gki] driver_dest_dir={driver_dest_dir}")

    copied = copy_driver_tree(driver_src_dir, driver_dest_dir, overwrite)

    drivers_makefile = os.path.join(source_dir, "common", "drivers", "Makefile")
    makefile_modified = ensure_line_in_file(drivers_makefile, f"obj-y += {project}/")

    module_rel = f"drivers/{project}/{module_name}" if module_name else ""
    modules_bzl = os.path.join(source_dir, "common", "modules.bzl")
    legacy_list = os.path.join(source_dir, "common", "android", f"gki_{arch}_modules")

    list_path = ""
    list_modified = False
    if module_rel:
        if android_ver > 13:
            list_path = modules_bzl
            list_modified = insert_module_into_modules_bzl(modules_bzl, module_rel)
        else:
            list_path = legacy_list
            list_modified = ensure_line_in_file(legacy_list, module_rel)

    # store useful derived
    set_derived("derived.gki.driver_project_name", project)
    set_derived("derived.gki.driver_dest_dir", driver_dest_dir)

    return {
        "project": project,
        "driver_src_dir": driver_src_dir,
        "driver_dest_dir": driver_dest_dir,
        "copied": copied,
        "drivers_makefile": drivers_makefile,
        "makefile_modified": makefile_modified,
        "module_rel": module_rel,
        "module_list_path": list_path,
        "module_list_modified": list_modified,
    }

def build(source_dir: str, android_ver: int, kernel_ver: str, arch: str, heartbeat_sec: int) -> Dict[str, Any]:
    jobs = to_int(cfg("gki.build.jobs", ""), None) or cpu_count()

    # Always build from kernel source root
    if android_ver <= 13:
        ensure_file(os.path.join(source_dir, "build", "build.sh"), "build/build.sh")

        legacy_args = parse_list_value(cfg("gki.build.legacy_args", []))
        legacy_env = cfg("gki.build.legacy_env", {}) or {}

        build_config = legacy_env.get("BUILD_CONFIG") or f"common/build.config.gki.{arch}"
        lto = legacy_env.get("LTO") or "thin"

        env_parts = [f"BUILD_CONFIG={build_config}", f"LTO={lto}"]
        for k, v in legacy_env.items():
            if k in {"BUILD_CONFIG", "LTO"}:
                continue
            env_parts.append(f"{k}={v}")

        cmd_str = " ".join(env_parts) + f" build/build.sh -j{jobs}"
        if legacy_args:
            cmd_str += " " + " ".join(legacy_args)

        run_cmd(["bash", "-lc", cmd_str], cwd=source_dir, stage="gki:build_sh", heartbeat_sec=heartbeat_sec)
        output_rel = f"out/android{android_ver}-{kernel_ver}/dist"
    else:
        bazel = os.path.join(source_dir, "tools", "bazel")
        ensure_file(bazel, "tools/bazel")
        if not os.access(bazel, os.X_OK):
            raise RuntimeError(f"tools/bazel is not executable: {bazel}")

        target = str(cfg("gki.build.bazel.dist_target", "") or "").strip()
        if not target:
            target = f"//common:kernel_{arch}_dist"

        bazel_args = parse_list_value(cfg("gki.build.bazel.args", []))
        cmd = [bazel, "run"] + bazel_args + [target]
        run_cmd(cmd, cwd=source_dir, stage="gki:bazel_dist", heartbeat_sec=heartbeat_sec)
        output_rel = f"out/kernel_{arch}"

    output_abs = os.path.join(source_dir, output_rel)
    set_derived("derived.gki.output_path_rel", output_rel)
    set_derived("derived.gki.output_path_abs", output_abs)

    return {
        "jobs": jobs,
        "output_path_rel": output_rel,
        "output_path_abs": output_abs,
    }

def export_compile_commands(source_dir: str, arch: str, heartbeat_sec: int) -> Dict[str, Any]:
    bazel = os.path.join(source_dir, "tools", "bazel")
    ensure_file(bazel, "tools/bazel")
    if not os.access(bazel, os.X_OK):
        raise RuntimeError(f"tools/bazel is not executable: {bazel}")

    target = str(cfg("gki.compile_commands.target", "") or "").strip()
    if not target:
        target = f"//common:kernel_{arch}_compile_commands"

    bazel_args = parse_list_value(cfg("gki.compile_commands.bazel_args", []))
    if not bazel_args:
        bazel_args = parse_list_value(cfg("gki.build.bazel.args", []))

    cmd = [bazel, "run"] + bazel_args + [target]
    run_cmd(cmd, cwd=source_dir, stage="gki:compile_commands", heartbeat_sec=heartbeat_sec)

    # Best-effort locate output
    cc1 = os.path.join(source_dir, "compile_commands.json")
    cc2 = os.path.join(source_dir, "common", "compile_commands.json")
    cc = cc1 if os.path.isfile(cc1) else (cc2 if os.path.isfile(cc2) else "")
    return {"target": target, "compile_commands": cc}

def export_abi(source_dir: str, arch: str, symbols: List[str], mode: str, do_sort: bool) -> Dict[str, Any]:
    abi_file = os.path.join(source_dir, "common", "android", f"abi_gki_{arch}")
    ensure_dir(os.path.dirname(abi_file))

    # normalize
    seen = set()
    sym = []
    for s in symbols:
        s = (s or "").strip()
        if not s:
            continue
        if s not in seen:
            sym.append(s)
            seen.add(s)

    if mode == "replace":
        lines = [
            "# ABI symbols list updated by kade",
        ] + (sorted(sym) if do_sort else sym)
        with open(abi_file, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")
        return {"abi_file": abi_file, "replaced": True, "added": len(sym)}

    # append / merge-sort
    if do_sort:
        existing = []
        if os.path.isfile(abi_file):
            with open(abi_file, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    t = ln.strip()
                    if t and not t.startswith("#"):
                        existing.append(t)
        merged = list(dict.fromkeys(existing + sym))
        merged_sorted = sorted(merged)
        with open(abi_file, "w", encoding="utf-8") as f:
            f.write("# ABI symbols list updated by kade\n")
            for ln in merged_sorted:
                f.write(ln + "\n")
        return {"abi_file": abi_file, "replaced": True, "added": max(0, len(merged_sorted) - len(set(existing)))}

    existing_set = set()
    if os.path.isfile(abi_file):
        with open(abi_file, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                existing_set.add(ln.strip())

    to_add = [s for s in sym if s not in existing_set]
    if to_add:
        with open(abi_file, "a", encoding="utf-8") as f:
            for s in to_add:
                f.write(s + "\n")
    return {"abi_file": abi_file, "replaced": False, "added": len(to_add)}
