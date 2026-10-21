# UniVTAC 环境配置

[English](univtac.md) | **简体中文**

[文档导航](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#univtac) · [队列评测](../queues.zh-CN.md)

UniVTAC 提供单臂操作、双视角 RGB 和可选触觉输入。本页说明依赖、控制预算和触觉模式；公共运行流程见 [运行指南](../running.zh-CN.md)。当前为实验性适配，首次使用建议先做 [无模型接口检查](../running.zh-CN.md#无模型接口检查)。

## 源码与资产

`--env-root` 指向已准备好资产和仿真依赖的 UniVTAC 仓库，需包含 `envs/_base_task.py`。`--sim-python` 使用该环境自己的解释器；入口会在导入任务前启动 Isaac Lab。

## 任务与观测选项

| 参数或能力 | 默认值与语义 |
|---|---|
| 任务 | 8 个任务，见 [任务清单](../../src/environments/tasks.json)；如 `insert_HDMI`，区分大小写 |
| 初始化 | 由 `--seed` 指定，不接受 layout-id / init-state-index |
| RGB 观测 | head / wrist；`--image-width 480 --image-height 270` |
| 触觉 | `--tactile-mode force`，双侧触觉合力 |
| 控制步预算 | `--max-native-steps 400` |
| 动作预算 | `--max-policy-actions 40` |
| 控制步细分 | `--control-decimation 6`，每控制步最多执行 6 个物理步，成功或提前终止时中断；初始化物理步另记 |
| 深度 | 默认开启模型深度估计声明；`--depth-estimation false` 关闭，不提供测量深度 |

### 触觉模式

| `--tactile-mode` | 除 RGB 与本体状态外的输入 |
|---|---|
| `none` | 无 |
| `image` | 触觉图像 |
| `force`（默认） | 双侧触觉合力 |
| `image-force` | 触觉图像与合力 |

触觉图像与普通相机标定分开。合力是 UIPC 最后一次求解器接触梯度的换算值，单位 N，坐标系为 robot_base，不等同于独立标定的真实力传感器。关闭模型输入不会关闭内部触觉更新，以保持官方成功判定。

### 夹爪与步数

动作使用 `robot0.gripper_position_m` 指定米制手指位置，范围 `[0,0.04]`，不是总开口或二值开合。控制循环、物理 tick 与模型动作分别记账；比较评测时应同时保持预算、`control_decimation` 和触觉模式一致。控制实现细节见 [架构说明](../architecture.zh-CN.md#univtac)。

## 参考与评测配置

参考使用 `univtac-codex-trajectory-v2` 连续夹爪格式，不自动转换旧二值夹爪示范。视频视角为 head / wrist；参考包不包含实时触觉。详细字段见 [上下文学习指南](../reference-protocol.zh-CN.md#univtac)，文字生成见 [视频文字教程](../reference-format.zh-CN.md)。

[单任务配置](../../configs/single_task/univtac.json) 使用 `insert_HDMI`。[队列配置](../../configs/queues/univtac.json) 包含 8 任务 × 20 seed，共 160 回合，seed 沿用来源项目预设，不代表官方 seed split。

队列默认 `force`，可在每个 episode 中设置 `tactile_mode`。模态参与回合身份计算，汇总按模态分组；执行与续跑步骤见 [队列指南](../queues.zh-CN.md)。
