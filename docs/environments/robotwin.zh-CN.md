# RoboTwin 环境配置

[English](robotwin.md) | **简体中文**

[文档导航](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#robotwin) · [队列评测](../queues.zh-CN.md)

RoboTwin 提供双臂操作、三视角 RGB 和 Clean / Random 场景配置。本页说明资产、控制选项和评测差异；公共运行流程见 [运行指南](../running.zh-CN.md)。当前为实验性适配，首次使用建议先做 [无模型接口检查](../running.zh-CN.md#无模型接口检查)。

## 源码与资产

`--env-root` 指向已安装的 RoboTwin 仓库，准备好任务源码、任务说明、`env_cfg/task_config/` 和 `assets/`。`--sim-python` 使用该环境自己的解释器，需具备 SAPIEN、PyTorch、NumPy、Pillow、PyYAML，以及宿主的规划器和渲染依赖；录像需要 FFmpeg/libx264。

当前支持配置中的单个共享双臂机器人。`_embodiment_config.yml` 指定机器人目录及其 `config.yml`，其中的资产路径须适用于本机。

## 任务与观测选项

| 参数或能力 | 默认值与语义 |
|---|---|
| 任务 | 宿主任务名，如 `adjust_bottle`，不使用排序编号 |
| 初始化 | `--seed 0`，不接受 layout-id / init-state-index |
| 场景配置 | `--task-config clean`；`clean` / `random` 分别使用 `demo_clean.yml` / `demo_randomized.yml` |
| 观测 | head_camera / left_camera / right_camera RGB 与双臂状态；`--image-size 256` |
| 预算 | `--max-native-steps 1000`，单位为原生双臂同步调用；初始化不计入，物理步另记 |
| 动作 | 双臂同步位姿增量，夹爪使用 `open` / `close`，省略或 `null` 保持目标 |
| 深度 | 默认开启模型深度估计声明；`--depth-estimation false` 关闭，不提供测量深度 |

比较 Clean / Random 时保持任务、seed、预算和输入条件一致。本接入直接评测指定 seed，不运行专家筛选或自动补齐有效样本；与其他评测比较时需保持相同的样本选择方式。

## 参考与评测配置

参考轨迹格式为 `robotwin-codex-dual-trajectory-v1`，文件须提前准备。视频映射与动作语义见 [上下文学习指南](../reference-protocol.zh-CN.md#robotwin)，三路视频生成文字见 [文字生成教程](../reference-format.zh-CN.md#robotwin三路专家视频)。

[单任务配置](../../configs/single_task/robotwin.json) 使用 `adjust_bottle`、seed 0、`clean`。[队列配置](../../configs/queues/robotwin.json) 包含 50 任务 × 2 种配置 × 5 seed，共 500 回合。执行与续跑见 [队列指南](../queues.zh-CN.md)，录像与日志见 [结果指南](../results.zh-CN.md)。
