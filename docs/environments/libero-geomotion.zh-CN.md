# LIBERO-GeoMotion 环境配置

[English](libero-geomotion.md) | **简体中文**

[文档首页](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#libero-geomotion) · [队列评测](../queues.zh-CN.md)

LIBERO-GeoMotion 提供单臂操作、双视角 RGB，以及 9 类任务的 36 个场景，通过 `--benchmark libero-geomotion` 独立选择。本页说明路径、任务编号和参考选项；公共运行流程见[运行指南](../running.zh-CN.md)。

## 源码与资产

按[上游安装教程](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion#installation)准备环境。`--env-root` 指向已安装的 LIBERO-GeoMotion 源码目录，`--sim-python` 指向其配套仿真 Python。

## 任务与观测选项

| 参数或能力 | 默认值与含义 |
|---|---|
| 任务 | `libero_rp/0` 至 `libero_rp/35`，见[任务列表](../../src/environments/tasks.json) |
| 初始化 | `--seed 0 --init-state-index 0`；只支持初态 0 |
| 观测 | agentview / robot0_eye_in_hand RGB 与单臂状态；`--image-size 256` |
| 预算 | `--max-native-steps 4000`，无初始化预热步 |
| 控制频率 | 20 Hz |
| 深度 | 默认启用模型深度估计声明；用 `--depth-estimation false` 关闭；无测量深度 |

首次运行可先做[无模型接口检查](../running.zh-CN.md#libero-geomotion-接口检查)。

## 参考示范与评测配置

按[上游文档](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion)准备示范，通过公共参考参数选择视频、文字和轨迹。参考轨迹格式为 `libero-codex-trajectory-v1`，控制点为 `robot0_grip_site`。字段说明见[参考协议](../reference-protocol.zh-CN.md#libero-geomotion)，文字生成见[视频转文字指南](../reference-format.zh-CN.md#libero-geomotion两路视频)。

[单任务配置](../../configs/single_task/libero_geomotion.json) 使用 `libero_rp/0`，不带参考。[完整队列](../../configs/queues/libero_geomotion.json) 包含 9 类任务、36 个场景，每项使用 seed 0、init state 0 和 4000 个原生步。

其中 **6 类任务有示范，剩余 3 类没有示范**。有示范的 6 类共 24 个场景，分别使用本类的示范 0、4、8、26、28、34，包含视频、文字和轨迹参考；无示范的 3 类对应场景 12–15、16–19、20–23，共 12 个场景，以无参考方式运行，无需补齐示范。

运行前替换 `/path/to/...` 示例路径。完整任务标识和参考选择以配置中的 `episodes` 为准，执行与续跑步骤见[队列指南](../queues.zh-CN.md)。
