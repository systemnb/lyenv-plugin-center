# scripts/cmd_abi_upstream.py
import os
import sys
import time
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, abspath_expand, ensure_file, to_bool


def backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = path + f".bak.{ts}"
    with open(path, "rb") as fsrc, open(bak, "wb") as fdst:
        fdst.write(fsrc.read())
    return bak


def comment_out_all_lines(path: str) -> int:
    """
    Comment out all non-empty, non-comment lines by prefixing '#'.
    Keep original alignment and text.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    changed = 0
    out = []
    for ln in lines:
        if ln.strip() == "":
            out.append(ln)
            continue
        if ln.lstrip().startswith("#"):
            out.append(ln)
            continue
        out.append("#" + ln)
        changed += 1

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out)
    return changed


def patch_strict_mode_false(path: str) -> int:
    """
    Patch kmi_symbol_list_strict_mode to False in common/BUILD.bazel.

    Supports these patterns:
      - kmi_symbol_list_strict_mode = True
      - kmi_symbol_list_strict_mode: True
      - "kmi_symbol_list_strict_mode": True
    Also handles True/true.

    Returns number of replacements.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Match:
    #   optional quotes around key
    #   key name
    #   separator '=' or ':'
    #   value True/true
    #
    # Keep the left side unchanged and replace only the value with False.
    pattern = r'((?:"\s*)?kmi_symbol_list_strict_mode(?:\s*"\s*)?\s*[:=]\s*)(True|true)\b'
    new_text, n = re.subn(pattern, r"\1False", text)

    if n:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

    return n


def verify_strict_mode_disabled(path: str) -> None:
    """
    Verify there is no 'kmi_symbol_list_strict_mode' set to True after patching.
    Raise error if still found.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Detect any remaining True assignment (covers ':' and '=' and optional quotes)
    bad = re.search(r'(?:"\s*)?kmi_symbol_list_strict_mode(?:\s*"\s*)?\s*[:=]\s*(True|true)\b', text)
    if bad:
        raise RuntimeError("kmi_symbol_list_strict_mode is still True after patching (pattern mismatch or file changed).")


def main():
    read_request()

    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor != "gki":
        respond_ok("abi_upstream skipped (non_gki)", extra={"outputs": [f"flavor={flavor}", "skipped=true"]})
        return

    source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
    if not source_dir:
        respond_error("derived.gki.source_dir is empty. Run prepare + sync first.", code=2)
    source_dir = abspath_expand(source_dir)

    deny_rel = str(cfg("abi_upstream.symbols_deny_path", "build/kernel/abi/symbols.deny") or "").strip()
    bazel_rel = str(cfg("abi_upstream.build_bazel_path", "common/BUILD.bazel") or "").strip()
    backup = to_bool(cfg("abi_upstream.backup", "true"), True)

    deny_path = abspath_expand(os.path.join(source_dir, deny_rel))
    bazel_path = abspath_expand(os.path.join(source_dir, bazel_rel))

    ensure_file(deny_path, "symbols.deny")
    ensure_file(bazel_path, "common/BUILD.bazel")

    outputs = [f"source_dir={source_dir}", f"deny_path={deny_path}", f"bazel_path={bazel_path}"]

    if backup:
        deny_bak = backup_file(deny_path)
        bazel_bak = backup_file(bazel_path)
        outputs += [f"deny_backup={deny_bak}", f"bazel_backup={bazel_bak}"]

    changed_deny = comment_out_all_lines(deny_path)
    changed_bazel = patch_strict_mode_false(bazel_path)

    # Verify patch actually worked
    try:
        verify_strict_mode_disabled(bazel_path)
        outputs.append("strict_mode_verify=ok")
    except Exception as e:
        # Fail fast (better than silent success)
        respond_error(f"abi_upstream failed: {e}", code=2, extra={"outputs": outputs})

    outputs += [
        f"deny_commented_lines={changed_deny}",
        f"strict_mode_replacements={changed_bazel}",
    ]

    respond_ok("abi_upstream ok", extra={"outputs": outputs})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[abi_upstream] error: {e}")
        respond_error(str(e), code=3)
