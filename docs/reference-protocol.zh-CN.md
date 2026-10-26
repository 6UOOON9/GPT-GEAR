# 具身上下文学习

[English](reference-protocol.md) | **简体中文**

[文档导航](README.zh-CN.md) · [运行第一个任务](running.zh-CN.md) · [查看结果](results.zh-CN.md) · [视频生成文字](reference-format.zh-CN.md) · [队列配置](queues.zh-CN.md)

具身上下文学习（Embodied In-Context Learning，ICL）将示范文字、视频和动作轨迹放入模型上下文，帮助模型在当前场景中执行任务。本指南介绍如何准备示范文件并将其加入评测。示范是可选的；不使用示范时，直接按 [运行指南](running.zh-CN.md) 启动即可。

名称沿用 📄 [论文中的能力评测术语](https://arxiv.org/html/2610.28259v1#S4.SS4.SSS2)。命令和配置字段使用 `reference`，例如 `--reference-text` 和 `--reference-video`。

使用已有示范时，依次阅读[输入组合](#1-选择输入组合)、[准备文件](#2-提前准备文件)、[离线校验](#3-离线校验)和[加入评测](#4-加入单回合或队列)。编写转换工具或排查格式问题时，再查阅[环境格式](#5-各环境的格式差异)。

## 1. 选择输入组合

| 提供的内容 | 是否支持 |
|---|---|
| 不提供参考 | 支持 |
| 仅文字 | 支持 |
| 仅视频 | 支持 |
| 仅轨迹 | 不支持，须搭配文字或视频 |
| 文字＋视频 | 支持 |
| 文字＋轨迹 | 支持 |
| 视频＋轨迹 | 支持 |
| 视频＋轨迹＋文字 | 支持 |

文字参考是来自专家示范视频的操作步骤说明；评测时可以只提供文字，无需同时提供来源视频。
参考轨迹必须搭配文字或视频，是给模型阅读的操作资料，不会直接回放为当前机器人的动作。文件校验通过也不代表示范成功、文字准确或各模态逐步、逐帧同步。

## 2. 提前准备文件

**所有环境都需在 `run` 或 `queue --run` 之前准备好所用参考文件。**

1. 按所选组合准备文件；如使用轨迹，准备所选环境格式的轨迹描述 JSON 和 JSONL。
2. 如需文字，提供已有文字，或使用 [视频文字生成教程](reference-format.zh-CN.md) 中的 `reference annotate`。
3. 核对任务、视角和轨迹坐标语义，再执行下面的离线校验。
4. 运行评测时传入原始文件路径，由启动器组装本次回合的缓存。

本项目提供视频转文字、格式校验、抽帧与缓存，不下载原始数据、不导出视频或生成轨迹，也不会在评测启动时补齐缺失示范。

| 环境 | 文字生成所需视角 | 文字生成入口 |
|---|---|---|
| RoboDojo | head / left_wrist / right_wrist | `reference annotate --benchmark robodojo` |
| LIBERO-plus | agentview / robot0_eye_in_hand | `reference annotate --benchmark libero-plus` |
| LIBERO-GeoMotion | agentview / robot0_eye_in_hand | `reference annotate --benchmark libero-geomotion` |
| RoboCasa GR1 | egoview | `reference annotate --benchmark robocasa-gr1` |
| UniVTAC | head / wrist | `reference annotate --benchmark univtac` |
| RoboTwin | head_camera / left_camera / right_camera | `reference annotate --benchmark robotwin` |

表内视角是文字生成要求；评测读取的相机映射规则见后文。视频可以单独用于评测；轨迹须搭配文字或视频。

## 3. 离线校验

完成 [安装](installation.zh-CN.md) 后，在仓库根目录执行。标准库 Python 可处理轨迹；处理视频还需要 `ffmpeg` 和 `ffprobe`。

校验纯文字参考（不需要视频处理工具）：

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --output outputs/reference_check_text/reference
```

校验文字＋轨迹：

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --trajectory /path/to/reference/trajectory.json \
  --output outputs/reference_check_text_trajectory/reference
```

校验文字＋视频（无需轨迹描述文件）：

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --reference-video /path/to/reference/videos \
  --output outputs/reference_check_text_video/reference
```

校验包含视频、轨迹和文字的参考：

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-video /path/to/reference/videos \
  --trajectory /path/to/reference/trajectory.json \
  --reference-text /path/to/reference/steps.txt \
  --reference-mode sequence --reference-fps 1 \
  --output outputs/reference_check_full/reference
```

目标 `reference` 目录必须不存在。该命令只校验已有内容并生成缓存，不启动仿真、不调用模型、不提交动作。

提供视频时默认按 `sequence`、1 FPS 抽帧；`endpoints` 模式取端点，不能同时指定 `--reference-fps`。未提供视频时不能指定采样参数。视频抽帧只影响图片，轨迹保留全部记录与原始数值拼写。离线 prepare 不接受空输入或纯轨迹输入。

## 4. 加入单回合或队列

以 RoboDojo 为例，替换路径并使用新的输出目录：

```bash
gpt-gear run align_blocks outputs/robodojo_reference \
  --benchmark robodojo \
  --env-root /path/to/RoboDojo \
  --sim-python /path/to/robodojo/bin/python \
  --seed 0 --layout-id 0 \
  --reference-video /path/to/reference/videos \
  --trajectory /path/to/reference/trajectory.json \
  --reference-text /path/to/reference/steps.txt
```

按所选组合保留对应参数：纯文字只保留 `--reference-text`；文字＋轨迹保留 `--reference-text` 和 `--trajectory`；文字＋视频保留 `--reference-text` 和 `--reference-video`。

运行 `run` 或 `queue` 时，序列参考默认每视角最多 48 张图片。可用 `--reference-max-frames`（至少 2）修改，单个 episode 的 `reference.max_frames` 优先于队列 CLI 参数。按 `--reference-fps` 抽帧超过上限时，在整段视频的源帧中均匀取样并保留首尾帧；否则保留原来的 fps 抽帧结果。轨迹记录不变。此上限不作用于离线 `reference prepare` 或文字标注。

即使执行过离线校验，这里仍填写所选组合的**原始视频目录、轨迹描述 JSON 或文字文件**，不填写缓存目录。启动器会重新校验并为本回合构建缓存；失败时停止，不自动降级成无参考运行。

队列使用 episode 内的 `reference` 对象，示例见 [队列指南](queues.zh-CN.md#为回合添加参考)。其他环境沿用相同参数，但文件格式必须匹配 `--benchmark`。

## 5. 各环境的格式差异

通过 `--benchmark` 选择对应格式。缓存统一使用 `sim-reference-v1` 并绑定环境。已有纯轨迹缓存不再接受，须补充文字或视频后从原始输入重新准备。

视频映射文件 `videos.json` 使用 `format: "sim-reference-videos-v1"`，其中 `videos` 对象将相机名称映射到视频文件路径。这个标识表示各环境共用的映射文件结构；环境由 `--benchmark` 选择，相机名称按环境填写。它与下表中描述机器人位姿和动作的轨迹格式标识用途不同。

轨迹描述 JSON 通过 `files.trajectory` 指向完整 JSONL 文件，路径相对描述文件所在目录。视频与轨迹一起提供时，描述文件还需通过 `files.videos` 映射所有参考相机；部分环境也支持下文列出的平铺字段。校验器会核对描述文件指向的视频与输入视频的文件摘要是否一致。文件路径须位于描述文件目录内，不接受绝对路径、`..` 或符号链接。

| 环境 | 轨迹格式 | 控制点 / 坐标 |
|---|---|---|
| RoboDojo | `robodojo-codex-trajectory-v1` | left_ee / right_ee，环境坐标 |
| LIBERO-plus | `libero-codex-trajectory-v1` | robot0_grip_site，环境坐标 |
| LIBERO-GeoMotion | `libero-codex-trajectory-v1` | robot0_grip_site，环境坐标 |
| GR1 | `robocasa-gr1-trajectory-v1` | 双臂 grip site，环境坐标 |
| UniVTAC | `univtac-codex-trajectory-v2` | gripper_center，robot_base |
| RoboTwin | `robotwin-codex-dual-trajectory-v1` | 原生双臂 EE，环境坐标 |

### RoboDojo

`pose.reference` 为 `{"left":"left_ee","right":"right_ee"}`，使用环境坐标，位置单位为米，四元数顺序为 wxyz。每条非末尾 action 包含 `left` / `right`，各自包含 `dpos`、`dquat`、`gripper`；夹爪目标范围为 `[0,1]`，0 表示闭合、1 表示张开，`null` 表示未知而非保持。末条 action 为 `null`。`sampling` 包含名义采样间隔、采样缺口和按左右臂分别记录的未知夹爪动作帧列表。语义常量见 [RoboDojo 校验器](../src/environments/robodojo/reference.py)。

视频目录可包含唯一的 `*head.mp4`、`*left_wrist.mp4` 与 `*right_wrist.mp4`，或使用 `videos.json` 显式映射；存在映射文件时优先使用映射。映射使用上述 `sim-reference-videos-v1` 标识，也接受 `robodojo-reference-videos-v1`，两者使用相同的映射结构。文字生成需要 `head`、`left_wrist`、`right_wrist` 三路视角，目录示例见 [视频文字教程](reference-format.zh-CN.md#robodojo三路视频)。轨迹与视频是否提供仍按前面的输入组合选择。

### LIBERO-plus

`pose.reference` 为 `robot0_grip_site`。每条 action 包含 `dpos`、`dquat`、`gripper`；夹爪取 `open`、`close` 或 `null`，其中 `null` 表示未知。末条 action 为 `null`。`sampling` 包含视频声明、名义间隔、缺口和未知夹爪帧列表。

视频目录可包含唯一的 `*agentview.mp4` 与 `*wrist.mp4`，或使用上述 `videos.json` 显式映射。

### LIBERO-GeoMotion

复用 [LIBERO 轨迹格式](#libero-plus)，视频包括 `agentview` 和腕部视角，每个视角均为 256 × 256，使用 `--benchmark libero-geomotion` 选择环境。参考输入与队列设置见[环境配置](environments/libero-geomotion.zh-CN.md#参考示范与评测配置)。缓存、模态组合和交付规则与其他环境相同。

### RoboCasa GR1

`pose.reference` 为 `{"right":"gripper0_right_grip_site","left":"gripper0_left_grip_site"}`，位置单位为米，四元数顺序为 wxyz。每条 `action.arms` 包含双臂的 `dpos`、`dquat`、`hand`；`hand` 为 6 个 `[-3,3]` 弧度目标，末条 action 为 `null`。采样字段使用 `unknown_hand_action_frames`，语义常量见 [GR1 校验器](../src/environments/robocasa_gr1/reference.py)。

视频可使用唯一的 `*egoview.mp4`。描述文件兼容平铺 `files.egoview` 和公共 `files.videos` 映射。

### UniVTAC

每条记录包含原始 7 维 `joint_positions` 和米制 `gripper_position_m`。动作夹爪目标必须等于下一记录的实测手指位置，范围 `[0,0.04]` 米，表示手指位置而非总开口。旧二值夹爪 v1 格式不被接受，也不隐式转换。

描述文件须包含 `robot_state` 语义声明，见 [UniVTAC 校验器](../src/environments/univtac/reference.py)。视频可使用唯一的 `*head.mp4`、`*wrist.mp4`；支持平铺 `files.head` / `files.wrist` 和公共 `files.videos` 映射。

### RoboTwin

`pose.reference=robotwin_native_ee`，`pose.arms=["left","right"]`，包含双臂 `initial_poses` / `final_poses`。每条记录含 `frame_index`、`action` 和 `gripper_opening`；非末条 action 含 left / right 的 `dpos`、`dquat`、`gripper`，源 gripper 必须为 `null`，末条 action 为 `null`。`gripper_opening` 是 `[0,1]` 实测开度，不能据此伪造原始开合命令。语义常量见 [RoboTwin 校验器](../src/environments/robotwin/reference.py)。

三路视频可直接命名为 `head_camera.mp4`、`left_camera.mp4`、`right_camera.mp4`，或使用通用 `videos.json` 映射。描述文件支持平铺 `files.head_camera` 等字段，也支持公共 `files.videos`；路径相对描述文件，视频内容须匹配。文字生成命令、输入目录与采样限制见 [视频文字教程](reference-format.zh-CN.md)。

所有轨迹格式都保留完整 JSONL 记录和原始数值拼写，并校验文件摘要与路径边界。参考包含所选组合的 RGB、文字和轨迹，实时触觉与测量深度不属于参考包。
