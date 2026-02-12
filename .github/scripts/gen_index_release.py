#!/usr/bin/env python3
# gen_index_release.py
# - Build dist-artifacts/<name>-<version>.zip for each plugins/<name>/
# - Compute sha256
# - Update index.yaml (merge versions, keep history)
# - source points to GitHub Release assets: https://github.com/<REPO>/releases/download/<TAG>/<zip>

import os, sys, json, yaml, datetime, hashlib, zipfile

ROOT = os.environ.get("GITHUB_WORKSPACE", ".")
PLUGINS_DIR = os.path.join(ROOT, "plugins")
OUT_DIR = os.path.join(ROOT, "dist-artifacts")

REPO = os.environ.get("REPO_FULL_NAME", "")  # e.g. systemnb/lyenv-plugin-center
RELEASE_TAG = os.environ.get("RELEASE_TAG", "artifacts")
DEFAULT_REF = os.environ.get("DEFAULT_REF", "main")

def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return yaml.safe_load(f)

def zip_dir(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src_dir):
            if ".git" in dirs:
                dirs.remove(".git")
            for fn in files:
                p = os.path.join(root, fn)
                arc = os.path.relpath(p, src_dir)
                z.write(p, arc)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(64 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def load_existing_index(path):
    if not os.path.isfile(path):
        return {"apiVersion": "v1", "updatedAt": "", "plugins": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "plugins" not in data or not isinstance(data["plugins"], dict):
        data["plugins"] = {}
    if "apiVersion" not in data:
        data["apiVersion"] = "v1"
    return data

def main():
    if not os.path.isdir(PLUGINS_DIR):
        print("plugins dir not found", file=sys.stderr)
        sys.exit(1)

    if not REPO:
        # fallback (still usable, but better set env)
        REPO = "systemnb/lyenv-plugin-center"

    os.makedirs(OUT_DIR, exist_ok=True)

    index_path = os.path.join(ROOT, "index.yaml")
    index = load_existing_index(index_path)

    # update timestamp (required by your decision 2Y)
    index["updatedAt"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for name in sorted(os.listdir(PLUGINS_DIR)):
        sub = os.path.join(PLUGINS_DIR, name)
        if not os.path.isdir(sub):
            continue

        manifest_path = None
        for cand in ("manifest.yaml", "manifest.yml", "manifest.json"):
            p = os.path.join(sub, cand)
            if os.path.isfile(p):
                manifest_path = p
                break
        if not manifest_path:
            print(f"skip {name}: no manifest", file=sys.stderr)
            continue

        m = load_manifest(manifest_path) or {}
        version = str(m.get("version") or "0.0.0")
        expose = m.get("expose") or []
        desc = m.get("name", name)

        zip_name = f"{name}-{version}.zip"
        zip_path = os.path.join(OUT_DIR, zip_name)

        zip_dir(sub, zip_path)
        digest = sha256_file(zip_path)

        # GitHub release asset download URL
        source_url = f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{zip_name}"

        # base entry
        entry = index["plugins"].get(name) or {}
        entry["desc"] = entry.get("desc") or desc
        entry["repo"] = entry.get("repo") or REPO
        entry["subpath"] = entry.get("subpath") or f"plugins/{name}"
        entry["ref"] = entry.get("ref") or DEFAULT_REF
        entry["shims"] = expose

        versions = entry.get("versions") or {}
        # merge versions: keep old + update this version
        versions[version] = {
            "source": source_url,
            "sha256": digest,
            "shims": expose,
        }
        entry["versions"] = versions

        index["plugins"][name] = entry

        print(f"Built {zip_name} sha256={digest}")

    with open(index_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(index, f, sort_keys=False)
    print(f"Updated index.yaml: {index_path}")
    print(f"Artifacts output: {OUT_DIR}")

if __name__ == "__main__":
    main()
