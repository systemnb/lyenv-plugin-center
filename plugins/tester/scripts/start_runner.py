# -*- coding: utf-8 -*-
# start_runner.py - stdio runner for Start node (CLI args -> config)
from lyenv_sdk import read_request, respond_ok, respond_error
from flow_sdk import write_outputs

START_ID = "START_1770791214742_3xw4"
OUT_PORTS = ["name"]

def main():
    try:
        req = read_request()
        args = [str(x) for x in (req.get("args") or [])]
        # Map args by Start output port order
        write_outputs(START_ID, OUT_PORTS, args)
        respond_ok("ok")
    except Exception as e:
        respond_error(str(e))

if __name__ == "__main__":
    main()
