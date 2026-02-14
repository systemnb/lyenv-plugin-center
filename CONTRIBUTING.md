# Contributing to lyenv (GUI Workflows + Plugins)

Thanks for contributing to **lyenv**!  
This guide focuses on the **GUI-first workflow experience**, including:

- how data moves between nodes (ports + wiring)
- how to write node code using the **Hybrid Node Runtime**
- a complete example you can reproduce: **KV Set → KV Get**
- how to export and publish plugins to the Plugin Center

![](gui-overview.png)

---

## 0) Key Ideas (Read First)

### 0.1 Workflow model
- **Workflow = Plugin**
- **Group = Command**
- **Nodes = Steps**
- **Edges = Data dependencies**

### 0.2 Dataflow model (the important part)
Nodes exchange data through **ports**:

- **Output ports** produce values
- **Input ports** consume values
- A connection means:  
  `Upstream.output_port → Downstream.input_port`

At runtime, values are stored in a flow “bus”:

```
flow.outputs.<node_id>.<port_name>
```

The GUI exporter generates a wiring map (`flow_wiring.json`) so each node can resolve its inputs from upstream outputs.

![](gui-ports.png)

---

## 1) Setup (One-time)

Create an env:

```bash
lyenv create ./demo
lyenv init ./demo
cd ./demo
```

Activate:

- **Linux/macOS**:
  ```bash
  eval "$(lyenv activate)"
  ```
- **Windows PowerShell**:
  ```powershell
  lyenv activate | Invoke-Expression
  ```

Start GUI and register env:

```bash
lyenv gui start --open
lyenv gui add . --name=demo
```

---

## 2) Hybrid Node Runtime (Most Important)

lyenv GUI uses a **Hybrid Node Runtime** so node authors can choose between two styles, but the node type does not split.

### 2.1 Simple style (recommended for 80% nodes)

- Inputs come from `argv` (port order)
- Outputs go to `stdout`
- For multi-output: print a JSON array: `["o1","o2"]`

Example (`simple_node.py`):

```python
import sys, json
a = sys.argv[1] if len(sys.argv) > 1 else ""
b = sys.argv[2] if len(sys.argv) > 2 else ""
print(json.dumps([a.upper(), b.lower()], ensure_ascii=False))
```

### 2.2 Advanced style (when you need config/mutations/artifacts)

- You can call `read_request()` in the node script
- You can use `mutate` / `config_plugin` / `emit_artifact` / `log`
- You can return a full stdio JSON response via `respond_ok` / `respond_error`
- To map outputs reliably to ports, return:

```python
respond_ok("", extra={"outputs": ["out1", "out2"]})
```

**Why it works**: the runner forwards the request JSON into child stdin and merges child stdio responses automatically.

---

## 3) Complete GUI Example: KV Set → KV Get (shows real data passing)

**Goal**:

- User inputs `key val`
- Write plugin config: `kv.<key> = <val>`
- Read it back and print the value

Expected output: `bar`

### 3.1 Build the graph

Create nodes:

- `Start`
- `WriteKV` (Code node, Python)
- `ReadKV` (Code node, Python)
- `End`

![](gui-overview-grphy.png)

### 3.2 Define ports

- **Start**  
  outputs: `key`, `val`

- **WriteKV**  
  inputs: `key`, `val`  
  outputs: `key`

- **ReadKV**  
  inputs: `key`  
  outputs: `val`

- **End**  
  inputs: `val`

### 3.3 Connect edges (wiring)

- `Start.key` → `WriteKV.key`
- `Start.val` → `WriteKV.val`
- `WriteKV.key` → `ReadKV.key`
- `ReadKV.val` → `End.val`

![](gui-wiring.png)

### 3.4 Node code (copy/paste)

#### 3.4.1 WriteKV node (Python)

This node writes `kv.<key> = <val>` into plugin config via mutations, and outputs `key`.

```python
import sys
from lyenv_sdk import read_request, mutate, respond_ok, respond_error, log

def main():
    # Load request (available because hybrid runtime forwards stdin)
    read_request()

    key = sys.argv[1] if len(sys.argv) > 1 else ""
    val = sys.argv[2] if len(sys.argv) > 2 else ""
    key = key.strip()

    if not key:
        respond_error("empty key")
        return

    mutate(f"kv.{key}", val, scope="plugin")
    log(f"write kv.{key}={val}")

    # Output for downstream port mapping:
    respond_ok("", extra={"outputs": [key]})

if __name__ == "__main__":
    main()
```

#### 3.4.2 ReadKV node (Python)

This node reads `kv.<key>` from plugin config and outputs `val`.

