## 中文指南

### 1. 概述
**lyenv** 是一个基于目录的环境管理器，为插件提供统一的安装、配置、执行与日志框架。  

- **环境目录结构**（由 `lyenv create/init` 创建）：

```
ENV_ROOT/
├─ bin/                         # 插件 shim 可执行（例如 andctl）
├─ plugins/                     # 插件安装位置（每个插件一个目录）
│  └─ <INSTALL_NAME>/
│     ├─ manifest.yaml|yml|json # 插件清单（必须）
│     ├─ config.yaml|json       # 插件私有配置（可选，推荐）
│     ├─ scripts/               # 插件脚本（bash/python 等）
│     └─ logs/YYYY-MM-DD/       # 插件命令日志（核心自动写入）
├─ workspace/                   # 工作区（由插件自由使用）
└─ .lyenv/
   ├─ logs/dispatch.log         # 全局调度日志（核心自动写入）
   └─ registry/installed.yaml   # 已安装插件注册表（核心写入）
```

- **关键理念**：  
  1) **Manifest 驱动**：每个插件必须提供清单，声明命令与执行方式。  
  2) **Executor 两类**：  
     - `shell`：适合只打印日志、不返回结构化数据；核心以 `bash -c` 执行。  
     - `stdio`：推荐；通过 **stdin/stdout 交换 JSON**，返回结构化结果与 **mutations**（由核心安全合并）。  
  3) **参数传递统一**：  
     - `shell`：`args` 与命令行 `-- ...args` 会被拼接到命令行尾部。  
     - `stdio`：命令行 `-- ...args` 出现在请求 JSON 的 `args` 字段内。  
  4) **工作目录**：默认是插件根目录，可用 `workdir` 重设为插件子目录或绝对路径。  
  5) **配置合并**：`stdio` 的响应 `mutations` 会安全合并到：  
     - 全局配置 `lyenv.yaml`（由核心管理）、  
     - 插件私有配置 `plugins/<INSTALL_NAME>/config.yaml|json`（保持原格式）。  
  6) **日志标准化**：插件命令日志为 JSON Lines，路径稳定、易回放。

---

### 2. Manifest 规范

#### 2.1 最小模板（YAML）
```yaml
name: myplugin
version: 0.1.0
expose: [myctl]              # 将生成 ENV_ROOT/bin/myctl shim

config:
  local_file: ./config.yaml  # 插件私有配置文件路径（建议）

commands:
  - name: run
    summary: Example stdio command
    executor: stdio
    program: ./main.py       # 可执行脚本（建议 LF 行尾 + chmod +x）
    use_stdio: true
    workdir: .
```

#### 2.2 字段说明

- `name`：逻辑名（仅显示，不用于目录）；安装名（INSTALL_NAME）用于实际目录与运行。
- `version`：插件版本（建议 SemVer）。
- `expose[]`：shim 别名列表；例如 `myctl` -> `ENV_ROOT/bin/myctl`。
- `config.local_file`：插件私有配置文件（相对插件根），支持 `.yaml/.json`，核心会按扩展保持原格式。
- `commands[]`：命令清单：
  - `executor`: `shell` 或 `stdio`。
  - `program`: 系统命令（如 `python3`）或插件内相对路径（如 `./main.py`）。
  - `args[]`: 固定参数；用户调用时的 `-- ...args` 会附加传入。
  - `workdir`: 运行时工作目录。
  - `env`: 注入子进程的环境变量键值对。
  - `use_stdio`: stdio 标记。
  - `steps[]`: 多步骤（shell/stdio 混合），每步可用 `continue_on_error` 控制容错；结合 `lyenv run` 的 `--fail-fast/--keep-going`。

---

### 3. 执行器与参数传递

#### 3.1 shell 执行器
- 核心执行：`bash -c "<program + args + passArgs>"`。
- 用途：简单命令，不需要返回 JSON 结构。
- 示例：
  ```yaml
  commands:
    - name: hello
      summary: Say hello from shell
      executor: shell
      program: echo "hello"
      args: ["from", "shell"]  # 最终命令行：echo "hello" from shell <passArgs...>
  ```

