# lyenv 贡献指南（插件 + GUI 工作流）

欢迎你为 **lyenv** 贡献代码或插件！

本文档介绍：
- 如何使用 **GUI（推荐）** 编写插件
- 节点之间 **数据是如何流动的**
- 如何导出为标准插件并用 CLI 验证
- 如何 **不借助 GUI 直接编写插件**
- 如何发布到 **插件中心**

---

## 0）快速术语说明

**环境（env）**  
由 `lyenv create/init` 创建的目录，包含：
`bin/ plugins/ workspace/ .lyenv/ lyenv.yaml`

**插件（Plugin）**  
位于 `env/plugins/<INSTALL_NAME>/` 的目录。

**工作流（Workflow）**  
GUI 中的节点 + 连线图，导出后即为插件。

**Group（组）**  
GUI 中一个 Group 对应插件里的一个命令。
> **一个 Group = 一个命令**

**端口（Ports）**  
节点通过端口交换数据：
- 输出端口：产生数据
- 输入端口：消费数据

---

## 1）推荐方式：使用 GUI 编写插件（Workflow 优先）

lyenv 的 GUI **不是另一个运行时**，  
而是一个 **工作流 → 插件 的可视化编译器**。

---

### 1.1 环境准备

```bash
lyenv create ./demo
lyenv init ./demo
cd ./demo
```

**激活环境：**  
Linux/macOS  
```bash
eval "$(lyenv activate)"
```
Windows PowerShell  
```powershell
lyenv activate | Invoke-Expression
```

**启动 GUI 并注册环境：**  
```bash
lyenv gui start --open
lyenv gui add . --name=demo
```

---

### 1.2 工作流整体结构

> Put picture here

最小工作流结构：  
`Start` → `Node` → `End`

- `Start`：接收命令行参数
- `Node`：执行实际程序
- `End`：输出最终结果

---

### 1.3 端口与数据流（非常重要）

> Put picture here

示例连线：  
`Start.name → Greet.name`  
`Greet.greeting → End.greeting`

运行时流程：
- Start 将 CLI 参数映射到输出端口
- 下游节点通过 wiring 读取数据
- 节点执行程序
- 输出写回 wiring
- End 生成最终结果

⚠️ 未连接的端口会得到空值

---

## 2）GUI 测试案例：Hello, <name>!

期望输出：  
```
Hello, Alice!
```

### 2.1 创建节点

创建 3 个节点：
- `Start`
- 普通节点（命名为 `Greet`）
- `End`

### 2.2 定义端口

**Start：**
- 输出端口：`name`

**Greet：**
- 输入端口：`name`
- 输出端口：`greeting`

**End：**
- 输入端口：`greeting`

### 2.3 连接节点
- `Start.name` → `Greet.name`
- `Greet.greeting` → `End.greeting`

### 2.4 配置 Greet 节点程序

示例 Python 逻辑：
```python
import sys
name = sys.argv[1] if len(sys.argv) > 1 else "world"
print(f"Hello, {name}!")
```

说明：
- 不要写死 `python3`
- 导出的 runner 会使用 `sys.executable`，自动适配 Windows/Linux

### 2.5 创建 Group（一个 Group = 一个命令）

把 Start / Greet / End 放入同一个 Group，命名为 `run`。

### 2.6 在 GUI 中运行

> Put picture here

运行步骤：
1. 点击 `Run`
2. 选择 Group：`run`
3. 输入参数：`Alice`

最终输出：
```
Hello, Alice!
```

---

## 3）导出为插件并用 CLI 验证

> Put picture here

导出插件后：
```bash
lyenv plugin add /path/to/exported-plugin --name=hello-demo
lyenv run hello-demo run -- Alice
```

---

## 4）不使用 GUI 直接编写插件（进阶）

GUI 推荐，但也支持手写插件。

### 4.1 最小结构

```
plugins/<NAME>/
├─ manifest.yaml
├─ scripts/main.py
└─ config.yaml（可选）
```

### 4.2 `manifest.yaml` 示例

```yaml
name: hello-cli
version: 0.1.0
expose: [run]

commands:
  - name: run
    executor: stdio
    program: ./scripts/main.py
```

### 4.3 `stdio` 脚本示例

```python
from lyenv_sdk import read_request, respond_ok

req = read_request()
args = req.get("args", [])
name = args[0] if args else "world"
respond_ok(f"Hello, {name}!")
```

---

## 5）发布到插件中心

✅ **只提交源码：**
```
plugins/<NAME>/
  manifest.yaml
  scripts/
  config.yaml（可选）
```

❌ **不提交 zip。**

**PR 流程：**
1. Fork 插件中心仓库
2. 添加/修改 `plugins/<NAME>/...`
3. 在 `manifest.yaml` 中升级版本号
4. 向 `main` 分支发起 PR

合并后 CI 会：
- 打包 `<NAME>-<VERSION>.zip`
- 作为 GitHub Release 附件上传（tag=artifacts）
- 更新 `index.yaml`
- 自动创建一个 PR

合并该 PR 即可完成发布。

---

## 6）常见问题

| 问题 | 解决方法 |
|------|----------|
| `node failed` | 查看 `scripts/runner_<NODE>.py`<br>查看 GUI 日志中的 stderr |
| **Windows 问题** | 确保 Python 已安装<br>使用 `sys.executable`<br>避免 Linux-only 命令 |
| **数据为空** | 多半是端口没连好<br>检查端口名是否一致 |

---

## 7）风格与可移植性建议

- [ ] 使用 LF 行尾
- [ ] 避免平台相关命令
- [ ] Python 节点优先 `sys.executable`
- [ ] 尽量无状态
- [ ] 用 GUI 验证 wiring

感谢你为 lyenv 做出贡献 🚀
