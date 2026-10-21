# 从示范视频生成文字步骤

[English](reference-format.md) | **简体中文**

[文档导航](README.zh-CN.md) · 下一步：[在评测中使用上下文学习](reference-protocol.zh-CN.md)

本教程介绍如何将自行准备好的示范视频转换为英文编号步骤 `steps.txt`。
本项目只提供文字生成过程；视频由使用者提前准备。生成文字无需轨迹、原始数据集或仿真环境。

## 1. 安装与准备

已按 [安装指南](installation.zh-CN.md) 安装工具时，只需在仓库根目录激活环境：

```bash
source .venvs/codex-mcp/bin/activate
```

如果只需要生成文字，也可以在独立 Python 环境执行 `python -m pip install -e .`，无需安装 MCP 扩展。

确保 `ffmpeg`、`ffprobe` 和已配置好的 `codex` 命令可用。文字生成使用本机 Codex CLI
调用模型，默认沿用其模型配置；Python 部分只需要标准库，无需安装仿真依赖。
网络连接继承当前进程的代理环境变量（如 `HTTPS_PROXY`、`HTTP_PROXY` 和 `NO_PROXY`）。
程序不设置本机代理地址，也不自动重试失败或超时的模型调用。

每个目录放一条示范的视频。同一示范的不同视角放在同一个目录，不同示范分开存放。
当前支持的相机配置如下；`--benchmark` 用于选择相机配置和文字提示词，不会启动对应仿真环境。

| 示范类型 | `--benchmark` | 所需视频视角 |
|---|---|---|
| RoboDojo | `robodojo` | `head`、`left_wrist`、`right_wrist` |
| LIBERO-plus | `libero-plus` | `agentview`、`robot0_eye_in_hand` |
| LIBERO-GeoMotion | `libero-geomotion` | `agentview`、`robot0_eye_in_hand` |
| UniVTAC | `univtac` | `head`、`wrist` |
| RoboCasa GR1 | `robocasa-gr1` | `egoview` |
| RoboTwin | `robotwin` | `head_camera`、`left_camera`、`right_camera` |

目前命令支持以上配置，不接受任意相机组合。

## 2. 整理视频并生成文字

选择与你的视频对应的一种配置执行即可：[RoboDojo](#robodojo三路视频) · [LIBERO-plus](#libero-plus两路视频) · [LIBERO-GeoMotion](#libero-geomotion两路视频) · [RoboCasa GR1](#robocasa-gr1单路视频) · [UniVTAC](#univtac两路视频) · [RoboTwin](#robotwin三路专家视频)。

### RoboDojo：三路视频

准备以下目录：

```text
references/robodojo/stack_blocks/
├── head.mp4
├── left_wrist.mp4
└── right_wrist.mp4
```

按以上方式命名时无需 `videos.json`；也支持文件名以 `head.mp4`、`left_wrist.mp4`、`right_wrist.mp4` 结尾，每种后缀须恰好匹配一个文件。若要使用其他文件名，可添加 `videos.json` 显式指定三路相机对应的文件；存在映射文件时优先使用映射：

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "head": "head.mp4",
    "left_wrist": "left_wrist.mp4",
    "right_wrist": "right_wrist.mp4"
  }
}
```

映射中的相机名称保持不变，文件名可按实际视频修改，路径相对于这个目录。
然后执行以下命令；它会调用模型并写入生成结果：

```bash
gpt-gear reference annotate --benchmark robodojo references/robodojo/stack_blocks
```

### UniVTAC：两路视频

准备 head 和 wrist 两路 MP4 视频。文件名分别以 `head.mp4`、`wrist.mp4` 结尾，
每种视角在目录中各有一个文件：

```text
references/univtac/insert_HDMI/
├── demo_head.mp4
└── demo_wrist.mp4
```

```bash
gpt-gear reference annotate --benchmark univtac references/univtac/insert_HDMI
```

按以上方式命名时无需 `videos.json`。若要使用其他文件名，也可参照上面的映射格式，
只保留 `head`、`wrist` 两个相机键并填写对应文件名。

### RoboCasa GR1：单路视频

准备一个文件名以 `egoview.mp4` 结尾的 MP4 视频：

```text
references/gr1/PnPCupToDrawerClose/
└── egoview.mp4
```

```bash
gpt-gear reference annotate --benchmark robocasa-gr1 references/gr1/PnPCupToDrawerClose
```

按以上方式命名时无需 `videos.json`。若要使用其他文件名，也可用同样的映射格式，
只保留 `egoview` 相机键并填写对应文件名。

### LIBERO-plus：两路视频

准备同一条示范的外部视角和腕部视角视频，文件名分别以 `agentview.mp4`、`wrist.mp4`
结尾，每种视角各一个文件：

```text
references/libero/pick_up_bowl/
├── demo_agentview.mp4
└── demo_wrist.mp4
```

```bash
gpt-gear reference annotate --benchmark libero-plus references/libero/pick_up_bowl
```

按以上方式命名时无需 `videos.json`；腕部视频对应的相机名称是 `robot0_eye_in_hand`。
若要使用其他文件名，添加如下映射（文件名按实际情况修改）：

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "agentview": "demo_agentview.mp4",
    "robot0_eye_in_hand": "demo_wrist.mp4"
  }
}
```

