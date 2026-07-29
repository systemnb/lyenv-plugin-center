# scripts/lib/gki.py
# GKI kernel operations: workspace inference, driver integration, build, compile_commands, ABI export.

import os
import shutil
from typing import Any, Dict, List

from lyenv_sdk import log
from scripts.lib.common import (
    cfg, set_derived, to_int, to_bool, abspath_expand, ensure_dir, ensure_file,
    parse_list_value, cpu_count, run_cmd
)

def infer_workspace() -> str:
    """Infer workspace path from config or environment."""
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
    """Infer GKI kernel source directory."""
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
    """Check if two paths point to the same location."""
    a = abspath_expand(a)
    b = abspath_expand(b)
    try:
        return os.path.samefile(a, b)
    except Exception:
        return a == b

def ensure_line_in_file(file_path: str, line: str) -> bool:
    """Append a line to a text file if it does not already exist. Returns True if added."""
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
    """
    Insert a module path into the _COMMON_GKI_MODULES_LIST in modules.bzl in sorted order.
    Returns True if the file was modified.
    """
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
    """Copy driver source tree to destination. Returns True if copied."""
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

def integrate_driver(source_dir: str, android_ver: int, arch: str,
                     project_name: str = None,
                     module_name: str = None,
                     in_tree: bool = None,
                     in_tree_path: str = None,
                     external_src_dir: str = None,
                     overwrite: bool = None) -> Dict[str, Any]:
    """
    Integrate a single driver into the GKI kernel tree:
      - Copy driver source
      - Update drivers/Makefile
      - Update module lists (legacy or modules.bzl based on Android version)

    All parameters are optional; if None, they fall back to gki.driver config values.
    This allows calling with explicit values (for multi-project support) or without (legacy single driver).
    """
    # Resolve parameters
    _project_name = project_name if project_name is not None else str(cfg("gki.driver.project_name", "") or "").strip() or "kerneldriver"
    _module_name = module_name if module_name is not None else str(cfg("gki.driver.module_name", "") or "").strip()
    _in_tree = in_tree if in_tree is not None else to_bool(cfg("gki.driver.in_tree", "true"), True)
    _in_tree_path = in_tree_path if in_tree_path is not None else str(cfg("gki.driver.in_tree_path", "") or "").strip()
    _overwrite = overwrite if overwrite is not None else to_bool(cfg("gki.driver.overwrite", "true"), True)
    _external_src_dir = external_src_dir if external_src_dir is not None else str(cfg("gki.driver.external_src_dir", "") or "").strip()

    if not _in_tree_path:
        _in_tree_path = os.path.join("common", "drivers", _project_name)

    driver_dest_dir = abspath_expand(os.path.join(source_dir, _in_tree_path))

    if _in_tree:
        driver_src_dir = driver_dest_dir
    else:
        ext = _external_src_dir
        if not ext:
            ws = infer_workspace()
            ext = os.path.join(ws, _project_name)
        if not os.path.isabs(ext):
            ws = infer_workspace()
            ext = os.path.join(ws, ext)
        driver_src_dir = abspath_expand(ext)

    log(f"[gki] integrate project={_project_name}")
    log(f"[gki] driver_src_dir={driver_src_dir}")
    log(f"[gki] driver_dest_dir={driver_dest_dir}")

    copied = copy_driver_tree(driver_src_dir, driver_dest_dir, _overwrite)

    drivers_makefile = os.path.join(source_dir, "common", "drivers", "Makefile")
    makefile_modified = ensure_line_in_file(drivers_makefile, f"obj-y += {_project_name}/")

    module_rel = f"drivers/{_project_name}/{_module_name}" if _module_name else ""
    modules_bzl = os.path.join(source_dir, "common", "modules.bzl")
    legacy_list = os.path.join(source_dir, "common", "android", f"gki_{arch}_modules")

    list_updates: List[str] = []

    if module_rel:
        if android_ver <= 13:
            # Update legacy list
            legacy_changed = ensure_line_in_file(legacy_list, module_rel)
            list_updates.append(f"legacy_list={legacy_list} changed={legacy_changed}")

            # Also update modules.bzl if present (Android 13 needs both)
            if os.path.isfile(modules_bzl):
                bzl_changed = insert_module_into_modules_bzl(modules_bzl, module_rel)
                list_updates.append(f"modules_bzl={modules_bzl} changed={bzl_changed}")
            else:
                list_updates.append("modules_bzl missing -> skip")
        else:
            bzl_changed = insert_module_into_modules_bzl(modules_bzl, module_rel)
            list_updates.append(f"modules_bzl={modules_bzl} changed={bzl_changed}")
    else:
        list_updates.append("module_name empty -> skip list update")

    # Store derived for the project (only if called as single project for backward compat)
    # For multi-project calls, these will be overwritten; that's okay.
    set_derived("derived.gki.driver_project_name", _project_name)
    set_derived("derived.gki.driver_dest_dir", driver_dest_dir)

    return {
        "project": _project_name,
        "driver_src_dir": driver_src_dir,
        "driver_dest_dir": driver_dest_dir,
        "copied": copied,
        "drivers_makefile": drivers_makefile,
        "makefile_modified": makefile_modified,
        "module_rel": module_rel,
        "list_updates": list_updates,
    }

