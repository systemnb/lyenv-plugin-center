# -*- coding: utf-8 -*-
# start_runner.py - stdio runner for Start node (CLI args -> flow outputs)
from lyenv_sdk import read_request, respond_ok, respond_error, log
from flow_sdk import set_outputs

START_ID = "START_1771048631946_ce17"
OUT_PORTS = ["key","val"]

def main():
    try:
        req = read_request()
        args = [str(x) for x in (req.get("args") or [])]

        # Map args by port order; missing values become ""
        vals = { OUT_PORTS[i]: (args[i] if i < len(args) else "") for i in range(len(OUT_PORTS)) }

        log({ "start_args": args, "start_outputs": vals })
        set_outputs(START_ID, vals)

        # Keep empty message to reduce console noise
        respond_ok("")
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
