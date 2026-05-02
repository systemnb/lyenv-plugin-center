# scripts/cmd_driver.py
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log, args as rt_args
from scripts.lib.common import (
    cfg, abspath_expand, ensure_dir, ensure_file
)
from scripts.lib.gki import (
    infer_workspace, infer_source_dir, get_drivers_config,
    _integrate_one_driver
)


def _replace_in_file(filepath: str, old: str, new: str) -> bool:
    """Replace all occurrences of old with new in file. Return True if changed."""
    if not os.path.isfile(filepath):
        return False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    new_content = content.replace(old, new)
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


def cmd_add(source_dir: str, android_ver: int, arch: str):
    """Handle 'kade driver add --name <proj> [--module <ko>] [--src <external>]'"""
    args = rt_args()[1:]  # discard the first 'add'
    params = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args):
                params[key] = args[i + 1]
                i += 2
            else:
                params[key] = ""
                i += 1
        else:
            i += 1

    project = params.get("name")
    if not project:
        respond_error("Usage: kade driver add --name <project> [--module <module.ko>] [--src <external_src>]", code=2)
        return

    module_name = params.get("module", "")
    ext_src = params.get("src", "")
    in_tree = not bool(ext_src)

    drv_cfg = {
        "project_name": project,
        "module_name": module_name,
        "in_tree": in_tree,
        "in_tree_path": "",
        "external_src_dir": ext_src,
        "overwrite": True,
    }

    log(f"[driver add] Integrating driver {project} ...")
    res = _integrate_one_driver(source_dir, android_ver, arch, drv_cfg)

    # Persist to config via mutation
    current_drivers = get_drivers_config()
    if any(d.get("project_name") == project for d in current_drivers):
        log("[driver add] Driver already exists in config, skipping config write")
    else:
        current_drivers.append(drv_cfg)
        from lyenv_sdk import plugin_write_config
        plugin_write_config("gki.drivers", current_drivers)

    outputs = [
        f"project={project}",
        f"dest_dir={res['dest_dir']}",
        f"copied={res['copied']}",
    ]
    respond_ok("driver add ok", extra={"outputs": outputs})


def cmd_rename(source_dir: str, android_ver: int, arch: str):
    """Handle 'kade driver rename <old_name> <new_name>'"""
    full_args = rt_args()
    if len(full_args) < 3:
        respond_error("Usage: kade driver rename <old_project_name> <new_project_name>", code=2)
        return

    old = full_args[1]
    new = full_args[2]

    if old == new:
        respond_ok("Names identical, nothing to do")
        return

    # 1. Rename driver directory under common/drivers/
    old_dir = os.path.join(source_dir, "common", "drivers", old)
    new_dir = os.path.join(source_dir, "common", "drivers", new)
    if not os.path.isdir(old_dir):
        respond_error(f"Driver directory not found: {old_dir}", code=2)
    if os.path.exists(new_dir):
        respond_error(f"Target driver directory already exists: {new_dir}. Remove it first.", code=2)

    log(f"[driver rename] Renaming {old_dir} -> {new_dir}")
    os.rename(old_dir, new_dir)

    # 2. Update Makefile
    makefile = os.path.join(source_dir, "common", "drivers", "Makefile")
    mk_updated = _replace_in_file(makefile, f"obj-y += {old}/", f"obj-y += {new}/")

    # 3. Update legacy module list (gki_{arch}_modules)
    legacy_list = os.path.join(source_dir, "common", "android", f"gki_{arch}_modules")
    if os.path.isfile(legacy_list):
        _replace_in_file(legacy_list, f"drivers/{old}/", f"drivers/{new}/")

    # 4. Update modules.bzl
    modules_bzl = os.path.join(source_dir, "common", "modules.bzl")
    if os.path.isfile(modules_bzl):
        _replace_in_file(modules_bzl, f"drivers/{old}/", f"drivers/{new}/")

    # 5. Update config (gki.drivers list or gki.driver)
    drivers = get_drivers_config()
    changed = False
    for drv in drivers:
        if drv.get("project_name") == old:
            drv["project_name"] = new
            # If in_tree_path was auto-generated, update it too
            if drv.get("in_tree_path", "").endswith(f"/{old}"):
                drv["in_tree_path"] = drv["in_tree_path"].replace(f"/{old}", f"/{new}")
            changed = True
            break

    if changed:
        from lyenv_sdk import plugin_write_config
        plugin_write_config("gki.drivers", drivers)

    # 6. Optionally update derived (best effort)
    # (Derived will be refreshed on next prepare, but we keep consistency)
    from scripts.lib.common import set_derived
    set_derived(f"derived.gki.drivers.{new}.dest_dir", new_dir)

    outputs = [
        f"old={old}",
        f"new={new}",
        f"makefile_updated={mk_updated}",
    ]
    respond_ok(f"Renamed driver '{old}' to '{new}' successfully", extra={"outputs": outputs})

