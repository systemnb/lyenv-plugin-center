# Contributing to lyenv (Plugins + GUI Workflows)

Thanks for contributing to **lyenv**!

This document explains how to:
- create plugins using the **GUI (recommended)**
- understand **how data flows between nodes**
- export workflows as **standard lyenv plugins**
- write plugins **without the GUI** (advanced)
- publish plugins to the **Plugin Center** (Release-assets model)

---

## 0) Quick Glossary

**Environment (env)**  
A directory created by `lyenv create/init`, containing:
`bin/`, `plugins/`, `workspace/`, `.lyenv/`, and `lyenv.yaml`.

**Plugin**  
A folder under `env/plugins/<INSTALL_NAME>/` with a manifest and scripts.

**Workflow**  
A visual graph (nodes + edges) built in the GUI.  
When exported, it becomes a **real lyenv plugin**.

**Group**  
A GUI Group defines **one executable command**.
> **One Group = one command**

**Ports**  
Nodes exchange data through named ports:
- Output port → produces data
- Input port → consumes data

---

## 1) Recommended: Author Plugins via the GUI (Workflow-first)

The lyenv GUI is **not a separate runtime**.  
It is a **visual workflow compiler** that exports real, portable plugins.

> **Workflow = Plugin**  
> **Group = Command**  
> **Node = stdio Step**

---

### 1.1 Setup (One-time)

```bash
lyenv create ./demo
lyenv init ./demo
cd ./demo
```

**Activate:**  
Linux/macOS  
```bash
eval "$(lyenv activate)"
```
Windows PowerShell  
```powershell
lyenv activate | Invoke-Expression
```

**Start GUI and register the env:**  
```bash
lyenv gui start --open
lyenv gui add . --name=demo
```

---

### 1.2 Workflow Overview

> Put picture here

A minimal workflow consists of:  
`Start` → `Node(s)` → `End`

- `Start`: receives CLI arguments  
- `Node`: executes real programs  
- `End`: produces the final result  

Execution always flows left to right.

---

### 1.3 Ports and Data Flow (Very Important)

> Put picture here

Nodes exchange data through named ports.  
Example wiring:  
`Start.name ──▶ Greet.name`  
`Greet.greeting ──▶ End.greeting`

At runtime:
- Start maps CLI args to its output ports
- Nodes read inputs via wiring
- Nodes execute programs
- Outputs are written back to wiring
- End reads final values and returns result

⚠️ If a port is not connected, downstream nodes receive empty values.

---

## 2) Hands-on GUI Test Case: “Hello, <name>!”

Expected output:  
```
Hello, Alice!
```

### 2.1 Build the Graph

Create three nodes:
- `Start`
- `Node` (label: `Greet`)
- `End`

### 2.2 Define Ports

**Start**
- Output ports: `name`

**Greet**
- Input ports: `name`
- Output ports: `greeting`

**End**
- Input ports: `greeting`

### 2.3 Connect Nodes
- `Start.name` → `Greet.name`
- `Greet.greeting` → `End.greeting`

### 2.4 Configure the Greet Node Program

Example Python logic:
```python
import sys
name = sys.argv[1] if len(sys.argv) > 1 else "world"
print(f"Hello, {name}!")
```

Notes:
- Do not hardcode `python3`
- Exported runners use `sys.executable` for portability

### 2.5 Create a Group (One Group = One Command)

Create a Group containing:
- Start
- Greet
- End

Name the command: `run`

### 2.6 Run in GUI

> Put picture here

Steps:
1. Click `Run`
2. Select Group `run`
3. Input args: `Alice`

Final output:
```
Hello, Alice!
```

The GUI automatically:
- exports a temporary plugin
- installs it
- runs it
- streams logs
- cleans up

---

## 3) Export as Plugin and Verify via CLI

> Put picture here

Export the workflow as a plugin.  
Install locally:
```bash
lyenv plugin add /path/to/exported-plugin --name=hello-demo
```

Run via CLI:
```bash
lyenv run hello-demo run -- Alice
```

Expected:
```
Hello, Alice!
```

---

## 4) Writing Plugins Without the GUI (Advanced)

GUI is recommended, but direct plugin development is supported.

### 4.1 Minimal Plugin Layout

```
plugins/<NAME>/
├─ manifest.yaml
├─ scripts/
│  └─ main.py
└─ config.yaml (optional)
```

### 4.2 Example `manifest.yaml`

```yaml
name: hello-cli
version: 0.1.0
expose: [run]

commands:
  - name: run
    executor: stdio
    program: ./scripts/main.py
```

### 4.3 Example stdio script

```python
from lyenv_sdk import read_request, respond_ok

req = read_request()
args = req.get("args", [])
name = args[0] if args else "world"
respond_ok(f"Hello, {name}!")
```

This approach is more flexible, but you must:
- manage wiring manually
- handle inputs/outputs yourself

---

## 5) Publishing to the Plugin Center (Release-assets Model)

✅ **Commit source only:**
```
plugins/<NAME>/
  manifest.yaml
  scripts/
  config.yaml (optional)
```

❌ **Do NOT commit zip artifacts.**

**PR flow:**
1. Fork the plugin center repo
2. Add/modify `plugins/<NAME>/...`
3. Bump version in `manifest.yaml`
4. Open PR to `main`

After merge, CI will:
- build `<NAME>-<VERSION>.zip`
- upload it as GitHub Release assets (tag=artifacts)
- update `index.yaml`
- open an automatic PR

Merge the `index.yaml` PR to publish.

---

## 6) Troubleshooting

| Issue | Solution |
|-------|----------|
| `node failed` | check `scripts/runner_<NODE>.py`<br>inspect stderr in GUI logs |
| **Windows issues** | ensure Python is installed<br>rely on `sys.executable`<br>avoid OS-specific shell commands |
| **Empty data** | most often caused by missing edges<br>verify port connections |

---

## 7) Style & Portability Checklist

- [ ] LF line endings
- [ ] Avoid OS-specific tools
- [ ] Prefer `sys.executable` for Python
- [ ] Keep nodes stateless
- [ ] Validate wiring visually in GUI

Thanks for contributing to lyenv 🚀

---