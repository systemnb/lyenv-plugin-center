# scripts/cmd_clean.py
import os
import sys
import shutil
from typing import List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, to_bool, abspath_expand, ensure_dir

def _is_under(child: str, parent: str) -> bool:
    child = abspath_expand(child)
    parent = abspath_expand(parent)
    try:
        return os.path.commonpath([child, parent]) == parent
    except Exception:
        return child.startswith(parent.rstrip(os.sep) + os.sep)

def _safe_rm(path: str) -> bool:
    """Remove file/dir safely. Return True if removed."""
    if not os.path.exists(path):
        return False
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
        return True
    shutil.rmtree(path, ignore_errors=True)
    return True

def main():
    read_request()

    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    safe_only = to_bool(cfg("clean.safe_only", "true"), True)

    workspace = str(cfg("derived.workspace", "") or "").strip()
    if not workspace:
        # fallback: env.workspace or LYENV_HOME
        ws = str(cfg("env.workspace", "") or "").strip()
        home = str(cfg("env.home", "") or "").strip() or os.environ.get("LYENV_HOME", "").strip()
        if ws:
            workspace = ws
        elif home:
            workspace = os.path.join(home, "workspace")
        else:
            respond_error("workspace not found. Run prepare first.", code=2)

    workspace = abspath_expand(workspace)

    # Determine source_dir
    if flavor == "gki":
        source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
    else:
        source_dir = str(cfg("derived.non_gki.source_dir", "") or "").strip()

    if not source_dir:
        respond_error("source_dir not found in derived. Run prepare + sync first.", code=2)
    source_dir = abspath_expand(source_dir)

    # Collect delete targets
    targets: List[str] = []

    if flavor == "gki":
        rels = cfg("clean.gki_paths", []) or []
    else:
        rels = cfg("clean.non_gki_paths", []) or []

    for r in rels:
        if not r:
            continue
        targets.append(os.path.join(source_dir, str(r)))

    wrels = cfg("clean.workspace_paths", []) or []
    for r in wrels:
        if not r:
            continue
        targets.append(os.path.join(workspace, str(r)))

    removed: List[str] = []
    skipped: List[Tuple[str, str]] = []

    for t in targets:
        t = abspath_expand(t)
        if safe_only and not (_is_under(t, source_dir) or _is_under(t, workspace)):
            skipped.append((t, "not under workspace/source_dir"))
            continue
        if _safe_rm(t):
            removed.append(t)

    outputs = [
        f"flavor={flavor}",
        f"workspace={workspace}",
        f"source_dir={source_dir}",
        f"removed={len(removed)}",
        f"skipped={len(skipped)}",
    ]
    for p in removed[:50]:
        outputs.append(f"removed_path={p}")
    for p, reason in skipped[:20]:
        outputs.append(f"skipped_path={p} reason={reason}")

    respond_ok("clean ok", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[clean] error: {e}")
        respond_error(str(e), code=3)