此流程沿用 LIBERO-plus 的视觉标注提示词，只使用视频图片和相机、时间标签，无需安装
LIBERO 仿真环境或提供轨迹。两路视频分别抽帧，不要求逐帧同步。生成的 `steps.txt`
用于评测时可以单独提供，也可搭配视频、轨迹或两者，见 [上下文学习指南](reference-protocol.zh-CN.md)。

### LIBERO-GeoMotion：两路视频

使用导出的 `agentview.mp4` 和 `wrist.mp4`（各 256 × 256）及其 `videos.json`，指定 GeoMotion 的 benchmark 标识：

```bash
gpt-gear reference annotate --benchmark libero-geomotion /path/to/geomotion-references-256/task_000
```

### RoboTwin：三路专家视频

将同一条专家示范的三个独立视角放在一个目录：

```text
references/robotwin/beat_block_hammer/videos/
├── head_camera.mp4
├── left_camera.mp4
└── right_camera.mp4
```

```bash
gpt-gear reference annotate --benchmark robotwin \
  references/robotwin/beat_block_hammer/videos
```

也支持文件名以这些相机名加 `.mp4` 结尾，或使用 `videos.json` 指定其他文件名：

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "head_camera": "front.mp4",
    "left_camera": "left.mp4",
    "right_camera": "right.mp4"
  }
}
```

无需 RoboTwin 仿真、任务源码或轨迹。模型只读取抽帧图片及相机、时间标签；
输出为英文编号步骤，包含可见操作、不确定性和执行前需核对的现场条件。

默认 1 FPS，三路合计最多 42 张图片，超过上限会在调用模型前报错。较长视频可显式降低
采样率，例如 `--reference-fps 0.5`；首末帧始终保留，不会自动丢弃超限附件。
采样率越低，越可能漏掉短暂动作，请检查生成结果。

## 3. 查看生成结果

默认在输入视频目录内新增：

```text
steps.txt                 # 生成的英文编号步骤
annotation/
├── frames/               # 提供给模型的抽帧图片
├── prompt.txt            # 使用的提示词
├── response.txt          # 模型原始回复
└── audit.json            # 抽帧与生成记录
```

程序默认按 1 FPS 对各路视频独立抽帧，可用 `--reference-fps` 调整，并保留首末帧。模型根据这些图片、相机名称和时间标签
描述可见操作。生成后请对照视频检查 `steps.txt`；程序会检查编号格式，但不会验证步骤
内容是否准确或示范是否成功。

## 4. 批量处理与常用选项

一次可以处理同一类型的多个示范目录，各目录的最后一级名称必须不同：

```bash
gpt-gear reference annotate --benchmark univtac \
  references/univtac/insert_HDMI \
  references/univtac/insert_USB
```

如需将文字单独保存，使用 `--output-root`：

```bash
gpt-gear reference annotate --benchmark univtac \
  references/univtac/insert_HDMI \
  --output-root outputs/reference_text
```

本例将结果保存到 `outputs/reference_text/insert_HDMI/steps.txt` 和同级的 `annotation/`，
视频仍保留在原目录。输出子目录应不存在或为空。程序不会覆盖已有文字、生成记录或已记录的
失败状态；另存生成结果时使用新的输出根目录。

如果来源目录有 `provenance.json`，程序会复制并检查其中的文字状态；已有 `text.status=complete`、
`text.status=failed` 或文字摘要时，即使指定新的 `--output-root` 也会拒绝生成，避免覆盖已有证据。
失败信息仅在已有 provenance 时写回其 `text` 字段；失败不保证留下 `annotation/`，需保留终端报错。

| 选项 | 用途 |
|---|---|
| `--benchmark` | 选择示范类型，默认 `robodojo`，建议显式填写 |
| `--output-root` | 保存到指定根目录下的 `<输入目录名>/`，默认保存到输入目录 |
| `--codex-model` | 指定模型，默认使用本机 Codex 配置 |
| `--reference-fps` | 抽帧频率，默认 `1`，必须为有限正数；RoboTwin 超过 42 张时需降低 |
| `--timeout` | 模型调用超时秒数，默认 `600` |

查看完整命令帮助：

```bash
gpt-gear reference annotate --help
```

## 5. 将文字用于评测

文字生成只需要视频；把 `steps.txt` 加入评测时可以只提供文字，也可搭配视频、轨迹或两者。轨迹不能单独用于评测。先检查生成步骤是否准确，再按 [上下文学习指南](reference-protocol.zh-CN.md) 运行离线校验，并将所选原始文件路径传给 `run` 或队列。

## 常见问题

| 情况 | 处理方式 |
|---|---|
| 相机不匹配或发现多个同后缀视频 | 每个目录保留一条示范，核对相机键或显式添加 `videos.json` |
| 输出目录已有文字或审计 | 使用新的 `--output-root`；来源 provenance 中已记录的完成或失败状态仍会阻止生成 |
| 模型超时或认证失败 | 检查 Codex 配置、网络和终端报错；已有 provenance 时另检查其 `text` 字段，程序不会自动重试 |
| RoboTwin 抽帧超过 42 张 | 降低 `--reference-fps` 后使用新的输出目录重新准备 |
| 希望从 HDF5 / LeRobot 直接生成 | 先用外部工具准备视频，本项目不导出原始数据 |
