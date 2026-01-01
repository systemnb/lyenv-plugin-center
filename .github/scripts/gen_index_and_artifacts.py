#!/usr/bin/env python3
# Generate artifacts/*.zip for each plugin and build index.yaml with source+sha256.
# Assumptions:
# - Repo structure: plugins/<NAME>/{manifest.yaml|yml|json, ...}
# - Artifacts written to artifacts/<NAME>-<VERSION>.zip
# - source URLs point to raw.githubusercontent.com on 'main' branch (after PR merged).
import os, sys, json, yaml, datetime, hashlib, zipfile

ROOT = os.environ.get("GITHUB_WORKSPACE", ".")
PLUGINS_DIR = os.path.join(ROOT, "plugins")
ARTIFACTS_DIR = os.path.join(ROOT, "artifacts")

REPO = os.environ.get("REPO_FULL_NAME", "systemnb/lyenv-plugin-center")
DEFAULT_REF = os.environ.get("DEFAULT_REF", "main")

RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main/artifacts"  # points to main (post-merge)

def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return yaml.safe_load(f)

def zip_dir(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src_dir):
            # skip logs or VCS dirs if desired
            if ".git" in dirs: dirs.remove(".git")
            for fn in files:
                p = os.path.join(root, fn)
                # relative path under src_dir
                arc = os.path.relpath(p, src_dir)
                z.write(p, arc)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(64*1024)
            if not b: break
            h.update(b)
    return h.hexdigest()

def main():
    if not os.path.isdir(PLUGINS_DIR):
        print("plugins dir not found", file=sys.stderr); sys.exit(1)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    index = {
        "apiVersion": "v1",
        "updatedAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugins": {}
    }

    for name in sorted(os.listdir(PLUGINS_DIR)):
        sub = os.path.join(PLUGINS_DIR, name)
        if not os.path.isdir(sub): continue
        manifest = None
        for cand in ("manifest.yaml", "manifest.yml", "manifest.json"):
            p = os.path.join(sub, cand)
            if os.path.isfile(p): manifest = p; break
        if not manifest:
            print(f"skip {name}: no manifest", file=sys.stderr); continue

        m = load_manifest(manifest) or {}
        expose = m.get("expose") or []
        version = str(m.get("version") or "0.0.0")

        # Build zip and compute sha256
        zip_name = f"{name}-{version}.zip"
        zip_path = os.path.join(ARTIFACTS_DIR, zip_name)
        zip_dir(sub, zip_path)
        digest = sha256_file(zip_path)

        # Source URL (raw on main branch after merge)
        source_url = f"{RAW_BASE}/{zip_name}"

        entry = {
            "desc": m.get("name", name),
            "repo": REPO,
            "subpath": f"plugins/{name}",
            "ref": DEFAULT_REF,
            "shims": expose,
            "versions": {
                version: {
                    "source": source_url,
                    "sha256": digest,
                    "shims": expose
                }
            }
        }
        index["plugins"][name] = entry

    out = os.path.join(ROOT, "index.yaml")
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(index, f, sort_keys=False)
    print(f"Generated: {out}")
    print(f"Artifacts dir: {ARTIFACTS_DIR}")

if __name__ == "__main__":
    main()
