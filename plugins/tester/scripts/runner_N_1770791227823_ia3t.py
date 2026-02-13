# -*- coding: utf-8 -*-
# runner_N_1770791227823_ia3t.py - stdio runner for node "Greet"
import subprocess
import sys
from typing import List
from lyenv_sdk import read_request, log, respond_ok, respond_error
from flow_sdk import load_wiring, build_inputs, write_outputs

NODE_ID = "N_1770791227823_ia3t"
INPUT_PORTS = ["name"]
OUTPUT_PORTS = ["greeting"]
PROGRAM = sys.executable
FIXED_ARGS = ["./scripts/N_1770791227823_ia3t.py"]

def split_outputs(s: str, out_count: int) -> List[str]:
    s = (s or "").strip()
    if out_count <= 1:
        return [s]
    return s.split()

def main():
    try:
        req = read_request()
        wiring = load_wiring("./scripts/flow_wiring.json")
        argv = build_inputs(req, wiring, NODE_ID, INPUT_PORTS)

        cmd = [PROGRAM] + list(FIXED_ARGS) + argv
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            respond_error(f"node failed: {NODE_ID}: {e}")
            return

        if p.stderr:
            log(p.stderr.strip())

        if p.returncode != 0:
            msg = (p.stderr or "").strip()
            if msg:
                msg = msg[:400]
            respond_error(f"node failed: {NODE_ID}: rc={p.returncode} {msg}")
            return

        outs = split_outputs(p.stdout, len(OUTPUT_PORTS))
        write_outputs(NODE_ID, OUTPUT_PORTS, outs)
        respond_ok("ok")
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