#### 3.2 stdio 执行器（推荐）
- 核心将**请求 JSON**写入子进程 stdin，期望子进程从 stdout 返回**响应 JSON**。
- 请求示例：
  ```json
  {
    "action": "run",
    "args": ["--DRIVER=mydriver"],
    "paths": {
      "home": "/env",
      "bin": "/env/bin",
      "workspace": "/env/workspace",
      "plugin_dir": "/env/plugins/myplugin"
    },
    "system": {"os":"linux","arch":"amd64"},
    "config": {
      "global": { /* lyenv.yaml 内容 */ },
      "plugin": { /* plugins/myplugin/config.yaml/json 内容 */ }
    },
    "merge_strategy": "override",
    "started_at": "2026-01-01T12:30:00Z"
  }
  ```
- 响应示例：
  ```json
  {
    "status": "ok",
    "logs": ["hello", "driver=mydriver"],
    "artifacts": ["/env/workspace/out/dist"],
    "mutations": {
      "plugin": {"status":{"last_run_at":"2026-01-01T12:30:00Z"}},
      "global": {"android":{"kernel_branch":"common-android14-6.1"}}
    }
  }
  ```
- `mutations` 合并：核心按策略（`override`/`append`/`keep`）自动合并到 `lyenv.yaml` 与插件私有配置。

---

### 4. 插件目录与脚本规范

#### 4.1 目录位置
插件安装后必须位于：`ENV_ROOT/plugins/<INSTALL_NAME>/`。  
Manifest 必须在插件根目录；脚本与配置也应在插件目录内。

#### 4.2 脚本要求
- LF 行尾；shebang 正确（如 `#!/usr/bin/env python3`）。
- 可执行位（`chmod +x`）对于直接执行的脚本必需。
- 不依赖 `awk -i inplace`（在 macOS/BSD 下不可用）。使用**临时文件 + sed/python**的跨平台写法。

#### 4.3 示例：STDIO Python 脚本
```python
#!/usr/bin/env python3
# Reads request JSON from stdin; prints response JSON to stdout.
import sys, json, time

def main():
    req = json.load(sys.stdin)
    args = req.get("args") or []
    plugin_cfg = req.get("config", {}).get("plugin", {}) or {}
    drv = plugin_cfg.get("driver", {}).get("name", "mydriver")

    resp = {
        "status": "ok",
        "logs": [f"stdio: driver={drv}", f"stdio: args={args}"],
        "artifacts": [],
        "mutations": {"plugin":{"status":{"last_run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}}},
    }
    print(json.dumps(resp))

if __name__ == "__main__":
    main()
```

---

### 5. 安装与运行（用户流程）
```bash
# 1) 创建与激活环境
lyenv create ./env
lyenv init ./env
cd ./env
eval "$(lyenv activate)"

# 2) 安装本地插件目录（开发阶段）
lyenv plugin add ./plugins/myplugin --name=myplugin

# 3) 运行命令（shim 或核心）
myctl run
# 或：
lyenv run myplugin run -- --DRIVER=mydriver
```

Shim 行为：在 `ENV_ROOT/bin/` 生成 `myctl`，通常执行 `lyenv run myplugin "$@"`。  
在 CI 中若 PATH 中没有 `lyenv`，建议 shim 优先使用环境变量：

```bash
#!/usr/bin/env bash
set -euo pipefail
exec "${LYENV_BIN:-lyenv}" run myplugin "$@"
```

---

### 6. 插件中心（统一分发）

#### 6.1 Monorepo 结构
```
plugin-center/
├─ plugins/
│  ├─ demo/
│  │  ├─ manifest.yaml
│  │  ├─ main.py
│  │  └─ config.yaml
│  └─ another-plugin/
│     └─ ...
└─ index.yaml  # 自动生成；记录每个插件的 repo/subpath/ref 或 artifacts 的 source+sha256
```

