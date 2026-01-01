#!/usr/bin/env python3
# Read request JSON from stdin and output response JSON with mutations.

import sys, json, time

def main():
    req = json.load(sys.stdin)
    logs = []
    logs.append("stdio: hello from tester!!!")
    logs.append("stdio: merge_strategy=" + str(req.get("merge_strategy")))
    logs.append("stdio: action=" + str(req.get("action")))

    # Build plugin mutations (increment build_count in local config)
    plugin_cfg = req.get("config", {}).get("plugin", {})
    build_count = int(plugin_cfg.get("build_count", 0)) + 1
    plugin_mut = {
        "build_count": build_count,
        "last_action": req.get("action", "run")
    }

    # Build global mutations (write last_run_at timestamp)
    global_mut = {
        "tester_demo": {
            "last_run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    }

    resp = {
        "status": "ok",
        "logs": logs,
        "artifacts": [],
        "mutations": {
            "plugin": plugin_mut,
            "global": global_mut
        }
    }
    print(json.dumps(resp))

if __name__ == "__main__":
    main()
