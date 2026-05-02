# kade — Android Kernel Driver Builder Plugin

[中文](#中文) | [English](#english)

---

## 中文

### 1. 简介

**kade** 是一个基于 **lyenv stdio 插件机制** 的内核构建工具插件，支持：

- **GKI**：repo 同步、驱动集成（drivers/Makefile + modules 列表）、Bazel/legacy 构建、导出 compile_commands、ABI 列表写入/上游 ABI 修补。
- **non-GKI**：源码获取（repo/local/zip），**按用户配置**直接构建（script 或可选 make 模式），导出 compile_commands。
- 工具命令：依赖安装、清理构建缓存、导出产物、镜像（boot/vendor_boot/system）解包/回包辅助。

> 设计原则：**稳定、可维护、可配置**。参数从 `lyenv_sdk.args()` 获取，不依赖 `sys.argv`。

---

### 2. 功能列表

- **prepare**：读取配置 + 推断派生路径（workspace/source_dir 等）
- **sync**：同步源码  
  - GKI：`repo init` + `repo sync`（含心跳日志）  
  - non-GKI：repo/local/zip（zip 支持自动剥离顶层目录）
- **build**：构建  
  - GKI：驱动集成 + 模块列表更新 + legacy/bazel 构建（支持 Bazel 自定义参数如 `--config=fast`）  
  - non-GKI：不做额外处理，按用户配置直接构建
- **compile_commands**：导出 `compile_commands.json`  
  - GKI：`tools/bazel run //common:kernel_${ARCH}_compile_commands`  
  - non-GKI：`gen_compile_commands.py -d <out_dir>`（若内核树缺脚本则回退到插件自带脚本）
- **abi**：向 ABI 列表文件追加/替换符号（GKI only）
- **abi_upstream**：上游 ABI 修补（GKI only）  
  - 注释 `build/kernel/abi/symbols.deny` 全部行  
  - 将 `common/BUILD.bazel` 中 `kmi_symbol_list_strict_mode` 强制改为 `False`
- **deps**：安装依赖（默认 apt）
- **clean**：清理构建缓存（安全模式：仅清理 workspace/source_dir 下的路径）
- **export**：导出编译产物（copy 或 tar.gz）
- **img**：boot/vendor_boot/system 镜像处理（解包/回包、ramdisk lz4+cpio）

---

### 3. 环境要求

- Python 3
- Linux / WSL（推荐）
- GKI：需要网络访问（repo sync），并需要 `git`、`curl` 等基础命令
- non-GKI zip 解包：需要 `zip` / `unzip`，以及 `lz4`、`cpio`（用于 ramdisk）
- 可选：`simg2img`（用于 system.img sparse 转 raw）

> 你也可以直接使用：`kade deps`（apt 环境）安装常用依赖。

---

### 4. 安装与运行

1) 将插件目录放到任意位置（例如 `~/kade`）。  
2) 确保 `kade.yaml` 与 `config.yaml` 位于插件根目录。  
3) lyenv 加载插件后即可使用 `kade <command>` 运行。

---

### 5. 配置

插件默认读取 `config.yaml`。你可以编辑该文件来切换 GKI / non-GKI、设置源码来源、设置构建参数等。

常用最小配置示例：

#### GKI 最小配置

```yaml
kernel:
  flavor: "gki"

gki:
  android_version: 14
  kernel_version: "6.1"
  target_arch: "aarch64"

  driver:
    project_name: "mydriver"
    in_tree: true
    module_name: "mydriver.ko"

  build:
    bazel:
      args: ["--config=fast"]
```

#### non-GKI repo 最小配置（script 模式）

```yaml
kernel:
  flavor: "non_gki"

non_gki:
  source:
    type: "repo"
    repo_url: "https://github.com/your/kernel.git"
    branch: "main"
  build:
    mode: "script"
    script: "build.sh"
    args: []
```

#### non-GKI zip 配置（自动剥离 zip 顶层目录）

```yaml
kernel:
  flavor: "non_gki"

non_gki:
  source:
    type: "zip"
    zip_path: "/path/to/kernel.zip"
    zip_strip_root: true
  build:
    mode: "script"
    script: "build.sh"
```

---

### 6. 命令

以下命令均以 `kade <command> [args...]` 形式调用：

#### 6.1 prepare

准备环境，推断派生路径：

```bash
kade prepare
```

#### 6.2 sync

同步源码：

