# lyenv —— 基于目录的隔离环境管理器（含可视化工作流 GUI）

**语言：** [English](README.md) | [中文](README_zh.md)  
**平台：** Windows · Linux · Android(Termux)

> 推荐：使用 GUI 编写工作流（Group=命令），GUI 导出为真实插件；CLI 负责安装与运行。

---

## 1. 快速开始

构建：

```bash
make build
make build-gui
```

创建环境：

```bash
lyenv create ./demo
lyenv init ./demo
```

激活：

**Linux/macOS（bash/zsh）**

```bash
eval "$(lyenv activate)"
```

**Windows PowerShell**

```powershell
lyenv activate | Invoke-Expression
```

---

## 2. 安装/卸载（无需源码）

`lyenv install` 会安装 `lyenv` + `lyenv-gui`：

- 优先系统目录（如 `/usr/local/bin`、Termux `$PREFIX/bin`）
- 无权限则回退 `~/.local/bin`
- Windows 不自动写 PATH（需手动把安装目录加入 PATH）

```bash
lyenv install
lyenv uninstall
```

---

## 3. GUI（推荐）

启动：

```bash
lyenv gui start --open
```

注册环境给 GUI：

```bash
lyenv gui add ./demo --name=demo
```

GUI 使用方式：

- 画流程（Start → ... → End）
- 用 Group 包起来：一个 Group = 一个命令
- 点击 Run 选择 Group → 输入参数 → 自动导出/安装/运行/实时日志/清理
- 发布前可 Export 导出插件 zip

---

## 4. 插件安装（支持版本）

```bash
# 最新
lyenv plugin install tester --name=tester

# 指定版本
lyenv plugin install tester --version=0.1.0 --name=tester

# 语法糖
lyenv plugin install tester@0.1.0 --name=tester
```

---

## 5. 发布插件到中心（开发者）

中心仓库模式：

- 源码提交到 `plugins/<NAME>/`
- CI 打包 zip 并上传到 GitHub Release assets（tag=`artifacts`），并更新 `index.yaml` 2 3

流程：

1. PR 只提交源码到 `plugins/<NAME>/`
2. 合并后 CI 自动上传 zip 并开 PR 更新 `index.yaml`
3. 合并 `index.yaml` PR 后生效

详细见：[CONTRIBUTING.md](CONTRIBUTING.md)

---

## 6. License

见 [LICENSE](LICENSE)
