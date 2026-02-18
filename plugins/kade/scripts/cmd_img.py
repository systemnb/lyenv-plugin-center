# scripts/cmd_img.py
import os
import sys
import shutil
from typing import List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log, args as rt_args
from scripts.lib.common import cfg, abspath_expand, ensure_dir, ensure_file, which, run_cmd, to_int

def _plugin_root() -> str:
    # scripts/cmd_img.py -> kade root is one level up
    return abspath_expand(os.path.join(os.path.dirname(__file__), ".."))

def _tool_path(rel_or_abs: str) -> str:
    p = rel_or_abs
    if not os.path.isabs(p):
        p = os.path.join(_plugin_root(), p)
    return abspath_expand(p)

def _find_ramdisk_file(work_dir: str) -> str:
    """
    Try to locate a ramdisk file in unpacked directory.
    Common names vary, so we search for cpio/lz4 combos.
    """
    candidates = [
        "ramdisk.cpio.lz4",
        "ramdisk.lz4",
        "ramdisk.img",
        "vendor_ramdisk.cpio.lz4",
        "vendor_ramdisk.lz4",
    ]
    for name in candidates:
        p = os.path.join(work_dir, name)
        if os.path.isfile(p):
            return p

    # fallback search
    for root, _, files in os.walk(work_dir):
        for f in files:
            if f.endswith(".cpio.lz4") or f.endswith(".lz4"):
                return os.path.join(root, f)
    return ""

def extract_ramdisk_lz4_cpio(ramdisk_file: str, out_dir: str, heartbeat_sec: int) -> Tuple[str, str]:
    """
    lz4 -d ramdisk_file ramdisk.cpio
    mkdir out_dir && cd out_dir && cpio -idmv < ../ramdisk.cpio
    """
    lz4_bin = str(cfg("img.lz4_bin", "lz4") or "lz4").strip()
    cpio_bin = str(cfg("img.cpio_bin", "cpio") or "cpio").strip()

    if which(lz4_bin) is None:
        raise RuntimeError(f"lz4 not found: {lz4_bin}")
    if which(cpio_bin) is None:
        raise RuntimeError(f"cpio not found: {cpio_bin}")

    ramdisk_file = abspath_expand(ramdisk_file)
    ensure_file(ramdisk_file, "ramdisk file")

    ensure_dir(out_dir)
    cpio_path = os.path.join(os.path.dirname(out_dir), "ramdisk.cpio")

    run_cmd([lz4_bin, "-d", ramdisk_file, cpio_path], cwd=None, stage="img:lz4_decompress", heartbeat_sec=heartbeat_sec)

    # cpio extract must run in out_dir
    # Use bash -lc to support redirection
    cmd = f'{cpio_bin} -idmv < "{cpio_path}"'
    run_cmd(["bash", "-lc", cmd], cwd=out_dir, stage="img:cpio_extract", heartbeat_sec=heartbeat_sec)

    return cpio_path, out_dir

def pack_ramdisk_dir(ramdisk_dir: str, out_lz4: str, heartbeat_sec: int) -> str:
    """
    find . | cpio -o -H newc | lz4 > out_lz4
    """
    lz4_bin = str(cfg("img.lz4_bin", "lz4") or "lz4").strip()
    cpio_bin = str(cfg("img.cpio_bin", "cpio") or "cpio").strip()

    if which(lz4_bin) is None:
        raise RuntimeError(f"lz4 not found: {lz4_bin}")
    if which(cpio_bin) is None:
        raise RuntimeError(f"cpio not found: {cpio_bin}")

    ramdisk_dir = abspath_expand(ramdisk_dir)
    if not os.path.isdir(ramdisk_dir):
        raise RuntimeError(f"ramdisk_dir not found: {ramdisk_dir}")

    out_lz4 = abspath_expand(out_lz4)
    ensure_dir(os.path.dirname(out_lz4))

    cmd = f'find . | {cpio_bin} -o -H newc | {lz4_bin} > "{out_lz4}"'
    run_cmd(["bash", "-lc", cmd], cwd=ramdisk_dir, stage="img:pack_ramdisk", heartbeat_sec=heartbeat_sec)

    return out_lz4

