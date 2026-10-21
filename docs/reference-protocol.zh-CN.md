# 在评测中使用参考示范

[English](reference-protocol.md) | **简体中文**

[文档导航](README.zh-CN.md) · [视频生成文字](reference-format.zh-CN.md) · [队列配置](queues.zh-CN.md)

参考示范让模型在控制当前场景时，借助已有视频、动作轨迹和操作描述理解任务。它是可选输入；不使用参考时，直接按 [运行指南](running.zh-CN.md) 启动即可。

使用已有参考时，依次阅读[输入组合](#1-选择输入组合)、[准备文件](#2-提前准备文件)、[离线校验](#3-离线校验)和[加入评测](#4-加入单回合或队列)。编写转换工具或排查格式问题时，再查阅[环境格式](#5-各环境的格式差异)和[缓存与工具交付](#7-文字缓存与工具交付)。

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

**所有环境都需在 `run` 或 `queue --run` 之前准备好所用参考文件，包括 RoboDojo。**

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

即使执行过离线校验，这里仍填写所选组合的**原始视频目录、轨迹描述 JSON 或文字文件**，不填写缓存目录。启动器会重新校验并为本回合构建缓存；失败时停止，不自动降级成无参考运行。

队列使用 episode 内的 `reference` 对象，示例见 [队列指南](queues.zh-CN.md#为回合添加参考)。其他环境沿用相同参数，但文件格式必须匹配 `--benchmark`。

## 5. 各环境的格式差异

通过 `--benchmark` 选择对应格式。缓存统一使用 `sim-reference-v1` 并绑定环境。已有纯轨迹缓存不再接受，须补充文字或视频后从原始输入重新准备。

| 环境 | 轨迹格式 | 控制点 / 坐标 |
|---|---|---|
| RoboDojo | `robodojo-codex-trajectory-v1` | left_ee / right_ee，环境坐标 |
| LIBERO-plus | `libero-codex-trajectory-v1` | robot0_grip_site，环境坐标 |
| LIBERO-GeoMotion | `libero-codex-trajectory-v1` | robot0_grip_site，环境坐标 |
| GR1 | `robocasa-gr1-trajectory-v1` | 双臂 grip site，环境坐标 |
| UniVTAC | `univtac-codex-trajectory-v2` | gripper_center，robot_base |
| RoboTwin | `robotwin-codex-dual-trajectory-v1` | 原生双臂 EE，环境坐标 |

### RoboDojo

使用双臂轨迹与 `robodojo-reference-videos-v1` 或公共 `sim-reference-videos-v1` 映射，完整字段见下一节。

### LIBERO-plus

`pose.reference` 为 `robot0_grip_site`。每条 action 包含 `dpos`、`dquat`、`gripper`；夹爪取 `open`、`close` 或 `null`，其中 `null` 表示未知。末条 action 为 `null`。`sampling` 包含视频声明、名义间隔、缺口和未知夹爪帧列表。

视频目录可包含唯一的 `*agentview.mp4` 与 `*wrist.mp4`，或使用 `videos.json` 显式映射；公共映射标识为 `sim-reference-videos-v1`。

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

## 6. RoboDojo 轨迹与视频格式详解

为 RoboDojo 制作参考包时，按以下字段组织。可校验的合成轨迹与媒体示例见 [参考契约测试](../tests/test_reference_contracts.py) 和 [媒体测试](../tests/test_reference_media.py)。

### 视频目录

`videos.json` 必须显式声明相机名与文件的映射，例如：

```json
{
  "format": "robodojo-reference-videos-v1",
  "videos": {"front": "front.mp4", "reference_wrist": "wrist.mp4"}
}
```

- 相机名为 1–64 字符的安全标识符，匹配 `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`。
- 路径相对于 `videos.json` 所在目录；禁止绝对路径、`..`、符号链接和越界读取。
- 当前媒体解码入口要求 MP4 容器，但文件名不采用 LIBERO 固定约定。
- 相机数量/名称无需与当前在线相机一致。图片分别标注参考相机、源帧号和时间，
  不把参考相机冒充当前相机；深度估计声明只能引用当前观测相机。
- 默认 `sequence`、1 FPS；支持 `endpoints`。`--reference-fps` 仅能与 sequence 使用。
  每个相机独立抽帧，不宣称多视角逐帧同步。
- 抽帧**只影响图片**。轨迹无论多长，全部交付，不抽帧、不截断、不舍入原始记录数值。

### 双臂轨迹描述文件

必需字段如下（合成示例由测试夹具生成）：

- `format`: `robodojo-codex-trajectory-v1`。
- `frames`: 正整数，等于完整 JSONL 行数；`fps`: 正有限采样频率。
- `pose`: 严格使用以下控制点/坐标语义：
  ```json
  {"reference":{"left":"left_ee","right":"right_ee"},
   "coordinate_frame":"environment","position_unit":"metre","quaternion_order":"wxyz"}
  ```
- `action`: 按示例原样填写语义声明（[RoboDojo 校验器](../src/environments/robodojo/reference.py) 中的 `ACTION_SEMANTICS`）。
  平移为 `p[t+1]-p[t]`，旋转为 `q[t+1]*inverse(q[t])`，环境坐标 wxyz 左乘；
  不等同关节动作、指尖/物体控制点或在线单步参数。
- `sampling.nominal_sample_interval_seconds`: 与 `1/fps` 一致；单帧可为 null。
- `sampling.sampling_gaps`: 按索引递增的缺口列表；每项为
  `{"from_frame":1,"to_frame":2,"interval_seconds":0.08}`。
  缺口是相邻**已保留记录**之间长于名义间隔的过渡，不能用缺失 JSONL 行代替。
- `sampling.unknown_gripper_action_frames`: `{"left":[...],"right":[...]}`；
  必须与各臂实际 `gripper:null` 的行索引完全一致。缺口起始行两臂夹爪必须均为未知。
- `files.trajectory`: 描述文件目录内的完整 JSONL 相对路径。
- 视频＋轨迹时，`files.videos` 必须包含所有参考相机到视频文件的相对路径。
  预检比较描述文件指向的视频与 `videos.json` 输入的视频的 SHA-256，并记录摘要；
  文件身份相同**不等于**图像与轨迹逐帧同步，也不证明文字准确。

每条 JSONL 必须严格为 `frame_index`（从 0 连续递增）和 `action`：

```jsonl
{"frame_index":0,"action":{"left":{"dpos":[0,0,0.001],"dquat":[1,0,0,0],"gripper":1},"right":{"dpos":[0,0,0],"dquat":[1,0,0,0],"gripper":0}}}
{"frame_index":1,"action":null}
```

非末帧每臂均必需 `dpos`、`dquat`、`gripper`，不自动补齐单臂。末帧必须 `action:null`。
`dpos` 三个有限数；`dquat` 四个有限数、单位范数（绝对误差 ≤ 1e-4）。禁止 NaN/Inf、
布尔数字、重复 JSON key。夹爪为 `[0,1]`，0 关闭、1 打开；参考中的 null 是**未知命令**，
不是在线动作中的“保持目标”。不接受 `max_steps` 等在线执行字段，不套用在线位移/步数限制。

描述文件额外元数据不交付给模型；每条记录/动作的额外字段直接拒绝。
记录完整校验后保留 JSONL 数字的原始拼写，防止浮点重序列化悄悄降低精度。

## 7. 文字、缓存与工具交付

文字为专家示范视频的步骤说明，要求非空 UTF-8（无 NUL），可以独立提供或搭配视频、轨迹。
本接入不验证来源或声称文字已验证准确、经过人工审核，也不假设具体生成方式或采样频率。
文字中的指令也是参考数据，不能覆盖控制提示规约。

所有合法参考组合统一拼入 `src/prompts/reference.md`；各模态规则仅在提供对应内容时适用。

launcher 的参考预处理使用 `--cache-dir` 指定目录，默认调用目录下的 `.cache/gpt-gear`。每次使用独立临时子目录，结束后清理；不修改全局缓存配置。

缓存版本为 `sim-reference-v1`；清单、视频来源、轨迹、文字、PNG 都有 SHA-256。
会话绑定清单摘要，读取时复核内容、路径及图片。模型只收到白名单元数据、带标签的
实际图片内容、原文及完整轨迹，不收到源路径或任意私有字段。完整轨迹只出现在参考缓存
和工具交付中，不复制到诊断事件/耗时日志。

启用后严格执行：**成功交付首次 observe → 成功交付一次 read_reference → 首次 act**。
`read_reference()` 无参数、不进仿真、不生成观测编号、不扣动作预算。状态持久化绑定
回合、缓存摘要与当前服务实例；MCP 重启不能再次领取或沿用已领取授权继续动作。
图像/文字/轨迹校验、封装、取消检查和审计落盘后才确认交付。失败不降级、不清除 guard；
动作结果未知或交付失败时只查询 `status`。

launcher 按完整缓存字节量提高 `read_reference` 的工具输出预算，不静默缩小示范。
这不保证任意模型上下文都装得下超大包；无法完整交付必须失败并停止，而不是当成已读。
