# scripts/lib/project.py
# Manage multiple driver projects stored in gki.projects config.

import os
from typing import Dict, List

from lyenv_sdk import log, plugin_write_config
from scripts.lib.common import cfg

def _get_projects() -> List[Dict]:
    """
    Read project list from gki.projects.
    If empty, fallback to legacy single gki.driver definition.
    """
    projs = cfg("gki.projects", default=[])
    if not projs:
        # Backward compatibility: derive a single project from gki.driver
        old = cfg("gki.driver", default={})
        if old:
            projs = [{
                "name": old.get("project_name", "unknown"),
                "module_name": old.get("module_name", ""),
                "in_tree": old.get("in_tree", True),
                "external_src_dir": old.get("external_src_dir", ""),
                "overwrite": old.get("overwrite", True),
                "in_tree_path": old.get("in_tree_path", ""),
            }]
    return projs

def _save_projects(projs: List[Dict]):
    """Persist the project list to gki.projects configuration."""
    plugin_write_config("gki.projects", projs, scope="plugin")

def add_project(args: List[str]) -> Dict:
    """
    Add a new driver project to the configuration.
    Required arguments: --name NAME --module MODULE
    Optional: --in-tree, --external-src-dir PATH, --in-tree-path PATH, --overwrite
    """
    params = {}
    i = 0
    while i < len(args):
        if args[i] == "--name" and i+1 < len(args):
            params["name"] = args[i+1]; i += 2
        elif args[i] == "--module" and i+1 < len(args):
            params["module_name"] = args[i+1]; i += 2
        elif args[i] == "--in-tree":
            params["in_tree"] = True; i += 1
        elif args[i] == "--external-src-dir" and i+1 < len(args):
            params["external_src_dir"] = args[i+1]; i += 2
        elif args[i] == "--in-tree-path" and i+1 < len(args):
            params["in_tree_path"] = args[i+1]; i += 2
        elif args[i] == "--overwrite" and i+1 < len(args):
            val = args[i+1].lower()
            params["overwrite"] = val in ("1", "true", "yes"); i += 2
        else:
            i += 1

    if "name" not in params or "module_name" not in params:
        raise ValueError("project add requires --name and --module")

    projs = _get_projects()
    for p in projs:
        if p["name"] == params["name"]:
            raise ValueError(f"Project '{params['name']}' already exists. Use remove first.")

    new_proj = {
        "name": params["name"],
        "module_name": params["module_name"],
        "in_tree": params.get("in_tree", True),
        "external_src_dir": params.get("external_src_dir", ""),
        "overwrite": params.get("overwrite", True),
        "in_tree_path": params.get("in_tree_path", ""),
    }
    projs.append(new_proj)
    _save_projects(projs)

    log(f"[project] added project: {new_proj}")
    return new_proj

def remove_project(args: List[str]) -> Dict:
    """
    Remove a project by name.
    Required argument: --name NAME
    """
    name = None
    for i, a in enumerate(args):
        if a == "--name" and i+1 < len(args):
            name = args[i+1]
    if not name:
        raise ValueError("project remove requires --name")

    projs = _get_projects()
    new_projs = [p for p in projs if p["name"] != name]
    if len(new_projs) == len(projs):
        raise ValueError(f"Project '{name}' not found.")

    removed = None
    for p in projs:
        if p["name"] == name:
            removed = p
            break

    _save_projects(new_projs)
    log(f"[project] removed project: {removed}")
    return removed

def list_projects() -> Dict:
    """Return the current list of driver projects."""
    projs = _get_projects()
    return {"projects": projs}