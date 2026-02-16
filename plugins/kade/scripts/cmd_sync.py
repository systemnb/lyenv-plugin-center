# scripts/cmd_sync.py
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, set_derived, abspath_expand, ensure_dir, to_int, to_bool, cpu_count, which, run_cmd, download_repo_tool
from scripts.lib.gki import infer_workspace, infer_source_dir
from scripts.lib.non_gki import sync as non_gki_sync

def gki_sync(workspace: str, heartbeat_sec: int):
    source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
    if not source_dir:
        # allow infer if prepare not run
        source_dir = infer_source_dir(workspace)
        ensure_dir(source_dir)
        set_derived("derived.gki.source_dir", source_dir)
    source_dir = abspath_expand(source_dir)

    android_ver = to_int(cfg("gki.android_version", ""), None)
    kernel_ver = str(cfg("gki.kernel_version", "") or "").strip()
    if android_ver is None or not kernel_ver:
        raise RuntimeError("gki.android_version or gki.kernel_version missing")

    manifest_url = str(cfg("gki.repo.manifest_url", "") or "").strip() or "https://android.googlesource.com/kernel/manifest"
    branch = str(cfg("gki.repo.branch", "") or "").strip()
    if not branch:
        branch = f"common-android{android_ver}-{kernel_ver}"

    jobs = to_int(cfg("gki.repo.jobs", ""), None) or cpu_count()
    init_args = str(cfg("gki.repo.init_args", "") or "").strip()
    sync_args = str(cfg("gki.repo.sync_args", "") or "").strip() or "-c --no-tags --optimized-fetch --force-sync"
    reinit = to_bool(cfg("gki.repo.reinit", "false"), False)

    ensure_dir(source_dir)

    repo_exe = which("repo")
    local_repo = os.path.join(workspace, ".lyenv", "bin", "repo")
    if not repo_exe:
        if not os.path.isfile(local_repo):
            download_repo_tool(local_repo)
        repo_exe = local_repo

    set_derived("derived.gki.repo.executable", repo_exe)
    set_derived("derived.gki.repo.branch", branch)
    set_derived("derived.gki.repo.manifest_url", manifest_url)
    set_derived("derived.gki.repo.jobs", jobs)

    repo_dir = os.path.join(source_dir, ".repo")
    need_init = reinit or (not os.path.isdir(repo_dir))
    if need_init:
        cmd = [repo_exe, "init", "-u", manifest_url, "-b", branch]
        if init_args:
            cmd += init_args.split()
        run_cmd(cmd, cwd=source_dir, stage="gki:init", heartbeat_sec=heartbeat_sec)
    else:
        log("[sync] .repo exists, skip init")

    cmd = [repo_exe, "sync", f"-j{jobs}"] + sync_args.split()
    run_cmd(cmd, cwd=source_dir, stage="gki:sync", heartbeat_sec=heartbeat_sec)

    return {"source_dir": source_dir, "manifest_url": manifest_url, "branch": branch, "jobs": jobs, "repo": repo_exe}

def main():
    read_request()

    heartbeat = to_int(cfg("sync.heartbeat_sec", ""), 30) or 30
    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    ws = infer_workspace()
    ensure_dir(ws)
    set_derived("derived.workspace", ws)

    log(f"[sync] flavor={flavor} workspace={ws} heartbeat={heartbeat}")

    if flavor == "gki":
        info = gki_sync(ws, heartbeat)
        respond_ok("sync ok (gki)", extra={"outputs": [f"{k}={v}" for k, v in info.items()]})
        return

    info = non_gki_sync(ws, heartbeat)
    respond_ok("sync ok (non_gki)", extra={"outputs": [f"{k}={v}" for k, v in info.items()]})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[sync] error: {e}")
        respond_error(str(e), code=3)
