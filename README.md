## ✅ README.md

# lyenv — Directory-based Isolated Environment Manager (with Visual Workflow GUI)

**Languages:** [English](README.md) | [中文](README_zh.md)
**Platforms:** Windows · Linux · Android (Termux)

> **TL;DR**: Build workflows in the GUI (recommended). The GUI exports *real* lyenv plugins. The CLI installs/runs plugins with structured stdio JSON, logs, and config mutations.

---

## 1. What is lyenv?

**lyenv** is a directory-based environment manager and automation runtime:

- **Environment = a directory** (`bin/`, `plugins/`, `workspace/`, `.lyenv/`)
- **Workflow = a plugin** (manifest-driven commands)
- **stdio JSON execution**: plugins exchange JSON via stdin/stdout (structured result/logs/mutations)
- **GUI is a workflow compiler**: draw flows → export as multi-step stdio plugin → install/run with live logs

---

## 2. Quick Start

### 2.1 Build

```bash
make build
make build-gui
```

CI note: if your workflow uses npm ci, you must commit package-lock.json (or shrinkwrap) because npm ci requires an existing lockfile. 4

### 2.2 Create & Init an Environment

```bash
lyenv create ./demo
lyenv init ./demo
```

### 2.3 Activate (per shell)

**Linux/macOS (bash/zsh)**

```bash
eval "$(lyenv activate)"
```

**Windows PowerShell**

```powershell
lyenv activate | Invoke-Expression
```

---

## 3. Install / Uninstall (No source repo required)

`lyenv install` installs both `lyenv` and `lyenv-gui`:

- Tries system bin first (e.g. `/usr/local/bin`, Termux `$PREFIX/bin`)
- If permission denied, falls back to `~/.local/bin`
- Windows (policy A): no automatic PATH modification; if not found, add install directory to PATH manually.

**Install:**

```bash
lyenv install
```

**Uninstall:**

```bash
lyenv uninstall
```

**Optional:**

```bash
lyenv install --bindir=/usr/local/bin
lyenv uninstall --bindir=/usr/local/bin
```

---

## 4. GUI (Recommended Workflow Authoring)

### 4.1 Start the GUI server

```bash
lyenv gui start --open
```

Register an environment for GUI selection:

```bash
lyenv gui add ./demo --name=demo
lyenv gui list
```

### 4.2 Build workflows visually (recommended)

- Create nodes and edges (Start → ... → End)
- Put a flow into a Group: one Group = one command
- Click **Run**:
  - choose which group to run
  - input args
  - GUI exports a temporary plugin → installs → runs → streams logs → cleans up

### 4.3 Export as plugin

When the flow is stable, export it as a plugin package (zip). This zip can be:

- installed locally (for development), or
- published to the plugin center (see below).

---

## 5. Plugins and Execution Model

### 5.1 Minimal plugin layout

```
plugin/
├─ manifest.yaml|yml|json
├─ config.yaml|json (optional)
└─ scripts/
   └─ ...
```

### 5.2 Executors

- **shell**: simple command execution and logging
- **stdio (recommended)**: JSON request/response via stdin/stdout
  - supports `message` (final result), `logs`, `artifacts`, `mutations`
  - mutations are merged safely into:
    - global config: `lyenv.yaml`
    - plugin local config: `plugins/<INSTALL_NAME>/config.yaml|json`

### 5.3 Run a plugin

```bash
lyenv run <INSTALL_NAME> <COMMAND> -- arg1 arg2
```

---

## 6. Plugin Center: Install by name (supports custom versions)

**Install latest:**

```bash
lyenv plugin install tester --name=tester
```

**Install a specific version:**

```bash
lyenv plugin install tester --version=0.1.0 --name=tester
```

**Sugar syntax:**

```bash
lyenv plugin install tester@0.1.0 --name=tester
```

---

## 7. Publishing Plugins to the Center (Developer Guide)

This project uses a plugin center monorepo:

- plugin source lives in `plugins/<NAME>/`
- plugin zip archives are published as GitHub Release assets under a fixed tag `artifacts` using a release upload action. 2 3
- `index.yaml` contains source + sha256 per version and is updated by CI

### 7.1 Upload (publish) workflow (what developers do)

1. Prepare a plugin directory (GUI-exported zip or hand-written plugin)
2. Add plugin source to the center repo at:  
   `plugins/<NAME>/`  
   `manifest.yaml`  
   `...`
3. Open a PR to center repo `main` **with source files only** (do NOT commit zip artifacts)
4. After merge, CI will:
   - package `plugins/<NAME>` into `<NAME>-<VERSION>.zip`
   - upload zip to GitHub Release assets (tag=`artifacts`) 2 3
   - update `index.yaml` and open a PR
5. Merge the `index.yaml` PR to publish

### 7.2 Contributing guide

See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- local testing
- sparse checkout (no full repo clone)
- CI rules and versioning

---

## 8. Release Automation (this repo)

Releases are built by GitHub Actions on tag push using a build matrix (OS/arch combinations). The matrix strategy is a standard GitHub Actions feature. 1  
Release assets are uploaded using a GitHub Release action. 2 3  
Build artifacts are typically collected via artifact upload/download actions. 5 6

---

## 9. Logs

- Global dispatch log: `.lyenv/logs/dispatch.log`
- Per-run log: `.lyenv/logs/dispatch/<DISPATCH_ID>.log`
- Plugin logs: `plugins/<INSTALL_NAME>/logs/YYYY-MM-DD/...`

---

## 10. License

See [LICENSE](LICENSE).

---
