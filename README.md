# Unified Plugin Authoring Guide for **lyenv**  
*统一的 lyenv 插件制作技术文档* [中文](README_zh.md) / [English](README.md)

> **Language / 语言**: 中文指南 · English Guide  
> License: see `LICENSE` in repository root.  
> Purpose: This README teaches **plugin authors** how to design, build, test, distribute, install, and run plugins for **lyenv**, in a robust, cross-platform, and maintainable way—without being limited to any single use case.

---

## English Guide

### 1. Overview
lyenv is a directory-based environment manager that standardizes how plugins are installed, configured, executed, and logged.

**Environment layout** (created by `lyenv create/init`):
```
ENV_ROOT/
├─ bin/                         # shims (e.g., myctl)
├─ plugins/                     # plugins (one dir per install)
│  └─ <INSTALL_NAME>/
│     ├─ manifest.yaml|yml|json # REQUIRED
│     ├─ config.yaml|json       # plugin-local config (optional, recommended)
│     ├─ scripts/               # plugin scripts
│     └─ logs/YYYY-MM-DD/       # per-command logs (JSON Lines)
├─ workspace/                   # free use by plugins
└─ .lyenv/
   ├─ logs/dispatch.log         # global dispatch log
   └─ registry/installed.yaml   # registry of installed plugins
```

**Key ideas**:
- Manifest-first plugin design.
- Executors: `shell` (simple logging) vs `stdio` (JSON request/response with mutations).
- Argument passing:
  - `shell`: `args` + user `-- ...args` appended to command line.
  - `stdio`: user `-- ...args` appear in `req["args"]`.
- Workdir: defaults to plugin root; override via `workdir`.
- Config merge: `mutations` are safely merged into `lyenv.yaml` (global) and `config.yaml|json` (plugin-local).
- Standard logs: JSON Lines per command; global dispatch log maintained by core.

---

### 2. Manifest Spec

#### 2.1 Minimal template (YAML)
```yaml
name: myplugin
version: 0.1.0
expose: [myctl]

config:
  local_file: ./config.yaml

commands:
  - name: run
    summary: Example stdio command
    executor: stdio
    program: ./main.py
    use_stdio: true
    workdir: .
```

#### 2.2 Fields
- `name`: logical name (display only); actual directory is the install name.
- `version`: SemVer recommended.
- `expose[]`: shim aliases; e.g., `myctl` → `ENV_ROOT/bin/myctl`.
- `config.local_file`: plugin-local config path (relative to plugin root).
- `commands[]`:
  - `executor`: `shell` or `stdio`.
  - `program`: system command (e.g., `python3`) or plugin-relative path (e.g., `./main.py`).
  - `args[]`: fixed args.
  - `workdir`: working dir.
  - `env`: injected env for child process.
  - `use_stdio`: stdio flag.
  - `steps[]`: multi-step (shell/stdio mix), with `continue_on_error`.

---

### 3. Executors & Arguments

#### 3.1 shell
- Core executes `bash -c "<program + args + passArgs>"`.
- Good for simple commands without structured returns.
- Example:
  ```yaml
  commands:
    - name: hello
      summary: Say hello from shell
      executor: shell
      program: echo "hello"
      args: ["from", "shell"]
  ```

#### 3.2 stdio (recommended)
- Core writes a request JSON to stdin; expects a response JSON on stdout.
- See the Chinese section for detailed examples.
- `mutations` are merged into global and plugin-local configs according to strategy.

---

### 4. Plugin Directory & Scripts

#### 4.1 Location
After installation, plugin must be at `ENV_ROOT/plugins/<INSTALL_NAME>/`.  
Manifest at plugin root is required.

#### 4.2 Scripts
- LF line endings; valid shebang; executable bit for direct scripts.
- Avoid `awk -i inplace` (not portable). Use **temp file + sed/Python**.

#### 4.3 STDIO Python script example
```python
#!/usr/bin/env python3
import sys, json, time
def main():
    req = json.load(sys.stdin)
    args = req.get("args") or []
    resp = {"status":"ok","logs":[f"args={args}"],"mutations":{"plugin":{"status":{"last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ")}}}}
    print(json.dumps(resp))
if __name__ == "__main__":
    main()
```

---

### 5. Install & Run (User flow)
```bash
lyenv create ./env
lyenv init ./env
cd ./env
eval "$(lyenv activate)"

lyenv plugin add ./plugins/myplugin --name=myplugin

myctl run
# or:
lyenv run myplugin run -- --DRIVER=mydriver
```

Shim: Prefer `LYENV_BIN` inside shim; fallback to `lyenv` in PATH.

---

### 6. Plugin Center (Unified distribution)
- Monorepo structure `plugin-center/plugins/<NAME>/` with auto-generated `index.yaml`.
- Install by name: `lyenv plugin install <NAME> --name=<INSTALL_NAME>`
  - Prefer archive + sha256 if available; else use repo+subpath+ref.

---

### 7. Multi-step, Timeout & Policies
- `steps[]` supports shell/stdio mixing and `continue_on_error`.
- Run options: `--timeout=<sec>`, `--fail-fast`, `--keep-going`.

---

### 8. Mutations (Config merge)
- Strategies: `override`, `append`, `keep`.
- Use `mutations` in stdio responses; core merges into `lyenv.yaml` and plugin-local config safely.

---

### 9. Logs
- Per-command logs: `plugins/<INSTALL_NAME>/logs/YYYY-MM-DD/<COMMAND>-<TIMESTAMP>.log` (JSON Lines).
- Global dispatch: `.lyenv/logs/dispatch.log`.
- Emit debug info about entry/args/workdir/envPATH for better diagnostics.

---

### 10. CI: Index & Archive (with SHA‑256)
- Center CI packs `artifacts/<NAME>-<VERSION>.zip`, computes SHA‑256, updates `index.yaml`, and opens a PR using a PAT secret.
- Client verifies archive SHA‑256 before installation.

---

### 11. Troubleshooting
- **Wrong directory**: ensure plugin is at `ENV_ROOT/plugins/<INSTALL_NAME>/`.
- **Missing args**:
  - `shell`: use positional `$1 $2 ...`.
  - `stdio`: read `req["args"]`.
- **Config not parsed**: rely on `config.local_file` and stdio `mutations`.
- **Shebang/LF**: ensure proper shebang and executable bit; `python3` in PATH.
- **Avoid `awk -i inplace`**: use temp file pattern.
- **lyenv not found**: use `LYENV_BIN` in shim or add `dist/` to PATH.
- **Timeout & policy**: use `--timeout`, `--fail-fast`, `--keep-going`.

---

### 12. Author Checklist
- [ ] Create `plugins/<NAME>/`.
- [ ] Write `manifest.yaml|json` (prefer `stdio`).
- [ ] Write scripts (English comments, LF, executable, portable edits).
- [ ] Provide `config.yaml|json`.
- [ ] Local test: `lyenv plugin add` & `lyenv run` with args.
- [ ] Push to center repo; CI generates `index.yaml` & artifacts.
- [ ] End-user install by name from center.

---

**End**