# RoboCasa GR1 环境配置

[English](robocasa-gr1.md) | **简体中文**

[文档导航](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#robocasa-gr1) · [队列评测](../queues.zh-CN.md)

RoboCasa GR1 提供双臂操作和 RGB 对齐的测量深度。本页说明源码、HDF5 配置和深度选项；公共运行流程见 [运行指南](../running.zh-CN.md)。当前为实验性适配，首次使用建议先做 [无模型接口检查](../running.zh-CN.md#无模型接口检查)。

## 源码与资产

准备已安装的 RoboCasa、robosuite 及配套仿真 Python，保留其 MuJoCo、Mink 和 NumPy 依赖配置。

| 参数 | 所需内容 |
|---|---|
| `--env-root` | RoboCasa 源码目录 |
| `--robosuite-root` | robosuite 源码目录 |
| `--data-root` | 包含 `<任务名>.hdf5` 的目录 |
| `--sim-python` | 已准备好仿真依赖的 Python 解释器 |

HDF5 的 `data.attrs['env_args']` 提供官方环境配置，**即使不使用参考示范，创建环境也需要这份配置**。必须使用 `WHOLE_BODY_MINK_IK`、absolute/base/axis_angle 输入，不能改成 joint-angle 输入。

适配来源使用的数据集为 `nvidia/PhysicalAI-Robotics-GR00T-Teleop-Sim`，本项目不自动下载。

## 任务与观测选项

| 参数或能力 | 默认值与语义 |
|---|---|
| 任务 | 24 个任务，见 [任务清单](../../src/environments/tasks.json)，如 `PnPCupToDrawerClose` |
| 初始化 | 由 `--seed` 指定，不接受 layout-id / init-state-index |
| 观测 | egoview RGB、双臂状态与测量深度；`--image-size 256` |
| 预算 | `--max-native-steps 1000`，包含 10 个稳定初始化步；最小值为 11 |
| 控制频率 | 20 Hz |
| 深度 | 默认 `--measured-depth true --depth-estimation false` |

### 深度模式

| 想使用的输入 | 参数 |
|---|---|
| RGB＋测量深度（默认） | 无需额外参数 |
| 纯 RGB，不要求深度声明 | `--measured-depth false --depth-estimation false` |
| RGB＋模型深度估计声明 | `--measured-depth false --depth-estimation true` |

只指定 `--measured-depth false` 时，模型深度估计声明恢复默认开启。测量深度与估计声明不能同时开启。

RGB 与深度同次渲染并同步翻转到左上原点，每份观测保存带 SHA-256 的 float32 米制深度。启用测量深度时，模型可通过 `read_depth(observation_id, camera="egoview", pixels_uv=[[u,v], ...])` 查询 1–64 个像素；`u` 是列，`v` 是行。

查询返回正光轴 Z 深度，以及用同份观测标定反投影的可见表面坐标，不是物体中心。历史查询不会推进物理时间；文件损坏、越界或禁用深度时会拒绝查询。该工具仅在启用测量深度的 GR1 会话提供。

## 参考与评测配置

参考轨迹格式为 `robocasa-gr1-trajectory-v1`，视频使用 egoview。文件须提前准备；创建环境所需的 HDF5 不会自动转换成参考视频或轨迹。参考包不包含实时测量深度，详细字段见 [参考协议](../reference-protocol.zh-CN.md#robocasa-gr1)，文字生成见 [视频文字教程](../reference-format.zh-CN.md)。

[单任务配置](../../configs/single_task/robocasa_gr1.json) 使用 `PnPCupToDrawerClose`。[队列配置](../../configs/queues/robocasa_gr1.json) 包含 24 任务 × 20 seed，共 480 回合，seed 沿用来源项目预设，不代表官方 seed split。测量深度开关参与回合身份计算；执行与续跑步骤见 [队列指南](../queues.zh-CN.md)。
