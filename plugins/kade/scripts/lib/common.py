# scripts/lib/common.py
import os
import json
import stat
import time
import threading
import subprocess
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional, Callable

from lyenv_sdk import config_plugin, config_global, mutate, log, log_stream

def cfg(key: str, default: Any = None, scope: str = "plugin") -> Any:
    """Read config key from plugin/global scope."""
    if scope == "global":
        return config_global(key, default)
    return config_plugin(key, default)

def set_derived(key: str, value: Any) -> None:
    """Write derived values to plugin scope."""
    if isinstance(value, (dict, list)):
        mutate(key, json.dumps(value, ensure_ascii=False), scope="plugin")
    else:
        mutate(key, str(value), scope="plugin")

def to_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        s = str(v).strip()
        return int(s) if s else default
    except Exception:
        return default

def to_bool(v: Any, default: bool = False) -> bool:
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default

def abspath_expand(p: str) -> str:
    return os.path.abspath(os.path.expanduser(p))

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def ensure_file(p: str, what: str) -> None:
    if not os.path.isfile(p):
        raise RuntimeError(f"{what} not found: {p}")

def which(cmd: str) -> Optional[str]:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for p in paths:
        exe = os.path.join(p, cmd)
        if os.path.isfile(exe) and os.access(exe, os.X_OK):
            return exe
    return None

def cpu_count() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1

def parse_list_value(v: Any) -> List[str]:
    """Accept list / JSON list string / space-separated string."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(x) for x in arr if str(x).strip()]
        except Exception:
            pass
    return s.split()

class Heartbeat:
    def __init__(self, prefix: str, sec: int, extra_getter: Optional[Callable[[], str]] = None):
        self.prefix = prefix
        self.sec = int(sec) if sec else 0
        self.extra_getter = extra_getter
        self._stop = threading.Event()
        self._th = None

    def start(self):
        if self.sec <= 0:
            return
        def _loop():
            while not self._stop.wait(self.sec):
                extra = ""
                if self.extra_getter:
                    try:
                        extra = self.extra_getter() or ""
                    except Exception:
                        extra = ""
                msg = f"{self.prefix} still running... (heartbeat {self.sec}s)"
                if extra:
                    msg += f" {extra}"
                log(msg)
        self._th = threading.Thread(target=_loop, daemon=True)
        self._th.start()

    def stop(self):
        self._stop.set()
        if self._th:
            self._th.join(timeout=1.0)

def run_cmd(cmd: List[str], cwd: Optional[str], stage: str, heartbeat_sec: int) -> None:
    """Run command and stream output to lyenv log."""
    prefix = f"[{stage}]"
    log(f"{prefix} run: {' '.join(cmd)}")
    if cwd:
        log(f"{prefix} cwd: {cwd}")
    log(f"{prefix} (this may take a while, please wait...)")

    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    hb = Heartbeat(prefix, heartbeat_sec)
    hb.start()
    try:
        assert p.stdout is not None
        for line in p.stdout:
            log_stream(line.rstrip("\n"))
        rc = p.wait()
        if rc != 0:
            raise RuntimeError(f"command failed (rc={rc}): {' '.join(cmd)}")
        log(f"{prefix} done")
    finally:
        hb.stop()

# -----------------------------
# repo tool download (no sudo)
# -----------------------------
def download_repo_tool(dest_path: str) -> None:
    url = "https://storage.googleapis.com/git-repo-downloads/repo"
    ensure_dir(os.path.dirname(dest_path))
    log(f"[repo] downloading: {url} -> {dest_path}")
    urllib.request.urlretrieve(url, dest_path)
    st = os.stat(dest_path)
    os.chmod(dest_path, st.st_mode | stat.S_IEXEC)
    log("[repo] ready")

# -----------------------------
# zip extraction with heartbeat & progress + ZipSlip protection
# -----------------------------
def _safe_extract_member(zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest_dir: str) -> None:
    member_name = member.filename
    dest_path = abspath_expand(os.path.join(dest_dir, member_name))
    dest_dir_abs = abspath_expand(dest_dir)
    if not (dest_path == dest_dir_abs or dest_path.startswith(dest_dir_abs + os.sep)):
        raise RuntimeError(f"Unsafe zip entry path detected: {member_name}")
    zf.extract(member, dest_dir)

def extract_zip_with_progress(zip_path: str, dest_dir: str, heartbeat_sec: int, progress_every: int = 200) -> None:
    prefix = "[zip]"
    log(f"{prefix} extracting: {zip_path} -> {dest_dir}")
    ensure_dir(dest_dir)

    state = {"count": 0, "total": 0}
    hb = Heartbeat(prefix, heartbeat_sec, extra_getter=lambda: f"extracted {state['count']}/{state['total']}")
    hb.start()
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.infolist()
            state["total"] = len(members)
            for i, m in enumerate(members, start=1):
                _safe_extract_member(zf, m, dest_dir)
                state["count"] = i
                if progress_every > 0 and (i % progress_every == 0):
                    log(f"{prefix} progress: {i}/{state['total']}")
        log(f"{prefix} done: {state['count']}/{state['total']}")
    finally:
        hb.stop()