def cmd_add_non_gki(source_dir):
    """Non-GKI version of driver add."""
    a = rt_args()[1:]
    params = {}
    i = 0
    while i < len(a):
        if a[i].startswith("--"):
            key = a[i][2:]
            if i+1 < len(a):
                params[key] = a[i+1]
                i += 2
            else:
                params[key] = ""
                i += 1
        else:
            i += 1

    project = params.get("name")
    if not project:
        respond_error("Usage: kade driver add --name <project> [--module <module.ko>] [--src <external_src>] [--target obj-m]", code=2)
        return

    drv_cfg = {
        "project_name": project,
        "module_name": params.get("module", ""),
        "in_tree": not bool(params.get("src")),
        "external_src_dir": params.get("src", ""),
        "overwrite": True,
        "makefile_target": params.get("target", "obj-y"),
    }

    from scripts.lib.non_gki import _integrate_non_gki_driver
    res = _integrate_non_gki_driver(source_dir, drv_cfg)

    # Update config
    current = get_non_gki_drivers_config()
    if any(d.get("project_name") == project for d in current):
        log("[driver add] Driver already in config, skip update")
    else:
        current.append(drv_cfg)
        from lyenv_sdk import plugin_write_config
        plugin_write_config("non_gki.drivers", current)

    respond_ok("driver add ok (non_gki)", extra={"outputs": [
        f"project={project}",
        f"dest_dir={res['dest_dir']}",
    ]})

def cmd_rename_non_gki(source_dir):
    """Non-GKI version of driver rename."""
    full_args = rt_args()
    if len(full_args) < 3:
        respond_error("Usage: kade driver rename <old_name> <new_name>", code=2)
        return
    old = full_args[1]
    new = full_args[2]
    if old == new:
        respond_ok("Names identical")
        return

    # Rename directory
    old_dir = os.path.join(source_dir, "drivers", old)
    new_dir = os.path.join(source_dir, "drivers", new)
    if not os.path.isdir(old_dir):
        respond_error(f"Driver directory not found: {old_dir}", code=2)
    if os.path.exists(new_dir):
        respond_error(f"Target directory exists: {new_dir}", code=2)

    os.rename(old_dir, new_dir)

    # Update Makefile
    makefile = os.path.join(source_dir, "drivers", "Makefile")
    _replace_in_file(makefile, f"obj-y += {old}/", f"obj-y += {new}/")
    _replace_in_file(makefile, f"obj-m += {old}/", f"obj-m += {new}/")

    # Update config
    drivers = get_non_gki_drivers_config()
    changed = False
    for d in drivers:
        if d.get("project_name") == old:
            d["project_name"] = new
            changed = True
            break
    if changed:
        from lyenv_sdk import plugin_write_config
        plugin_write_config("non_gki.drivers", drivers)

    respond_ok(f"Renamed driver '{old}' to '{new}' (non_gki)", extra={
        "outputs": [f"old={old}", f"new={new}"]
    })

def main():
    read_request()
    args = rt_args()
    if len(args) < 1:
        respond_error("kade driver <add|rename> ...", code=2)
        return

    flavor = str(cfg("kernel.flavor", "")).strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("driver management only supports gki or non_gki flavors", code=2)

    if flavor == "non_gki":
        # Non-GKI mode: use non_gki source dir
        source_dir = str(cfg("derived.non_gki.source_dir", "") or "").strip()
        if not source_dir:
            respond_error("derived.non_gki.source_dir not found. Run prepare + sync first.", code=2)
        source_dir = abspath_expand(source_dir)
        # For simplicity, we don't need android_ver/arch in non-GKI integration
        if args[0] == "add":
            cmd_add_non_gki(source_dir)
        elif args[0] == "rename":
            cmd_rename_non_gki(source_dir)
    else:
        # GKI mode (original logic)
        source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
        if not source_dir:
            ws = infer_workspace()
            source_dir = infer_source_dir(ws)
        source_dir = abspath_expand(source_dir)
        android_ver = int(cfg("gki.android_version", "0"))
        arch = str(cfg("gki.target_arch", "aarch64")).strip()

        if args[0] == "add":
            cmd_add(source_dir, android_ver, arch)
        elif args[0] == "rename":
            cmd_rename(source_dir, android_ver, arch)
        else:
            respond_error(f"Unknown driver subcommand: {subcmd}", code=2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[driver] error: {e}")
        respond_error(str(e), code=3)