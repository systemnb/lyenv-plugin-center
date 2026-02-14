# -*- coding: utf-8 -*-
# runner_N_1771048651464_n6w5.py - stdio runner for node "WriteKV" (hybrid runtime)

import subprocess
import sys
import json
from typing import List, Any, Dict, Tuple

from lyenv_sdk import read_request, log, respond_ok, respond_error, mutate, emit_artifact
from flow_sdk import load_wiring, get_inputs, set_outputs, debug_dump_io

NODE_ID = "N_1771048651464_n6w5"
INPUT_PORTS = ["key","val"]
OUTPUT_PORTS = ["key"]
PROGRAM = sys.executable
FIXED_ARGS = ["./scripts/N_1771048651464_n6w5.py"]

# ---------------------------
# Helpers
# ---------------------------

def _as_text(x: Any) -> str:
    return "" if x is None else str(x)

def _parse_outputs_from_text(stdout_text: str, out_count: int) -> List[str]:
    """
    Text output parsing strategy:
    1) If stdout is JSON array: ["a","b",...], map by index (recommended)
    2) Else if out_count == 1: return raw text
    3) Else fallback: split() tokens (last resort; unsafe for spaces)
    """
    s = (stdout_text or "").strip()
    if out_count <= 0:
        return []
    if s == "":
        return [""] * out_count

    # Try JSON array first
    try:
        obj = json.loads(s)
        if isinstance(obj, list):
            arr = [_as_text(v) for v in obj]
            if len(arr) < out_count:
                arr = arr + [""] * (out_count - len(arr))
            return arr[:out_count]
    except Exception:
        pass

    if out_count == 1:
        return [s]

    parts = s.split()
    if len(parts) < out_count:
        parts = parts + [""] * (out_count - len(parts))
    return parts[:out_count]

def _looks_like_stdio_resp(obj: Any) -> bool:
    return isinstance(obj, dict) and ("status" in obj)

def _flatten_dict(prefix: str, obj: Any, out: List[Tuple[str, Any]]) -> None:
    """
    Flatten nested dict into dotted keys:
      {"a":{"b":1}} -> ("a.b", 1)
    Lists/scalars are treated as leaf values.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            k = str(k)
            np = f"{prefix}.{k}" if prefix else k
            _flatten_dict(np, v, out)
    else:
        if prefix:
            out.append((prefix, obj))

def _merge_child_mutations(child_resp: Dict[str, Any]) -> None:
    muts = child_resp.get("mutations") or {}
    if not isinstance(muts, dict):
        return

    for scope_name in ["plugin", "global"]:
        scope_obj = muts.get(scope_name) or {}
        flat: List[Tuple[str, Any]] = []
        _flatten_dict("", scope_obj, flat)
        for k, v in flat:
            mutate(k, v, scope=scope_name)

def _merge_child_logs(child_resp: Dict[str, Any]) -> None:
    logs = child_resp.get("logs") or []
    if isinstance(logs, list):
        for x in logs:
            log(x)

def _merge_child_artifacts(child_resp: Dict[str, Any]) -> None:
    arts = child_resp.get("artifacts") or []
    if isinstance(arts, list):
        for x in arts:
            emit_artifact(x)

def _extract_child_outputs(child_resp: Dict[str, Any], out_count: int) -> List[str]:
    """
    Child outputs priority:
    1) child_resp.outputs (list) if present
    2) if out_count==1: child_resp.message
    3) fallback: empty list padded
    """
    outs = child_resp.get("outputs")
    if isinstance(outs, list):
        arr = [_as_text(v) for v in outs]
        if len(arr) < out_count:
            arr = arr + [""] * (out_count - len(arr))
        return arr[:out_count]

    if out_count == 1:
        msg = _as_text(child_resp.get("message") or "")
        return [msg]

    return [""] * out_count

def _should_pass_stdin() -> bool:
    """
    Pass req JSON to child stdin for script-like nodes.
    For most GUI code nodes, FIXED_ARGS[0] points to ./scripts/<node>.ext.
    If this returns False, child won't get stdin.
    """
    if len(FIXED_ARGS) >= 1 and isinstance(FIXED_ARGS[0], str):
        s0 = FIXED_ARGS[0]
        if s0.startswith("./scripts/") or s0.startswith("scripts/"):
            return True
    # Also pass stdin for python interpreter mode (safe)
    if PROGRAM == sys.executable:
        return True
    return False

# ---------------------------
# Main
# ---------------------------

def main():
    try:
        req = read_request()
        wiring = load_wiring("./scripts/flow_wiring.json")

        argv = get_inputs(req, wiring, NODE_ID, INPUT_PORTS, default="")
        # Great for GUI debugging: shows resolved inputs and current stored outputs (if any)
        debug_dump_io(req, wiring, NODE_ID, INPUT_PORTS, OUTPUT_PORTS)

        cmd = [PROGRAM] + list(FIXED_ARGS) + argv
        log({ "node": NODE_ID, "cmd": cmd })

        pass_stdin = _should_pass_stdin()
        req_json = json.dumps(req, ensure_ascii=False) + "\n"

        try:
            if pass_stdin:
                p = subprocess.run(cmd, input=req_json, capture_output=True, text=True)
            else:
                p = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            respond_error(f"node failed: {NODE_ID}: {e}")
            return

        # Always log stderr (truncate)
        if p.stderr:
            s = p.stderr.strip()
            if len(s) > 2000:
                s = s[:2000] + "...(truncated)"
            log({ "node": NODE_ID, "stderr": s })

        raw_out = (p.stdout or "").strip()

        # 1) Try interpret stdout as a stdio JSON response from child
        child_resp = None
        if raw_out:
            try:
                obj = json.loads(raw_out)
                if _looks_like_stdio_resp(obj):
                    child_resp = obj
            except Exception:
                child_resp = None

        if child_resp is not None:
            # If child provides stdio response, honor it
            st = str(child_resp.get("status") or "")
            if st != "ok":
                msg = _as_text(child_resp.get("message") or f"node failed: {NODE_ID}")
                respond_error(msg)
                return

            # Merge logs/artifacts/mutations from child into runner response
            _merge_child_logs(child_resp)
            _merge_child_artifacts(child_resp)
            _merge_child_mutations(child_resp)

            # Map outputs for downstream ports
            outs = _extract_child_outputs(child_resp, len(OUTPUT_PORTS))
            set_outputs(NODE_ID, dict(zip(OUTPUT_PORTS, outs)))
            log({ "node": NODE_ID, "outputs": dict(zip(OUTPUT_PORTS, outs)) })

            # keep empty message to reduce console noise
            respond_ok("")
            return

        # 2) Otherwise treat as normal process output
        if p.returncode != 0:
            # no child stdio response, fall back to returncode+stderr
            msg = (p.stderr or "").strip()
            if msg:
                msg = msg[:400]
            respond_error(f"node failed: {NODE_ID}: rc={p.returncode} {msg}")
            return

        outs = _parse_outputs_from_text(p.stdout, len(OUTPUT_PORTS))
        set_outputs(NODE_ID, dict(zip(OUTPUT_PORTS, outs)))
        log({ "node": NODE_ID, "outputs": dict(zip(OUTPUT_PORTS, outs)) })

        respond_ok("")
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
