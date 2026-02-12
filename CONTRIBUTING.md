# Contributing to lyenv (Plugins + GUI workflows)

Thanks for contributing! This guide explains how to:
- develop plugins (recommended: GUI workflows)
- test locally in a lyenv environment
- publish plugins to the plugin center (Release-assets model)

---

## 1) Recommended: Author workflows in the GUI

### Run GUI

```bash
lyenv gui start --open
```

Register an env directory:

```bash
lyenv gui add ./demo --name=demo
```

### Build & Run a workflow

1. Create nodes (Start → ... → End)
2. Put nodes into a **Group** — one Group = one command
3. Click **Run**, pick group, enter args
4. The GUI will export → install → run → stream logs → cleanup automatically

When stable, export the workflow as a plugin zip and publish it.

---

## 2) Hand-writing plugins (supported)

### Minimal layout

```
plugins/<NAME>/
├─ manifest.yaml|yml|json
├─ scripts/
│  └─ ...
└─ config.yaml|json (optional)
```

### Local test

Create a local env:

```bash
lyenv create ./env
lyenv init ./env
cd ./env
```

Activate:

**Linux/macOS (bash/zsh):**

```bash
eval "$(lyenv activate)"
```

**Windows PowerShell:**

```powershell
lyenv activate | Invoke-Expression
```

Install plugin from local folder:

```bash
lyenv plugin add /abs/path/to/plugin --name=<INSTALL_NAME>
```

Run:

```bash
lyenv run <INSTALL_NAME> run -- arg1 arg2
```

---

## 3) Publishing plugins to the Plugin Center (Release-assets model)

The plugin center is a monorepo:

- plugin source: `plugins/<NAME>/`
- zips are uploaded as GitHub Release assets under fixed tag `artifacts` by CI 2 3
- `index.yaml` is updated by CI to include source + sha256 per version

### 3.1 What you commit

✅ Commit plugin source **only** under:  
`plugins/<NAME>/`  
`manifest.yaml`  
`scripts/...`  
`config.yaml` (optional)

❌ Do **NOT** commit zip artifacts.

### 3.2 PR flow (recommended)

1. Fork the plugin center repo
2. Add/modify `plugins/<NAME>/...`
3. Bump version in the plugin manifest
4. Open a PR to `main`
5. After merge, CI will:
   - build `<NAME>-<VERSION>.zip`
   - upload it to Release assets (tag=`artifacts`) 2 3
   - update `index.yaml` (keeping historical versions)
   - open an automatic PR for `index.yaml`
6. You then merge the `index.yaml` PR to publish

### 3.3 Contributing without cloning the whole center repo (sparse checkout)

If the center repo grows large, use sparse checkout to work only on your plugin folder:

```bash
git clone --filter=blob:none --no-checkout https://github.com/<ORG>/lyenv-plugin-center.git
cd lyenv-plugin-center
git sparse-checkout init --cone
git sparse-checkout set plugins/<NAME> .github/scripts index.yaml
git checkout main
```

### 3.4 Install from center (verify)

Users can install:

**latest:**

```bash
lyenv plugin install <NAME> --name=<INSTALL_NAME>
```

**specific version:**

```bash
lyenv plugin install <NAME> --version=0.1.0 --name=<INSTALL_NAME>
lyenv plugin install <NAME>@0.1.0 --name=<INSTALL_NAME>
```

---

## 4) CI notes

- If your CI uses `npm ci`, ensure `package-lock.json` exists and is committed, because `npm ci` requires an existing lockfile. 4
- Release pipelines often build multiple OS/arch targets using the GitHub Actions matrix strategy. 1
- Build artifacts can be uploaded/downloaded with artifact actions. 5 6

---

## 5) Style and portability checklist

- LF line endings for scripts
- Shebang + executable bit when needed
- Avoid non-portable inline editing (e.g. `awk -i inplace`)
- Prefer stdio JSON executor for structured results

Thanks again!