#### 6.2 index.yaml 示例
```yaml
apiVersion: v1
updatedAt: 2026-01-01T12:00:00Z
plugins:
  demo:
    desc: "Demo stdio plugin"
    repo: "YOUR_ORG/plugin-center"
    subpath: "plugins/demo"
    ref: "main"
    shims: ["democtl"]
    versions:
      "0.1.0":
        # 归档分发（优先解析；含 sha256 完整性校验）
        source: "https://raw.githubusercontent.com/YOUR_ORG/plugin-center/main/artifacts/demo-0.1.0.zip"
        sha256: "<64-hex>"
        shims: ["democtl"]
```

客户端：`lyenv plugin install demo --name=demo`  
若 `source+sha256` 存在 → 下载 ZIP、校验 SHA‑256、解压安装。  
否则 → 以 `repo+subpath+ref` 方式克隆子目录安装。

---

### 7. 多步骤命令、超时与错误策略
Manifest 支持 `steps[]` 多步骤（shell/stdio 混合），每步可设置 `continue_on_error`。  
运行时支持：
- `--timeout=<sec>`（全局超时，使用 `exec.CommandContext`）。
- `--fail-fast`（遇到错误立即终止）。
- `--keep-going`（遇到错误继续后续步骤）。

---

### 8. 配置合并策略（Mutations）
- `override`：键值覆盖（适用于时间戳、派生字段）。
- `append`：列表追加（适用于队列、工件列表）。
- `keep`：仅在目标无值时写入（适用于默认值注入）。

插件通过 stdio 响应返回 `mutations`，核心按策略安全合并到 `lyenv.yaml` 与插件私有配置。

---

### 9. 日志与调度
- 插件日志路径：`plugins/<INSTALL_NAME>/logs/YYYY-MM-DD/<COMMAND>-<TIMESTAMP>.log`（JSON Lines）。
- 全局调度日志：`.lyenv/logs/dispatch.log`。
- 建议在 stdio 中输出 `debug` 字段（如最终 entry/args/workdir/envPATH），便于定位环境差异。

---

### 10. CI：自动生成索引与归档（含 SHA‑256）
中心仓库工作流：
1. 扫描 `plugins/<NAME>` → 生成 `artifacts/<NAME>-<VERSION>.zip`。
2. 计算 `sha256` → 更新 `index.yaml` 的 `versions[x].sha256`。
3. 以 PAT Secret 创建 PR（合并后 raw URL 可用）。

客户端安装时自动校验归档的 SHA‑256。

---

### 11. 常见问题与排错
- **目录误解**：插件必须安装到 `ENV_ROOT/plugins/<INSTALL_NAME>/`；Manifest 在插件根。
- **参数拿不到**：
  - `shell`：命令行 `-- ...args` 拼接到命令行尾部，用 `$1 $2 ...` 接收。
  - `stdio`：在请求 JSON `args` 中读取。
- **配置无法解析**：不要到随机路径写配置；使用 `config.local_file`，通过 `mutations` 合并状态。
- **shebang/行尾**：确保 LF 行尾与可执行位；`python3` 在 PATH。
- **awk -i inplace**：不可移植；使用**临时文件 + sed/python**。
- **找不到 lyenv**：shim 优先 `LYENV_BIN`；在 CI 将 `dist/` 加入 PATH。
- **超时与策略**：`--timeout`、`--fail-fast/--keep-going` 控制多步骤；不要在脚本内自行实现不一致的超时。

---

### 12. 作者清单（制作流程）
- [ ] 在本地创建 `plugins/<NAME>/`。
- [ ] 编写 `manifest.yaml|json`（至少一个命令；推荐 `stdio`）。
- [ ] 编写脚本（英文注释；LF 行尾；可执行位；不使用 `awk -i inplace`）。
- [ ] 准备 `config.yaml|json`（建议）。
- [ ] 本地安装测试：`lyenv plugin add ./plugins/<NAME> --name=<INSTALL_NAME>`。
- [ ] 运行测试：`lyenv run <INSTALL_NAME> <COMMAND> -- ...args`；检查日志与 `mutations`。
- [ ] 推送到中心：`plugins/<NAME>`；合并 PR 自动生成 `index.yaml` 与归档。
- [ ] 客户端验证：`lyenv plugin install <NAME> --name=<INSTALL_NAME>`。

---