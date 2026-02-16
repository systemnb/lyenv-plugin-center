# scripts/cmd_abi.py
import os
import sys
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log, args as rt_args
from scripts.lib.common import cfg, to_int
from scripts.lib.gki import export_abi

def read_symbols_file(path: str) -> List[str]:
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out

def main():
    read_request()
    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor != "gki":
        respond_ok("abi skipped (non_gki)", extra={"outputs": [f"flavor={flavor}", "skipped=true"]})
        return

    source_dir = str(cfg("derived.gki.source_dir", "") or "").strip()
    if not source_dir:
        respond_error("derived.gki.source_dir is empty. Run prepare + sync first.", code=2)

    arch = str(cfg("gki.target_arch", "aarch64") or "aarch64").strip()

    # IMPORTANT: plugin args come from request["args"]
    a = rt_args()
    log(f"[abi] runtime args={a}")

    mode = "append"   # append|replace
    do_sort = False
    file_path = ""
    symbols: List[str] = []

    i = 0
    while i < len(a):
        x = a[i]
        if x == "--file" and i + 1 < len(a):
            file_path = a[i + 1]
            i += 2
            continue
        if x == "--replace":
            mode = "replace"
            i += 1
            continue
        if x == "--append":
            mode = "append"
            i += 1
            continue
        if x == "--sort":
            do_sort = True
            i += 1
            continue
        symbols.append(x)
        i += 1

    if file_path:
        fp = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.isfile(fp):
            respond_error(f"symbols file not found: {fp}", code=2)
        symbols += read_symbols_file(fp)

    # If still empty, error
    if not [s for s in symbols if str(s).strip()]:
        respond_error("No ABI symbols provided. Use: kade abi sym1 sym2 ... OR kade abi --file symbols.txt", code=2)

    info = export_abi(source_dir, arch, symbols, mode=mode, do_sort=do_sort)
    outputs = [
        "flavor=gki",
        f"abi_file={info.get('abi_file','')}",
        f"replaced={info.get('replaced', False)}",
        f"added={info.get('added', 0)}",
    ]
    respond_ok("abi ok", extra={"outputs": outputs})

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[abi] error: {e}")
        respond_error(str(e), code=3)
