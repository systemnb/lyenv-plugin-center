# scripts/cmd_deps.py
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, parse_list_value, run_cmd, to_bool, to_int, which

def main():
    read_request()

    enable = to_bool(cfg("deps.enable", "true"), True)
    if not enable:
        respond_ok("deps disabled", extra={"outputs": ["skipped=true"]})
        return

    pm = str(cfg("general.package_manager", "") or "").strip() or "apt"
    if pm != "apt":
        respond_error(f"deps installer currently supports apt only. Please install dependencies manually for '{pm}'.", code=2)

    pkgs = cfg("deps.packages", [])
    if not isinstance(pkgs, list) or not pkgs:
        respond_error("deps.packages is empty.", code=2)

    use_sudo = to_bool(cfg("deps.use_sudo", "true"), True)
    sudo = "sudo" if use_sudo else ""

    # Basic sanity check
    if which("apt-get") is None:
        respond_error("apt-get not found. This deps command requires Debian/Ubuntu environment.", code=2)

    # Install
    log("[deps] apt-get update...")
    run_cmd(([sudo, "apt-get", "update"] if sudo else ["apt-get", "update"]), cwd=None, stage="deps:update", heartbeat_sec=30)

    log(f"[deps] installing {len(pkgs)} packages...")
    install_cmd = ([sudo, "apt-get", "install", "-y"] if sudo else ["apt-get", "install", "-y"]) + [str(x) for x in pkgs]
    run_cmd(install_cmd, cwd=None, stage="deps:install", heartbeat_sec=30)

    respond_ok("deps install ok", extra={"outputs": [f"package_manager=apt", f"packages={len(pkgs)}"]})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[deps] error: {e}")
        respond_error(str(e), code=3)
