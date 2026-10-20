# 队列与批量评测

[English](queues.md) | **简体中文**

[文档导航](README.zh-CN.md) · 前置：[单回合运行](running.zh-CN.md) · 下一步：[查看结果](results.zh-CN.md)

队列将任务、seed 和环境选项写入 JSON，按列表顺序串行执行。每个回合使用新的仿真进程、Codex 会话和输出目录，适合在单回合跑通后扩展评测。

## 1. 从现有配置开始

配置按用途分为 `configs/queues/`（复现评测流程与条件对比）和 `configs/single_task/`（指定单任务，每份恰好 1 个 episode）。两类均由 `gpt-gear queue` 加载，完整清单和单任务示例见[配置说明](../configs/README.zh-CN.md)。

先复制适合你的配置，再修改其中的环境路径。仓库示例使用 `/path/to/...` 环境路径占位符，请全部替换为自己的安装路径；复制到不同目录时也需调整相对路径。以下是队列式配置：

| 配置 | 内容 | 需要调整 |
|---|---|---|
| [libero_plus.json](../configs/queues/libero_plus.json) | LIBERO-plus：任务清单中的 50 个变体，各运行一次 | `env_root`、`sim_python` |
| [robocasa_gr1.json](../configs/queues/robocasa_gr1.json) | GR1：24 任务 × 20 seed | 四项环境路径 |
| [univtac.json](../configs/queues/univtac.json) | UniVTAC：8 任务 × 20 seed，`force` 模式 | `env_root`、`sim_python` |
| [robotwin.json](../configs/queues/robotwin.json) | 50 任务 × 2 种配置 × 5 seed：clean 和 random 均为 `0–4`，共 500 回合 | `env_root`、`sim_python` |
| [robodojo.json](../configs/queues/robodojo.json) | RoboDojo：42 个任务，其中 34 个带参考 | 环境路径及所有参考路径 |

GR1 的四项路径为 `env_root`、`robosuite_root`、`data_root`、`sim_python`。GR1 与 UniVTAC 大队列中的 seed 来自来源项目预设，不代表官方 seed split。

