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

参考轨迹格式为 `libero-codex-trajectory-v1`，控制点为 `robot0_grip_site`。视频视角和动作字段见 [参考协议](../reference-protocol.zh-CN.md#libero-plus)，文字生成见 [视频文字教程](../reference-format.zh-CN.md)。

[单任务配置](../../configs/single_task/libero_plus.json) 使用 `libero_spatial/0`。[队列配置](../../configs/queues/libero_plus.json) 包含 5 个基础任务的 50 个变体，每项使用 seed 0、init state 0 和 600 个原生步，不带参考；完整任务标识与执行顺序以配置中的 `episodes` 为准。执行与续跑步骤见 [队列指南](../queues.zh-CN.md)。