```bash
kade sync
```

#### 6.3 build

构建：

```bash
kade build
```

#### 6.4 compile_commands

导出 `compile_commands.json`：

```bash
kade compile_commands
```

#### 6.5 abi（GKI only）

写入 ABI 符号列表（参数来自 lyenv request args）：

```bash
kade abi register_kprobe unregister_kprobe
kade abi --file symbols.txt
kade abi --replace --file symbols.txt
kade abi --sort --file symbols.txt
```

#### 6.6 abi_upstream（GKI only）

修补上游 ABI 限制：

```bash
kade abi_upstream
```

#### 6.7 deps（apt）

安装依赖（默认使用 sudo）：

```bash
kade deps
```

#### 6.8 clean

清理构建缓存/产物：

```bash
kade clean
```

#### 6.9 export

导出构建产物到 `export.dest_dir`（默认 `workspace/exports/时间戳`）：

```bash
kade export
```

#### 6.10 img

镜像工具：

```bash
kade img unpack boot.img --out /tmp/boot_out
kade img extract-ramdisk ramdisk.cpio.lz4 --out /tmp/ramdisk_out
kade img pack-ramdisk /tmp/ramdisk_out --out /tmp/build.cpio.lz4
kade img repack boot.img /tmp/boot_out --out /tmp/new_boot.img -- --any-extra-args
```

#### 6.11 driver

管理内核驱动项目：

```bash
# 添加一个驱动
kade driver add --name <项目名> [--module <模块.ko>] [--src <外部源码目录>]

# 重命名已有驱动
kade driver rename <旧项目名> <新项目名>
```


---

### 7. 推荐工作流

#### GKI

```bash
kade prepare
kade sync
kade abi_upstream          # 可选：需要放开上游限制时
kade abi --file symbols.txt # 可选：按需写入符号
kade build
kade export
kade compile_commands
```

#### non-GKI

```bash
kade prepare
kade sync
kade build                 # 由用户脚本或 make 模式决定
kade export
kade compile_commands
```

---

### 8. 常见问题

**参数拿不到 / sys.argv 为空**  
本插件所有命令应使用 `lyenv_sdk.args()` 获取参数，避免 `sys.argv` 在插件 runtime 下不一致的问题。

**zip 解压后多了一层目录**  
设置 `non_gki.source.zip_strip_root: true`（默认启用），自动剥离顶层目录。

**non-GKI 没有 build.sh**  
这是预期行为：non-GKI 构建完全交给用户配置。请在 `non_gki.build.script` 指定构建脚本路径。

**compile_commands 缺少 gen_compile_commands.py**  
non-GKI 会优先使用内核树内的脚本，不存在时自动使用插件自带 fallback 脚本（可在 config 中设置路径）。

---

### 9. 开发说明

推荐结构：

```
scripts/
  lib/            # shared helper modules
  cmd_*.py        # commands entrypoints
```

每个命令脚本都应：

- 使用 `read_request()` 读取请求
- 使用 `config_plugin()` / `cfg()` 读取配置
- 使用 `args()` 获取参数
- 使用 `log()` 输出过程日志（长任务建议心跳）
- 以 `respond_ok()` / `respond_error()` 输出最终结果

---

### 10. License

由项目维护者自行指定 License。

---

## English

### 1. Overview

**kade** is a lyenv stdio plugin for kernel workflows, supporting:

- **GKI**: repo sync, driver integration (Makefile + module list), Bazel/legacy builds, compile_commands export, ABI list editing and upstream ABI patching.
- **non-GKI**: source fetch (repo/local/zip), build via user-configured script (or optional make mode), compile_commands export.
- **Utilities**: dependency installation, build cache cleanup, artifact export, image (boot/vendor_boot/system) unpack/repack helpers.

> Design goal: **stable, maintainable, and configurable**. Arguments are read from `lyenv_sdk.args()` (not `sys.argv`).

---

### 2. Features

- **prepare**: load config and derive paths (workspace/source_dir, etc.)
- **sync**:
  - GKI: `repo init` + `repo sync` (with heartbeat logs)
  - non-GKI: repo/local/zip (zip supports top-level folder stripping)
- **build**:
  - GKI: integrate driver + update module lists + legacy/bazel build (supports custom Bazel args, e.g. `--config=fast`)
  - non-GKI: run exactly what user configured (script/make mode)
