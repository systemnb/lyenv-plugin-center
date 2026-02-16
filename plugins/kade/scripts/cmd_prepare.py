# scripts/cmd_prepare.py
import os
import sys

# Ensure project root is in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log
from scripts.lib.common import cfg, set_derived, abspath_expand, ensure_dir, to_int
from scripts.lib.gki import infer_workspace, infer_source_dir

def main():
    read_request()

    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor not in ("gki", "non_gki"):
        respond_error("kernel.flavor must be gki|non_gki", code=2)

    ws = infer_workspace()
    ensure_dir(ws)
    set_derived("derived.workspace", ws)
    set_derived("derived.flavor", flavor)

    outputs = [f"workspace={ws}", f"flavor={flavor}"]

    if flavor == "gki":
        av = to_int(cfg("gki.android_version", ""), None)
        kv = str(cfg("gki.kernel_version", "") or "").strip()
        if av is None or not kv:
            respond_error("Missing gki.android_version or gki.kernel_version", code=2)

        src = infer_source_dir(ws)
        ensure_dir(src)
        set_derived("derived.gki.source_dir", src)
        set_derived("derived.gki.target_arch", str(cfg("gki.target_arch", "aarch64") or "aarch64").strip())

        outputs += [f"gki_source_dir={src}", f"android={av}", f"kernel={kv}"]

    respond_ok("prepare ok", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[prepare] error: {e}")
        respond_error(str(e), code=3)
