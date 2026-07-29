# scripts/cmd_project.py
# Entry point for 'kade project' subcommands.

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lyenv_sdk import read_request, respond_ok, respond_error, log, args as rt_args
from scripts.lib.project import add_project, remove_project, list_projects

def main():
    read_request()
    a = rt_args()
    if len(a) < 1:
        respond_error("Usage: kade project <add|remove|list> [args...]", code=2)

    sub = a[0]
    rest = a[1:]

    # Only supported for GKI for now
    from scripts.lib.common import cfg
    flavor = str(cfg("kernel.flavor", "") or "").strip()
    if flavor != "gki":
        respond_error("Project management is only supported for GKI flavor.", code=2)

    if sub == "add":
        info = add_project(rest)
        respond_ok("project add ok", extra={"outputs": [f"{k}={v}" for k, v in info.items()]})

    elif sub == "remove":
        info = remove_project(rest)
        respond_ok("project remove ok", extra={"outputs": [f"removed={info.get('name','')}"]})

    elif sub == "list":
        info = list_projects()
        lines = []
        for p in info["projects"]:
            lines.append(f"  - {p['name']} (module: {p['module_name']}, in_tree: {p.get('in_tree', True)})")
        respond_ok("projects listed", extra={"outputs": lines})

    else:
        respond_error(f"Unknown project subcommand: {sub}", code=2)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"[project] error: {e}")
        respond_error(str(e), code=3)