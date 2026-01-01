#!/usr/bin/env python3
# Generate index.yaml by scanning plugins/* subdirectories.
# Reads manifest.yaml|yml|json to extract name, version, expose, and writes repo/ref/subpath entries.

import os, sys, json, yaml, datetime

ROOT = os.environ.get("GITHUB_WORKSPACE", ".")
PLUGINS_DIR = os.path.join(ROOT, "plugins")
REPO = os.environ.get("REPO_FULL_NAME", "YOUR_ORG/plugin-center")
REF = os.environ.get("DEFAULT_REF", "main")

def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return yaml.safe_load(f)

def main():
    if not os.path.isdir(PLUGINS_DIR):
        print("plugins dir not found", file=sys.stderr)
        sys.exit(1)

    index = {
        "apiVersion": "v1",
        "updatedAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugins": {}
    }

    for name in sorted(os.listdir(PLUGINS_DIR)):
        sub = os.path.join(PLUGINS_DIR, name)
        if not os.path.isdir(sub):
            continue
        # find manifest file
        manifest = None
        for cand in ("manifest.yaml", "manifest.yml", "manifest.json"):
            p = os.path.join(sub, cand)
            if os.path.isfile(p):
                manifest = p
                break
        if not manifest:
            print(f"skip {name}: no manifest", file=sys.stderr)
            continue

        m = load_manifest(manifest) or {}
        expose = m.get("expose") or []
        version = m.get("version") or "0.0.0"
        # fill entry
        entry = {
            "desc": m.get("name", name),
            "repo": REPO,
            "subpath": f"plugins/{name}",
            "ref": REF,
            "shims": expose,
            "versions": {
                str(version): {
                    "repo": REPO,
                    "subpath": f"plugins/{name}",
                    "ref": REF,
                    "shims": expose
                }
            }
        }
        index["plugins"][name] = entry

    # write index.yaml
    out = os.path.join(ROOT, "index.yaml")
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(index, f, sort_keys=False)
    print(f"Generated: {out}")

if __name__ == "__main__":
    main()