def integrate_all_drivers(source_dir: str, android_ver: int, arch: str) -> List[Dict[str, Any]]:
    """
    Integrate all driver projects from gki.projects (or fallback to single gki.driver).
    Returns a list of integration results, one per project.
    """
    # Import here to avoid circular dependency
    from scripts.lib.project import _get_projects
    projects = _get_projects()
    if not projects:
        raise RuntimeError("No driver projects configured. Use 'kade project add' or configure gki.driver.")

    results = []
    for proj in projects:
        log(f"[gki] integrating project: {proj['name']}")
        res = integrate_driver(
            source_dir, android_ver, arch,
            project_name=proj["name"],
            module_name=proj["module_name"],
            in_tree=proj.get("in_tree", True),
            in_tree_path=proj.get("in_tree_path", ""),
            external_src_dir=proj.get("external_src_dir", ""),
            overwrite=proj.get("overwrite", True),
        )
        results.append(res)
    return results

def ensure_kmi_strict_mode_disabled(build_config_abs: str) -> bool:
    """
    Ensure KMI_SYMBOL_LIST_STRICT_MODE=0 exists in build config.
    If key exists and is not 0, force it to 0.
    Return True if modified.
    """
    if not os.path.isfile(build_config_abs):
        raise RuntimeError(f"BUILD_CONFIG not found: {build_config_abs}")

    with open(build_config_abs, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()

    found = False
    changed = False
    out: List[str] = []

    for ln in lines:
        if ln.strip().startswith("KMI_SYMBOL_LIST_STRICT_MODE="):
            found = True
            if ln.strip() != "KMI_SYMBOL_LIST_STRICT_MODE=0":
                out.append("KMI_SYMBOL_LIST_STRICT_MODE=0")
                changed = True
            else:
                out.append(ln)
            continue
        out.append(ln)

    if not found:
        out.append("")
        out.append("KMI_SYMBOL_LIST_STRICT_MODE=0")
        changed = True

    if changed:
        with open(build_config_abs, "w", encoding="utf-8") as wf:
            wf.write("\n".join(out) + "\n")

    return changed

def build(source_dir: str, android_ver: int, kernel_ver: str, arch: str, heartbeat_sec: int) -> Dict[str, Any]:
    """
    Execute the kernel build (legacy or Bazel) and return output paths.
    """
    jobs = to_int(cfg("gki.build.jobs", ""), None) or cpu_count()

    if android_ver <= 13:
        ensure_file(os.path.join(source_dir, "build", "build.sh"), "build/build.sh")

        legacy_args = parse_list_value(cfg("gki.build.legacy_args", []))
        legacy_env = cfg("gki.build.legacy_env", {}) or {}

        build_config = legacy_env.get("BUILD_CONFIG") or f"common/build.config.gki.{arch}"
        lto = legacy_env.get("LTO") or "thin"

        build_config_abs = os.path.join(source_dir, build_config)
        modified = ensure_kmi_strict_mode_disabled(build_config_abs)
        log(f"[gki] patch BUILD_CONFIG strict mode: {build_config_abs} modified={modified}")

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

def _plugin_root() -> str:
    """Return the root directory of the kade plugin."""
    return abspath_expand(os.path.join(os.path.dirname(__file__), "..", ".."))

def export_compile_commands(source_dir: str, android_ver: int, kernel_ver: str, arch: str, heartbeat_sec: int) -> Dict[str, Any]:
    """
    Export compile_commands.json for GKI kernel.
    Android <= 13 uses a Python script; later versions use Bazel.
    """
    source_dir = abspath_expand(source_dir)

    if android_ver <= 13:
        kernel_script = os.path.join(source_dir, "common", "scripts", "clang-tools", "gen_compile_commands.py")

        fallback_rel = str(cfg("non_gki.compile_commands.fallback_script", "") or "").strip()
        if not fallback_rel:
            fallback_rel = "tools/gen_compile_commands.py"
        fallback_path = fallback_rel if os.path.isabs(fallback_rel) else os.path.join(_plugin_root(), fallback_rel)
        fallback_path = abspath_expand(fallback_path)

        if os.path.isfile(kernel_script):
            script = kernel_script
            log(f"[gki][compile_commands] using kernel script: {script}")
        else:
            ensure_file(fallback_path, "fallback gen_compile_commands.py (kade)")
            script = fallback_path
            log(f"[gki][compile_commands] kernel script missing, using fallback: {script}")

        out_dir = abspath_expand(os.path.join(source_dir, "out", f"android{android_ver}-{kernel_ver}", "common"))
        run_cmd(["python3", script, "-d", out_dir], cwd=source_dir, stage="gki:compile_commands_py", heartbeat_sec=heartbeat_sec)

        cc = ""
        for cand in [
            os.path.join(source_dir, "compile_commands.json"),
            os.path.join(source_dir, "common", "compile_commands.json"),
            os.path.join(out_dir, "compile_commands.json"),
        ]:
            if os.path.isfile(cand):
                cc = cand
                break
        return {"mode": "python", "script": script, "out_dir": out_dir, "compile_commands": cc}

    # Android > 13: Bazel mode
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
    run_cmd(cmd, cwd=source_dir, stage="gki:compile_commands_bazel", heartbeat_sec=heartbeat_sec)

    cc1 = os.path.join(source_dir, "compile_commands.json")
    cc2 = os.path.join(source_dir, "common", "compile_commands.json")
    cc = cc1 if os.path.isfile(cc1) else (cc2 if os.path.isfile(cc2) else "")
    return {"mode": "bazel", "target": target, "compile_commands": cc}

def export_abi(source_dir: str, arch: str, symbols: List[str], mode: str, do_sort: bool) -> Dict[str, Any]:
    """
    Append or replace ABI symbols in the GKI ABI list file.
    mode: 'append' or 'replace'
    do_sort: if True, sort the final symbol list.
    """
    abi_file = os.path.join(source_dir, "common", "android", f"abi_gki_{arch}")
    ensure_dir(os.path.dirname(abi_file))

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