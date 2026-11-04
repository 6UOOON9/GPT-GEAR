# LIBERO-plus 环境配置

[English](libero-plus.md) | **简体中文**

[文档导航](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#libero-plus) · [队列评测](../queues.zh-CN.md)

LIBERO-plus 提供单臂操作、双视角 RGB 和多种任务变体。本页说明源码、任务编号和初始化选项；公共运行流程见 [运行指南](../running.zh-CN.md)。

## 源码与资产

使用已安装的 LIBERO-plus 源码与配套仿真 Python，`--env-root` 指向 LIBERO-plus 目录。源码下的 `libero/libero/assets`、`bddl_files` 和 `init_files` 目录均须就绪。仿真可使用已有 Python 3.10 环境，保留其依赖配置。

每个回合生成独立的 `libero_config/config.yaml`，通过子进程的 `LIBERO_CONFIG_PATH` 使用，不修改全局 `~/.libero/config.yaml`。

## 任务与观测选项

| 参数或能力 | 默认值与语义 |
|---|---|
| 任务 | `suite/task_id`，如 `libero_spatial/0`，编号从 0 开始 |
| 初始化 | `--seed 0 --init-state-index 0` |
| 观测 | agentview / robot0_eye_in_hand RGB 与单臂状态；`--image-size 256` |
| 预算 | `--max-native-steps 600`，包含 10 个稳定初始化步；最小值为 11 |
| 控制频率 | 20 Hz |
| 深度 | 默认开启模型深度估计声明；`--depth-estimation false` 关闭，不提供测量深度 |

`--init-state-index` 选择任务的初始化状态；任务变体名称中的 `initstate_N` 不作为该参数。LIBERO-plus 不接受 `--layout-id`。首次运行可先做 [无模型接口检查](../running.zh-CN.md#无模型接口检查)。

## 参考与评测配置

参考轨迹格式为 `libero-codex-trajectory-v1`，控制点为 `robot0_grip_site`。视频视角和动作字段见 [上下文学习指南](../reference-protocol.zh-CN.md#libero-plus)，文字生成见 [视频文字教程](../reference-format.zh-CN.md)。

[单任务配置](../../configs/single_task/libero_plus.json) 使用 `libero_spatial/0`。[队列配置](../../configs/queues/libero_plus.json) 包含 5 个基础任务的 50 个变体，每项使用 seed 0、init state 0 和 600 个原生步，并按基础任务配置视频、文字和轨迹参考（`sequence`、1 fps）。运行前将 `/path/to/reference_demo` 替换为本机示范根目录；完整任务标识与执行顺序以配置中的 `episodes` 为准。执行与续跑步骤见 [队列指南](../queues.zh-CN.md)。

参考示范集包含 40 份 LIBERO-Plus 基础任务示范，下载方法见[示范下载指南](../reference-protocol.zh-CN.md#download-reference-demo)。`/path/to/reference_demo/LIBERO-Plus/` 下的目录对应关系如下：

| 示范目录 | Suite | 数量 |
|---|---|---:|
| `base_00`–`base_09` | `libero_spatial` | 10 |
| `base_10`–`base_19` | `libero_object` | 10 |
| `base_20`–`base_29` | `libero_goal` | 10 |
| `base_30`–`base_39` | `libero_10` | 10 |

先确定变体所属的基础任务，再选择示范。`base_XX` 是示范编号，不是 `suite/task_id`。例如，`libero_goal/0` 属于 `open_the_middle_drawer_of_the_cabinet`，对应 `base_20`；同一基础任务的其他变体也使用这份参考：

```json
"reference": {
  "video": "/path/to/reference_demo/LIBERO-Plus/base_20/videos",
  "trajectory": "/path/to/reference_demo/LIBERO-Plus/base_20/trajectory.json",
  "text": "/path/to/reference_demo/LIBERO-Plus/base_20/steps.txt",
  "mode": "sequence",
  "fps": 1
}
```

每份示范包含外部视角（`agentview`）和腕部视角（`robot0_eye_in_hand`）视频、文字步骤及动作轨迹。请保留完整目录，包括 `trajectory.jsonl` 和 `videos/videos.json`。

运行仓库队列前，将 JSON 中的 `env_root`、`sim_python` 和所有 `/path/to/reference_demo` 前缀替换为本机绝对路径。`--env-root` 只覆盖仿真环境路径，不会修改 reference 路径。然后检查计划并执行：

```bash
gpt-gear queue configs/queues/libero_plus.json outputs/libero_plus_reference
gpt-gear queue configs/queues/libero_plus.json outputs/libero_plus_reference --run
```

第一条命令只打印执行计划。如果此前运行过不带参考的队列，本次带参考运行请使用新的输出目录。每份 queue JSON 均可独立分发；接收者修改路径后，可直接用 `gpt-gear queue <config.json> <输出目录> --run` 执行自己的文件。
