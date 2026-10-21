# 运行第一个任务

[English](running.md) | **简体中文**

[文档导航](README.zh-CN.md) · 前置：[安装与环境准备](installation.zh-CN.md) · 下一步：[查看结果](results.zh-CN.md) · [上下文学习（可选）](reference-protocol.zh-CN.md)

本页给出所有支持环境的单回合命令。每次运行都会创建独立的仿真进程与 Codex 会话；以下示例均不使用示范。想加入示范文字、视频或轨迹，可按 [上下文学习（ICL）指南](reference-protocol.zh-CN.md) 配置。

先阅读[运行前](#运行前)，再选择你的环境：[RoboDojo](#robodojo) · [LIBERO-plus](#libero-plus) · [LIBERO-GeoMotion](#libero-geomotion) · [RoboCasa GR1](#robocasa-gr1) · [UniVTAC](#univtac) · [RoboTwin](#robotwin)。其他内容可按需查阅：[常用选项](#常用运行选项) · [无模型接口检查](#无模型接口检查) · [查看结果与后续操作](#结束后做什么)。

## 运行前

在仓库根目录激活工具环境，并将示例中的 `/path/to/...` 替换为你的路径：

```bash
source .venvs/codex-mcp/bin/activate
```

先对准备使用的任务运行 `doctor`。可以将下面的 `run 任务名 输出目录` 替换为 `doctor --task 任务名`，保留环境路径与任务选项。例如：

```bash
gpt-gear doctor --benchmark robotwin --task adjust_bottle \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python --task-config clean
```

`doctor` 不启动仿真或模型，也不验证模型认证。支持该入口的环境可先做 [无模型接口检查](#无模型接口检查)，确认场景加载与录像正常。

每个 `run` 的输出目录必须尚不存在，不要提前创建或重复使用。相对路径以当前工作目录为基准。

## RoboDojo

```bash
gpt-gear run align_blocks outputs/robodojo_one \
  --benchmark robodojo \
  --env-root /path/to/RoboDojo \
  --sim-python /path/to/robodojo/bin/python \
  --seed 0 --layout-id 0
```

`align_blocks` 可换成宿主支持且有评测布局的任务名。`--layout-id` 选择该 seed 下的布局，默认 `0`。RoboDojo 使用宿主原生执行预算、评分与录像。

源码、子模块和评测布局要求见 [RoboDojo 环境配置](environments/robodojo.zh-CN.md)。

## LIBERO-plus

```bash
gpt-gear run libero_spatial/0 outputs/libero_one \
  --benchmark libero-plus \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python \
  --seed 0 --init-state-index 0 --max-native-steps 600
```

任务标识为 `suite/task_id`。`--init-state-index` 选择任务的初始化状态，默认 `0`。默认图像为 256×256，控制频率 20 Hz；600 个原生步的预算包含前 10 个稳定初始化步。

源码、资产与初始化状态的说明见 [LIBERO-plus 环境配置](environments/libero-plus.zh-CN.md)。

## LIBERO-GeoMotion

```bash
gpt-gear run libero_rp/0 outputs/geomotion_one \
  --benchmark libero-geomotion \
  --env-root /path/to/LIBERO-GeoMotion \
  --sim-python /path/to/geomotion/bin/python \
  --seed 0 --init-state-index 0 --max-native-steps 4000
```

任务为 `libero_rp/0` 至 `libero_rp/35`，只支持初态 0。默认图像为 256×256，控制频率为 20 Hz。预算为 4000 个原生步，无初始化预热。

环境路径与参考说明见 [LIBERO-GeoMotion 环境配置](environments/libero-geomotion.zh-CN.md)。添加示范时，按[上下文学习指南](reference-protocol.zh-CN.md)配置。

## RoboCasa GR1

```bash
gpt-gear run PnPCupToDrawerClose outputs/gr1_one \
  --benchmark robocasa-gr1 \
  --env-root /path/to/robocasa-gr1-tabletop-tasks \
  --robosuite-root /path/to/robosuite-gr1 \
  --data-root /path/to/robocasa_data \
  --sim-python /path/to/robocasa/bin/python \
  --seed 1365783547 --max-native-steps 1000
```

GR1 需要额外指定 robosuite 源码和 HDF5 数据目录。上述任务要求 `data_root` 下存在 `PnPCupToDrawerClose.hdf5`，其环境配置用于创建场景；不使用参考时也需要它。

默认输入为 RGB＋测量深度，1000 个原生步包含 10 个稳定初始化步。纯 RGB 使用 `--measured-depth false --depth-estimation false`。

可用的 24 个任务见 [任务清单](../src/environments/tasks.json)，深度选项见 [GR1 环境配置](environments/robocasa-gr1.zh-CN.md)。

## UniVTAC

```bash
gpt-gear run insert_HDMI outputs/univtac_one \
  --benchmark univtac \
  --env-root /path/to/UniVTAC \
  --sim-python /path/to/univtac/bin/python \
  --seed 1468828686 --tactile-mode force
```

任务名区分大小写，支持的 8 个任务见 [任务清单](../src/environments/tasks.json)。默认预算为 400 个控制步、40 次模型动作，每个控制步最多执行 6 个物理步，任务成功或提前终止时会中断剩余物理步。

`--tactile-mode` 可选 `none`、`image`、`force`、`image-force`，分别表示不提供触觉、提供触觉图像、提供触觉合力、同时提供二者。所有模式均保留 RGB 和本体状态；默认 `force`。

触觉含义与动作参数见 [UniVTAC 环境配置](environments/univtac.zh-CN.md)。

## RoboTwin

```bash
gpt-gear run adjust_bottle outputs/robotwin_one \
  --benchmark robotwin \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python \
  --seed 0 --task-config clean --max-native-steps 1000
```

使用宿主任务名，如 `adjust_bottle`。`--task-config` 可选 `clean` 或 `random`，默认 `clean`。默认预算为 1000 次原生双臂同步调用，初始化不计入。

资产、观测和 Clean / Random 评测说明见 [RoboTwin 环境配置](environments/robotwin.zh-CN.md)。

## 常用运行选项

| 选项 | 用途 |
|---|---|
| `--codex-model 模型名` | 覆盖本机默认模型配置 |
| `--device-id 0` | 选择 GPU |
| `--port 8092` | 选择本地控制端口 |
| `--depth-estimation false` | 关闭模型的深度估计声明要求 |
| `--cache-dir PATH` | 指定参考预处理等使用的缓存根目录 |
| `--codex-mcp-python PATH` | 指定独立 MCP 解释器 |
| `--codex-startup-timeout 600` | 等待仿真就绪的秒数 |
| `--codex_connect_timeout 600` | 会话连接超时秒数 |
| `--codex_idle_timeout 600` | 连接后原生动作计数无进展的超时秒数；只读查询不会重置计时 |
| `--codex_request_timeout 600` | 请求处理超时秒数 |

GR1 默认开启测量深度并关闭估计声明；其他环境默认开启估计声明。估计声明是模型基于画面的估计，不是仿真真实深度。

环境专属选项不能跨环境使用。查看完整帮助时带上 benchmark，例如：

```bash
gpt-gear run --benchmark univtac --help
```

## 无模型接口检查

LIBERO-plus、LIBERO-GeoMotion、GR1、UniVTAC 和 RoboTwin 支持 `--smoke` 检查。它启动真实仿真，保存初始观测，执行一次保持动作，再保存末态和录像；不启动 Codex，不调用模型，结果为 `interface_smoke_only`，不计入任务成功率。RoboDojo 当前没有这一入口，使用前面的预检和单回合命令验证。

先完成 `doctor` 预检，再选择下面对应环境的命令。在仓库根目录执行，将本项目 `src` 加入仿真进程的 `PYTHONPATH`；替换所有路径，输出目录必须尚不存在：

```bash
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

### LIBERO-plus 接口检查

```bash
/path/to/libero/bin/python -m environments.libero_plus.simulator \
  libero_spatial/0 outputs/libero_interface --smoke \
  --benchmark libero-plus --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python --seed 0 --init-state-index 0
```

### LIBERO-GeoMotion 接口检查

```bash
/path/to/geomotion/bin/python -m environments.libero_geomotion.simulator \
  libero_rp/0 outputs/geomotion_interface --smoke \
  --benchmark libero-geomotion --env-root /path/to/LIBERO-GeoMotion \
  --sim-python /path/to/geomotion/bin/python --seed 0 --init-state-index 0
```

### RoboCasa GR1 接口检查

```bash
/path/to/robocasa/bin/python -m environments.robocasa_gr1.simulator \
  PnPCupToDrawerClose outputs/gr1_interface --smoke \
  --benchmark robocasa-gr1 --env-root /path/to/robocasa-gr1-tabletop-tasks \
  --robosuite-root /path/to/robosuite-gr1 --data-root /path/to/robocasa_data \
  --sim-python /path/to/robocasa/bin/python
```

### UniVTAC 接口检查

```bash
/path/to/univtac/bin/python -m environments.univtac.simulator \
  insert_HDMI outputs/univtac_interface --smoke \
  --benchmark univtac --env-root /path/to/UniVTAC \
  --sim-python /path/to/univtac/bin/python --tactile-mode force
```

### RoboTwin 接口检查

```bash
/path/to/robotwin/bin/python -m environments.robotwin.simulator \
  adjust_bottle outputs/robotwin_interface_clean --smoke \
  --benchmark robotwin --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python \
  --task-config clean --seed 0 --max-native-steps 10
```

检查 Random 配置时，将 `--task-config` 改为 `random`，并使用新的输出目录。

### 查看检查结果

`smoke.json` 记录接口检查结果，`host.json` 记录加载的源码和依赖；检查 `observations/` 中的画面与 `video.json` 中的编码状态。这些命令直接运行仿真入口，异常会输出到当前终端；通过 `gpt-gear run` 启动时则查看 `server.log`。排错方法见 [结果指南](results.zh-CN.md)。

接口检查通过只说明场景、保持动作和录像能够工作；完整控制与模型连接仍需通过单回合运行验证。

## 结束后做什么

```bash
gpt-gear summarize outputs/libero_one
```

将路径换成刚才的输出目录，按 [结果指南](results.zh-CN.md) 查看成功判定、录像和日志。

接下来可以：

- 尝试 [上下文学习（ICL）](reference-protocol.zh-CN.md)：准备示范文字、视频或轨迹，再启动新回合。
- 使用 [队列](queues.zh-CN.md) 评测更多任务。

### 用 JSON 保存单任务配置（可选）

也可以使用 [`configs/single_task/`](../configs/single_task/) 中的 JSON 指定任务。每份配置仅含 1 个 episode；修改环境路径、任务和 seed 后执行：

```bash
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_config_one
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_config_one --run
```

第一条只打印计划，第二条运行一个回合。各环境的配置清单见[配置说明](../configs/README.zh-CN.md)；批量复现使用 `configs/queues/`。