```python
import sys
from lyenv_sdk import read_request, config_plugin, respond_ok, respond_error, log

def main():
    read_request()

    key = sys.argv[1] if len(sys.argv) > 1 else ""
    key = key.strip()
    if not key:
        respond_error("empty key")
        return

    val = config_plugin(f"kv.{key}", "")
    log(f"read kv.{key}={val}")

    respond_ok("", extra={"outputs": [str(val)]})

if __name__ == "__main__":
    main()
```

### 3.5 Run in GUI

Click **Run**, choose the group command, input args: `foo bar`

Expected final output: `bar`

![](gui-run.png)

---

## 4) Multi-output Example (JSON array outputs)

If a node has outputs: `a`, `b`, `c`  
Your node program can just print:

```python
import json
print(json.dumps(["A","B","C"], ensure_ascii=False))
```

The runner maps outputs in order.

> **Tip**: prefer JSON array outputs to avoid space-splitting issues.

---

## 5) Export as Plugin and Verify via CLI

Export the workflow as a plugin from GUI.

Install locally:

```bash
lyenv plugin add /path/to/exported-plugin --name=myflow
```

Run:

```bash
lyenv run myflow run -- foo bar
```

---

## 6) Publishing to the Plugin Center (Release-assets model)

✅ **Commit source only**:

```
plugins/<NAME>/
  manifest.yaml
  scripts/
  config.yaml (optional)
```

❌ **Do NOT commit zip artifacts.**

**PR flow**:

1. Fork the `plugin-center` repo
2. Add/modify `plugins/<NAME>/...`
3. Bump version in `manifest.yaml`
4. Open PR to `main`

After merge, CI will:

- build `<NAME>-<VERSION>.zip`
- upload to GitHub Release assets (tag=`artifacts`)
- update `index.yaml` and open an automatic PR

Merge the index PR to publish.

---

## 7) Troubleshooting

### 7.1 Empty values downstream

- Most common: missing edges
- Ensure `Upstream.output → Downstream.input` connections exist

### 7.2 Node gets wrong input

- Ensure input port names match what you connect
- Ensure one input port has only one incoming edge

### 7.3 Need config access but code fails

- With hybrid runtime you can safely call `read_request()`
- Use `mutate` / `config_plugin` / `log` / `respond_ok(extra={"outputs":[...]})`

---

## 8) Working with Large Plugin Repositories (Partial Clone)

As the plugin-center repository grows, **cloning the entire repository can become slow and unnecessary**, especially when you only want to add or update **one plugin**.

To improve contributor experience, we strongly recommend using **Git partial clone and sparse checkout**.

---

### 8.1 Recommended: Sparse Checkout (Git ≥ 2.25)

This allows you to fetch **only the files you need**.

#### Step 1: Clone without checking out files

```bash
git clone --filter=blob:none --no-checkout https://github.com/<ORG>/<PLUGIN-CENTER-REPO>.git
cd <PLUGIN-CENTER-REPO>
```

#### Step 2: Enable sparse checkout

```bash
git sparse-checkout init --cone
```

#### Step 3: Checkout only what you need

For example, to work on a single plugin:

```bash
git sparse-checkout set plugins/my-plugin
git checkout main
```

Or if you also need the index file:

```bash
git sparse-checkout set plugins/my-plugin index.yaml
git checkout main
```

✅ **Result:**

- Only `plugins/my-plugin/` (and optionally `index.yaml`) are downloaded
- No need to fetch the full repository history or all plugin files

---

### 8.2 Updating an Existing Plugin (Lightweight Workflow)

```bash
git sparse-checkout set plugins/my-plugin
git checkout main
# edit files
git add plugins/my-plugin
git commit -m "Update my-plugin: fix inputs/outputs"
git push origin my-branch
```

Open a Pull Request as usual.

---

### 8.3 Adding a New Plugin (Minimal Files)

When adding a new plugin, only commit source files:

```
plugins/my-plugin/
  manifest.yaml
  scripts/
  config.yaml (optional)
```

❌ **Do NOT commit:**

- zip artifacts
- build outputs
- generated files

Artifacts are built automatically by CI and uploaded as GitHub Release assets.

---

### 8.4 Alternative: Shallow Clone (Less Recommended)

If sparse checkout is not available, you may use a shallow clone:

```bash
git clone --depth=1 https://github.com/<ORG>/<PLUGIN-CENTER-REPO>.git
```

⚠️ This still downloads the full tree and is less efficient than sparse checkout.

---

### 8.5 Why This Matters

Using sparse checkout:

- reduces clone time dramatically
- lowers disk usage
- makes contributing feasible even on slow networks
- scales better as the plugin ecosystem grows

We highly encourage all contributors to adopt this workflow.

---

Thanks again for contributing to lyenv 🚀