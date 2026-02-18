# scripts/cmd_export.py
import os
import sys
import time
import shutil
import glob
import tarfile
from typing import List, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, abspath_expand, ensure_dir, to_bool

def _infer_workspace() -> str:
    ws = str(cfg("derived.workspace", "") or "").strip()
    if ws:
        return abspath_expand(ws)
    ws = str(cfg("env.workspace", "") or "").strip()
    if ws:
        return abspath_expand(ws)
    home = str(cfg("env.home", "") or "").strip() or os.environ.get("LYENV_HOME", "").strip()
    if home:
        return abspath_expand(os.path.join(home, "workspace"))
    raise RuntimeError("workspace not found")

def _infer_artifact_root(flavor: str) -> str:
    if flavor == "gki":
        p = str(cfg("derived.gki.output_path_abs", "") or "").strip()
        if p:
            return abspath_expand(p)
        # fallback
        src = str(cfg("derived.gki.source_dir", "") or "").strip()
        arch = str(cfg("gki.target_arch", "aarch64") or "aarch64").strip()
        if src:
            return abspath_expand(os.path.join(src, "out", f"kernel_{arch}"))
        raise RuntimeError("gki output path not found, run build first")
    else:
        p = str(cfg("derived.build.artifacts_dir", "") or "").strip()
        if p:
            return abspath_expand(p)
        src = str(cfg("derived.non_gki.source_dir", "") or "").strip()
        if src:
            return abspath_expand(os.path.join(src, "out"))
        raise RuntimeError("non_gki source_dir not found")

def _match_files(root: str, include: List[str], exclude: List[str]) -> List[str]:
    root = abspath_expand(root)
    files: Set[str] = set()

    for pat in include:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            if os.path.isfile(p):
                files.add(abspath_expand(p))

    # exclude
    for pat in exclude:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            if os.path.isfile(p) and abspath_expand(p) in files:
                files.remove(abspath_expand(p))

    return sorted(files)

def main():
    read_request()

    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    workspace = _infer_workspace()
    artifact_root = _infer_artifact_root(flavor)

    dest_dir_cfg = str(cfg("export.dest_dir", "exports") or "exports").strip()
    if os.path.isabs(dest_dir_cfg):
        dest_dir = dest_dir_cfg
    else:
        dest_dir = os.path.join(workspace, dest_dir_cfg)

    ts_sub = to_bool(cfg("export.timestamp_subdir", "true"), True)
    if ts_sub:
        dest_dir = os.path.join(dest_dir, time.strftime("%Y%m%d-%H%M%S"))

    ensure_dir(dest_dir)

    mode = str(cfg("export.mode", "copy") or "copy").strip().lower()
    include = cfg("export.include", []) or ["**/*"]
    exclude = cfg("export.exclude", []) or []

    files = _match_files(artifact_root, include, exclude)
    if not files:
        respond_error(f"No files matched for export. artifact_root={artifact_root}", code=2)

    outputs = [
        f"flavor={flavor}",
        f"artifact_root={artifact_root}",
        f"dest_dir={dest_dir}",
        f"mode={mode}",
        f"files={len(files)}",
    ]

    if mode == "archive":
        tar_path = os.path.join(dest_dir, "artifacts.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tf:
            for f in files:
                arcname = os.path.relpath(f, artifact_root)
                tf.add(f, arcname=arcname)
        outputs.append(f"archive={tar_path}")
        respond_ok("export ok (archive)", extra={"outputs": outputs})
        return

    # copy mode: preserve relative structure
    for f in files:
        rel = os.path.relpath(f, artifact_root)
        out_path = os.path.join(dest_dir, rel)
        ensure_dir(os.path.dirname(out_path))
        shutil.copy2(f, out_path)

    respond_ok("export ok (copy)", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[export] error: {e}")
        respond_error(str(e), code=3)