def main():
    read_request()
    a = rt_args()
    if not a:
        respond_error("Usage: kade img <unpack|repack|extract-ramdisk|pack-ramdisk> ...", code=2)

    heartbeat = to_int(cfg("sync.heartbeat_sec", ""), 30) or 30

    sub = a[0]
    rest = a[1:]

    out_base = str(cfg("img.out_dir", "img_out") or "img_out").strip()
    workspace = str(cfg("derived.workspace", "") or "").strip()
    if not workspace:
        ws = str(cfg("env.workspace", "") or "").strip()
        home = str(cfg("env.home", "") or "").strip() or os.environ.get("LYENV_HOME", "").strip()
        workspace = ws or (os.path.join(home, "workspace") if home else "")
    if not workspace:
        respond_error("workspace not found. Run prepare first.", code=2)

    workspace = abspath_expand(workspace)
    out_base = out_base if os.path.isabs(out_base) else os.path.join(workspace, out_base)
    ensure_dir(out_base)

    unpack_py = _tool_path(str(cfg("img.tools.unpack_bootimg", "unpack_bootimg.py") or "unpack_bootimg.py"))
    repack_py = _tool_path(str(cfg("img.tools.repack_bootimg", "repack_bootimg.py") or "repack_bootimg.py"))
    mkbootimg_py = _tool_path(str(cfg("img.tools.mkbootimg", "mkbootimg.py") or "mkbootimg.py"))

    # Check tool existence only when used
    if sub == "unpack":
        if not rest:
            respond_error("Usage: kade img unpack <boot.img|vendor_boot.img|system.img> [--out DIR]", code=2)
        img = abspath_expand(rest[0])
        ensure_file(img, "image")
        out_dir = os.path.join(out_base, os.path.basename(img) + ".unpacked")

        # parse --out
        if "--out" in rest:
            idx = rest.index("--out")
            if idx + 1 < len(rest):
                out_dir = abspath_expand(rest[idx + 1])
                ensure_dir(out_dir)

        # system.img is special; we try to help but require external tools
        if os.path.basename(img).endswith("system.img"):
            # Try simg2img if available
            simg2img = str(cfg("img.simg2img_bin", "simg2img") or "simg2img").strip()
            if which(simg2img) is None:
                respond_error(
                    "system.img unpack requires external tools (e.g. simg2img + mount/7z). "
                    f"simg2img not found: {simg2img}",
                    code=2,
                )
            raw = os.path.join(out_dir, "system.raw.img")
            ensure_dir(out_dir)
            run_cmd([simg2img, img, raw], cwd=None, stage="img:simg2img", heartbeat_sec=heartbeat)
            respond_ok("img unpack ok (system)", extra={"outputs": [f"img={img}", f"out_dir={out_dir}", f"raw_img={raw}"]})
            return

        ensure_file(unpack_py, "unpack_bootimg.py")
        ensure_dir(out_dir)

        # Call your script; common signature is: unpack_bootimg.py <img> <outdir>
        run_cmd(["python3", unpack_py, img, out_dir], cwd=None, stage="img:unpack_bootimg", heartbeat_sec=heartbeat)

        # Try extract ramdisk
        ramdisk = _find_ramdisk_file(out_dir)
        if ramdisk:
            ramdisk_out = os.path.join(out_dir, "ramdisk_out")
            ensure_dir(ramdisk_out)
            try:
                cpio_path, _ = extract_ramdisk_lz4_cpio(ramdisk, ramdisk_out, heartbeat)
                respond_ok("img unpack ok", extra={"outputs": [f"img={img}", f"out_dir={out_dir}", f"ramdisk={ramdisk}", f"cpio={cpio_path}", f"ramdisk_out={ramdisk_out}"]})
                return
            except Exception as e:
                log(f"[img] ramdisk extract skipped/failed: {e}")

        respond_ok("img unpack ok", extra={"outputs": [f"img={img}", f"out_dir={out_dir}", "ramdisk_extract=skipped"]})
        return

    if sub == "extract-ramdisk":
        if not rest:
            respond_error("Usage: kade img extract-ramdisk <ramdisk.lz4> [--out DIR]", code=2)
        ramdisk = abspath_expand(rest[0])
        ensure_file(ramdisk, "ramdisk")

        out_dir = os.path.join(out_base, "ramdisk_out")
        if "--out" in rest:
            idx = rest.index("--out")
            if idx + 1 < len(rest):
                out_dir = abspath_expand(rest[idx + 1])
        ensure_dir(out_dir)

        cpio_path, _ = extract_ramdisk_lz4_cpio(ramdisk, out_dir, heartbeat)
        respond_ok("extract-ramdisk ok", extra={"outputs": [f"ramdisk={ramdisk}", f"cpio={cpio_path}", f"out_dir={out_dir}"]})
        return

    if sub == "pack-ramdisk":
        if not rest:
            respond_error("Usage: kade img pack-ramdisk <ramdisk_dir> [--out FILE.lz4]", code=2)
        ramdisk_dir = abspath_expand(rest[0])
        out_lz4 = os.path.join(out_base, "build.cpio.lz4")
        if "--out" in rest:
            idx = rest.index("--out")
            if idx + 1 < len(rest):
                out_lz4 = abspath_expand(rest[idx + 1])

        out_file = pack_ramdisk_dir(ramdisk_dir, out_lz4, heartbeat)
        respond_ok("pack-ramdisk ok", extra={"outputs": [f"ramdisk_dir={ramdisk_dir}", f"out_lz4={out_file}"]})
        return

    if sub == "repack":
        # Use repack_bootimg.py if provided; otherwise user must use mkbootimg.py manually.
        if len(rest) < 2:
            respond_error("Usage: kade img repack <orig_img> <work_dir> [--out new.img] [-- extra args...]", code=2)

        orig_img = abspath_expand(rest[0])
        work_dir = abspath_expand(rest[1])
        ensure_file(orig_img, "orig image")
        if not os.path.isdir(work_dir):
            respond_error(f"work_dir not found: {work_dir}", code=2)

        out_img = os.path.join(out_base, "repacked.img")
        extra_args: List[str] = []

        # Parse --out
        if "--out" in rest:
            idx = rest.index("--out")
            if idx + 1 < len(rest):
                out_img = abspath_expand(rest[idx + 1])

        # Parse passthrough args after "--"
        if "--" in rest:
            idx = rest.index("--")
            extra_args = rest[idx + 1 :]

        # Prefer repack tool
        if os.path.isfile(repack_py):
            cmd = ["python3", repack_py, orig_img, work_dir, out_img] + extra_args
            run_cmd(cmd, cwd=None, stage="img:repack_bootimg", heartbeat_sec=heartbeat)
            respond_ok("repack ok", extra={"outputs": [f"orig_img={orig_img}", f"work_dir={work_dir}", f"out_img={out_img}", f"tool={repack_py}"]})
            return

        # Fallback: mkbootimg requires many args; we cannot guess.
        ensure_file(mkbootimg_py, "mkbootimg.py")
        respond_error("repack_bootimg.py not found. mkbootimg.py requires device-specific args; please provide your own repack script.", code=2)

    respond_error(f"Unknown subcommand: {sub}", code=2)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[img] error: {e}")
        respond_error(str(e), code=3)