- **compile_commands**:
  - GKI: `tools/bazel run //common:kernel_${ARCH}_compile_commands`
  - non-GKI: `gen_compile_commands.py -d <out_dir>` with fallback script shipped in plugin
- **abi** (GKI only): append/replace ABI symbols into ABI list file
- **abi_upstream** (GKI only): patch upstream ABI settings:
  - comment out all lines in `build/kernel/abi/symbols.deny`
  - set `kmi_symbol_list_strict_mode = False` in `common/BUILD.bazel`
- **deps**: install dependencies (apt)
- **clean**: remove build outputs/caches (safe-only mode)
- **export**: copy/archive build artifacts to a destination directory
- **img**: boot/vendor_boot/system image helpers (unpack/repack, ramdisk lz4+cpio)

---

### 3. Requirements

- Python 3
- Linux / WSL recommended
- GKI: network access for repo sync and basic tools (git, curl, etc.)
- Zip/ramdisk: unzip, lz4, cpio
- Optional: simg2img for sparse system.img conversion

---

### 4. Installation

1. Place plugin directory anywhere (e.g. `~/kade`).
2. Ensure `kade.yaml` and `config.yaml` exist in plugin root.
3. Load plugin via lyenv, then run `kade <command>`.

---

### 5. Configuration

Edit `config.yaml` to switch GKI/non-GKI and tune build parameters.

Minimal examples:

#### Minimal GKI

```yaml
kernel:
  flavor: "gki"

gki:
  android_version: 14
  kernel_version: "6.1"
  target_arch: "aarch64"
  driver:
    project_name: "mydriver"
    in_tree: true
    module_name: "mydriver.ko"
  build:
    bazel:
      args: ["--config=fast"]
```

#### Minimal non-GKI (repo + script)

```yaml
kernel:
  flavor: "non_gki"

non_gki:
  source:
    type: "repo"
    repo_url: "https://github.com/your/kernel.git"
    branch: "main"
  build:
    mode: "script"
    script: "build.sh"
```

---

### 6. Commands

All commands are invoked as `kade <command> [args...]`:

#### 6.1 prepare

```bash
kade prepare
```

#### 6.2 sync

```bash
kade sync
```

#### 6.3 build

```bash
kade build
```

#### 6.4 compile_commands

```bash
kade compile_commands
```

#### 6.5 abi (GKI only)

```bash
kade abi <symbols...> | --file symbols.txt | --replace --file symbols.txt | --sort --file symbols.txt
```

#### 6.6 abi_upstream (GKI only)

```bash
kade abi_upstream
```

#### 6.7 deps (apt)

```bash
kade deps
```

#### 6.8 clean

```bash
kade clean
```

#### 6.9 export

```bash
kade export
```

#### 6.10 img

```bash
kade img unpack boot.img --out /tmp/boot_out
kade img extract-ramdisk ramdisk.cpio.lz4 --out /tmp/ramdisk_out
kade img pack-ramdisk /tmp/ramdisk_out --out /tmp/build.cpio.lz4
kade img repack boot.img /tmp/boot_out --out /tmp/new_boot.img -- --any-extra-args
```
#### 6.11 driver

Manage kernel driver projects:

```bash
# Add a driver
kade driver add --name <project> [--module <module.ko>] [--src <external_source>]

# Rename an existing driver
kade driver rename <old_name> <new_name>
```

---

### 7. Suggested Workflows

#### GKI

```bash
kade prepare
kade sync
kade abi_upstream           # optional
kade abi --file symbols.txt # optional
kade build
kade export
kade compile_commands
```

#### non-GKI

```bash
kade prepare
kade sync
kade build
kade export
kade compile_commands
```

---

### 8. Troubleshooting

**Args missing / sys.argv empty**  
Always use `lyenv_sdk.args()`.

**Zip has extra top folder**  
Enable `non_gki.source.zip_strip_root: true`.

**non-GKI build script missing**  
Expected; user must set `non_gki.build.script`.

**Missing gen_compile_commands.py**  
non-GKI uses fallback script shipped by plugin if the kernel tree does not provide one.

---

### 9. Development Notes

Recommended layout:

```
scripts/
  lib/
  cmd_*.py
```

Each command should:

- `read_request()` first
- read configs via `config_plugin()` / helper `cfg()`
- read arguments via `args()`
- stream logs via `log()` (use heartbeat for long tasks)
- end with `respond_ok()` or `respond_error()`

---

### 10. License

To be defined by the repository owner.