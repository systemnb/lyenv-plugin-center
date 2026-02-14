# -*- coding: utf-8 -*-
# end_runner.py - stdio runner for End node (flow outputs -> final response)
from lyenv_sdk import read_request, respond_ok, respond_error, log
from flow_sdk import load_wiring, get_inputs

END_ID = "END_1771048634311_uprn"
IN_PORTS = ["result"]

def main():
    try:
        req = read_request()
        wiring = load_wiring("./scripts/flow_wiring.json")
        vals = get_inputs(req, wiring, END_ID, IN_PORTS, default="")

        msg = " ".join(vals).strip()
        log({ "end_inputs": dict(zip(IN_PORTS, vals)) })
        respond_ok(msg)
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
