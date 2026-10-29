# 运行配置

[English](README.md) | **简体中文**

[文档导航](../docs/README.zh-CN.md) · [单回合运行](../docs/running.zh-CN.md) · [队列指南](../docs/queues.zh-CN.md)

配置按用途分为两类：

- **`queues/`：队列式评测。** 固定任务、seed、初始化和输入条件，用于复现已有评测流程或运行条件对比。
- **`single_task/`：单任务测试。** 每个文件仅包含 **1 个 episode**，用于试跑环境、调试任务或单独测一个回合。

两类都使用 `version: 2` 格式，通过 `gpt-gear queue` 加载；`single_task/` 中的 `episodes` 只有一项。无需 JSON、直接用命令行指定任务时，使用 [`gpt-gear run`](../docs/running.zh-CN.md)。

## 队列式评测

| 配置 | 评测内容 | episode 数 |
|---|---|---:|
| [robodojo.json](queues/robodojo.json) | RoboDojo：42 个任务，seed 0、layout 9；其中 34 个提供参考输入，其余 8 个不带参考 | 42 |
| [libero_plus.json](queues/libero_plus.json) | LIBERO-plus：5 个基础任务 × 10 个扰动变体，每项运行一次 | 50 |
| [libero_geomotion.json](queues/libero_geomotion.json) | LIBERO-GeoMotion：36 场景；6 类有示范（24 场景），3 类无示范（12 场景） | 36 |
| [robocasa_gr1.json](queues/robocasa_gr1.json) | RoboCasa GR1：24 个任务 × 20 个预设 seed | 480 |
| [univtac.json](queues/univtac.json) | UniVTAC：8 个任务 × 20 个预设 seed，默认 `force` 模式 | 160 |
| [robotwin.json](queues/robotwin.json) | RoboTwin：50 个任务 × 2 种配置 × 5 个 seed（均为 `0–4`），全部带参考输入 | 500 |

GR1 和 UniVTAC 的批量 seed 沿用来源项目预设，不代表官方 seed split。参考数据需另行准备。

RoboTwin 队列按任务名字典序排列，每个任务依次使用 seed `0–4` 跑 `clean`、seed `0–4` 跑 `random`，共 250 个 clean 和 250 个 random 回合。50 个任务名核对自 RoboTwin 的 `envs/` 目录中的任务模块及配套任务说明，并与 RPent 的 RoboTwin 评测任务集合交叉检查；seed 按本队列规则设置。每个任务在两种配置和所有 seed 下共用其同名示范。

UniVTAC 的模态可按需设置：JSON 中为相应 episode 设置 `tactile_mode`，可选 `none`、`image`、`force`、`image-force`，默认 `force`；直接使用 `gpt-gear run` 时通过 `--tactile-mode` 指定。

LIBERO-plus 的完整任务标识与执行顺序见 [队列配置](queues/libero_plus.json) 中的 `episodes`。`task` 使用 `suite/Task编号`（0-based），不使用 1-based 的 Classification ID。每项沿用单任务配置的 `seed=0`、`init_state_index=0`、`max_native_steps=600`，未配置参考输入。任务名称中的 `initstate_N` 属于变体名称，不作为 `init_state_index`。

## 单任务测试

| 配置 | 任务 | 初始条件 / 模式 |
|---|---|---|
| [robodojo.json](single_task/robodojo.json) | RoboDojo `align_blocks` | seed 0、layout 0 |
| [libero_plus.json](single_task/libero_plus.json) | LIBERO-plus `libero_spatial/0` | seed 0、init state 0 |
| [libero_geomotion.json](single_task/libero_geomotion.json) | LIBERO-GeoMotion `libero_rp/0` | seed 0，固定初态 0，无参考输入 |
| [robocasa_gr1.json](single_task/robocasa_gr1.json) | RoboCasa GR1 `PnPCupToDrawerClose` | seed 1365783547 |
| [univtac.json](single_task/univtac.json) | UniVTAC `insert_HDMI` | seed 1468828686、`force` |
| [robotwin.json](single_task/robotwin.json) | RoboTwin `adjust_bottle` | seed 0、`clean` |

修改唯一 episode 中的 `task`、`seed` 和该环境支持的选项即可指定要测试的任务。保持 `episodes` 只有一项，就只运行一个回合。单任务配置执行时也会调用模型；无模型接口检查见 [运行指南](../docs/running.zh-CN.md#无模型接口检查)。

## 使用方法

在仓库根目录执行。先复制配置，将所有 `/path/to/...` 环境路径占位符替换为自己的安装路径；JSON 内的相对路径以**配置文件所在目录**为基准，复制到其他目录时也要调整路径。建议使用绝对路径，不能在 JSON 中写 `$HOME` 等 shell 变量。GR1 还需配置 `robosuite_root` 和 `data_root`。仿真 Python 占位路径统一为 `/path/to/<benchmark>/bin/python`。参考路径统一为 `/path/to/reference_demo/<环境>/<任务>/`，环境目录名与下载数据保持一致（如 `RoboDojo`、`LIBERO-GeoMotion`）；视频指向其 `videos/` 子目录，文本为 `steps.txt`，轨迹描述为 `trajectory.json`。

```bash
# 只跑一个 episode：先检查计划，再执行。
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_one
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_one --run

# 复现队列评测：先检查计划，再执行。
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20 --run

gpt-gear summarize outputs/gr1_24x20
```

不加 `--run` 只解析并打印计划，不验证仿真安装。首次运行先执行 `doctor`。复现评测还需匹配环境版本、资产、参考数据和模型配置，见[安装指南](../docs/installation.zh-CN.md)；续跑、重试及字段规则见[队列指南](../docs/queues.zh-CN.md)。