`single_task/` 中的配置执行时也会调用模型；无模型检查见 [运行指南](running.zh-CN.md#无模型接口检查)。参考数据不随仓库提供。

## 2. 检查计划，再执行

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run
gpt-gear summarize outputs/robotwin_queue
```

第一条命令只解析配置并打印计划，不创建回合目录、不启动仿真或模型。计划检查不等于环境预检；首次运行环境仍需执行 `doctor`。

## 3. 编写自己的队列

配置使用 `version: 2`。`environments` 定义命名环境和路径，`episodes` 定义要执行的回合。将下面内容保存为 `configs/queues/my_robotwin_queue.json`，替换路径后运行：

```json
{
  "version": 2,
  "environments": {
    "twin": {
      "benchmark": "robotwin",
      "env_root": "/path/to/RoboTwin",
      "sim_python": "/path/to/robotwin/bin/python"
    }
  },
  "episodes": [
    {"environment": "twin", "task": "adjust_bottle", "seed": 0, "task_config": "clean"},
    {"environment": "twin", "task": "adjust_bottle", "seed": 1, "task_config": "clean"},
    {"environment": "twin", "task": "adjust_bottle", "seed": 0, "task_config": "random"}
  ]
}
```

```bash
gpt-gear queue configs/queues/my_robotwin_queue.json outputs/my_robotwin_queue
gpt-gear queue configs/queues/my_robotwin_queue.json outputs/my_robotwin_queue --run
```

增加命名环境，并在对应 episode 中选择 `environment`，即可组织混合环境队列。

### 路径与参数规则

| 写在哪里 | 规则 |
|---|---|
| JSON 中的路径 | 相对于配置文件所在目录；建议使用绝对路径，不写 `$HOME` 等 shell 变量 |
| 命令行中的路径 | 相对于当前工作目录 |
| seed、初始化选择、预算、模态 | 放在每个 episode 中，使用下划线字段，如 `max_native_steps` |
| 模型、GPU、端口、缓存 | 可通过 `queue` 命令的公共选项指定 |
| 环境选择 | 使用 `benchmark`，命令行没有 `--backend` 别名 |

只有一个命名环境时，可在命令行覆盖两项路径：

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_override \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python --run
```

GR1 的 `robosuite_root` 和 `data_root` 仍需在 JSON 中修改。混合环境队列不要传统一的 `--benchmark`。

### 为回合添加参考

先准备好原始参考文件，再在 episode 内增加 `reference`。例如，下面是一个可放入 `episodes` 的条目：

```json
{
  "environment": "twin",
  "task": "adjust_bottle",
  "seed": 0,
  "task_config": "clean",
  "reference": {
    "video": "/path/to/reference/videos",
    "trajectory": "/path/to/reference/trajectory.json",
    "text": "/path/to/reference/steps.txt",
    "mode": "sequence",
    "fps": 1
  }
}
```

按需提供 `text`、`video`、`trajectory`；轨迹必须搭配文字或视频。无视频时不能指定 `mode`、`fps`。参数指向原始文件，不指向 `reference prepare` 生成的缓存。完整规则见 [参考输入指南](reference-protocol.zh-CN.md)。

新增组合的 `reference` 写法如下（相对路径以队列配置文件所在目录为基准）：

```json
{"text": "/path/to/reference/steps.txt"}
```

```json
{"text": "/path/to/reference/steps.txt", "trajectory": "/path/to/reference/trajectory.json"}
```

```json
{"text": "/path/to/reference/steps.txt", "video": "/path/to/reference/videos"}
```

### 什么算同一个回合

队列通过环境路径、任务、seed 和初始化选择识别回合。GR1 的测量深度开关、UniVTAC 的触觉模式、RoboTwin 的 `task_config` 也参与身份计算。

同一队列不允许重复身份。只改变预算、模型、参考或深度估计声明，不能将同一任务与初始化变成另一条独立回合。比较这些条件时，应分别执行队列并使用不同的输出目录；预算、参考和深度估计声明的差异分别写入各次使用的配置，模型通过各次命令的 `--codex-model` 指定。

## 4. 续跑与重试

继续未跑完的队列，使用原配置和原输出目录再次执行：

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run
```

| 上次状态 | 续跑行为 |
|---|---|
| 尚未开始 | 启动新回合 |
| `success` | 跳过，已完成 |
| `task_failure` | 跳过，已完成一次有效评测 |
| `invalid` / `runtime_error` | 默认跳过；加 `--retry-failed` 才新建尝试 |

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run --retry-failed
```

重试创建新的 `attempt`，从初始状态重新开始，不恢复或重放旧动作。修改队列内容、环境路径或预算后，使用新的输出目录；原输出目录中的配置清单用于核对续跑是否一致。

续跑比对的是解析后的 episode 配置和环境路径，**不包含命令行指定的模型、GPU、端口、缓存或 MCP 解释器**。续跑时请保持这些选项一致；更换模型做对比时使用新的输出目录，程序不会因此自动重跑已完成的回合。

## 5. 查看队列产物

```text
outputs/robotwin_queue/
├── queue.json
├── status.jsonl
└── <回合ID>/
    ├── attempt-0001/
    ├── attempt-0001.queue.log
    └── attempt-0002/          # 如发生重试
```

`summarize` 使用每个回合最新一次尝试，按 benchmark 分组，UniVTAC 另按触觉模式、RoboTwin 另按 Clean / Random 汇总。不跨环境平均原始评分。

旧 v1 配置需要迁移到 v2；旧结果不会被改写，不支持的格式不计入当前成功率。字段含义和排障方法见 [结果指南](results.zh-CN.md)。
