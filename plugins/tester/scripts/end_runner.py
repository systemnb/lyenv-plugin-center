# -*- coding: utf-8 -*-
# end_runner.py - stdio runner for End node (config -> response)
from lyenv_sdk import read_request, respond_ok, respond_error, log
from flow_sdk import load_wiring, build_inputs

END_ID = "END_1770791219397_h6sf"
IN_PORTS = ["final"]

def main():
    try:
        req = read_request()
        wiring = load_wiring("./scripts/flow_wiring.json")
        vals = build_inputs(req, wiring, END_ID, IN_PORTS)
        # Compose a human-friendly message; also log structured values
        msg = " ".join(vals).strip()
        log({ "end_inputs": dict(zip(IN_PORTS, vals)) })
        respond_ok(msg)
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
