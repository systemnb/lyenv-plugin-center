# scripts/cmd_compile_commands.py
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, to_int
from scripts.lib.gki import infer_workspace, infer_source_dir, export_compile_commands
from scripts.lib.non_gki import export_compile_commands as non_gki_compile_commands

def main():
    read_request()
    heartbeat = to_int(cfg("sync.heartbeat_sec", ""), 30) or 30
    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    if flavor == "gki":
        source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
        if not source_dir:
            ws = infer_workspace()
            source_dir = infer_source_dir(ws)
        arch = str(cfg("gki.target_arch", "aarch64") or "aarch64").strip()
        info = export_compile_commands(source_dir, arch, heartbeat)
        outputs = [
            f"flavor=gki",
            f"source_dir={source_dir}",
            f"target={info.get('target','')}",
            f"compile_commands={info.get('compile_commands','')}",
        ]
        respond_ok("compile_commands ok (gki)", extra={"outputs": outputs})
        return

    info = non_gki_compile_commands(heartbeat)
    outputs = [
        "flavor=non_gki",
        f"source_dir={info.get('source_dir','')}",
        f"out_dir={info.get('out_dir','')}",
        f"compile_commands={info.get('compile_commands','')}",
    ]
    respond_ok("compile_commands ok (non_gki)", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[compile_commands] error: {e}")
        respond_error(str(e), code=3)
