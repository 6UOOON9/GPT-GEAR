# 安装与环境准备

[English](installation.md) | **简体中文**

[文档导航](README.zh-CN.md) · 下一步：[运行第一个任务](running.zh-CN.md)

GPT-GEAR 使用两套 Python：工具环境运行命令行与 MCP 服务，仿真环境运行已安装的仿真器。这样可以保留各仿真器自己的依赖版本。

## 1. 准备运行条件

| 组件 | 要求 |
|---|---|
| 系统 | 建议 Linux；GPU、驱动和渲染条件按所选仿真器准备 |
| 工具 Python | Python 3.11+，下面使用 Python 3.12 |
| 仿真 Python | 使用对应仿真器的现有解释器；公共仿真模块兼容 Python 3.10+ |
| Codex CLI | 在当前用户的 `PATH` 中，并已完成认证 |
| 视频工具 | 录像需要 FFmpeg 和可用的编码器；视频参考需要 FFmpeg、FFprobe |
| 仿真源码与资产 | 单独安装；本仓库不包含仿真器、任务资产或示范数据 |

RoboDojo 可使用已有 Python 3.11 环境，LIBERO-plus 可使用已有 Python 3.10 环境。优先保留仿真器原有的解释器与依赖配置。各环境的源码目录、资产和任务配置要求见 [环境配置指南](README.zh-CN.md#环境配置)。

### 先安装所需的仿真环境

**运行机器人任务前，请先按上游说明安装要使用的仿真环境、依赖和资产，并跑通其原生示例。只需安装你要使用的环境，不必安装全部环境。** 安装 GPT-GEAR 不会自动安装这些环境或下载资产。

| 环境 | 获取来源 | 安装与资产准备 |
|---|---|---|
| RoboDojo | [RoboDojo-Benchmark/RoboDojo](https://github.com/RoboDojo-Benchmark/RoboDojo) | [安装与资源下载](https://robodojo-benchmark.com/doc/usage/install-and-download/) |
| LIBERO-plus | [sylvestf/LIBERO-plus](https://github.com/sylvestf/LIBERO-plus) | [README 的 Installation 部分](https://github.com/sylvestf/LIBERO-plus#readme)，包含附加依赖和资产下载入口 |
| LIBERO-GeoMotion | [uooon/LIBERO-GeoMotion](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion) | [安装教程](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion#installation) |
| RoboCasa GR1 | [robocasa/robocasa-gr1-tabletop-tasks](https://github.com/robocasa/robocasa-gr1-tabletop-tasks) | [Getting Started](https://github.com/robocasa/robocasa-gr1-tabletop-tasks#getting-started)，包含配套 robosuite 和场景资产 |
| UniVTAC | [univtac/UniVTAC](https://github.com/univtac/UniVTAC) | [Installation Guide](https://github.com/univtac/UniVTAC/blob/main/docs/Installation.md) |
| RoboTwin | [RoboTwin-Platform/RoboTwin](https://github.com/RoboTwin-Platform/RoboTwin) | [Install & Download](https://robotwin-platform.github.io/doc/usage/robotwin-install.html) |

先确认原生示例能够创建场景、渲染画面并执行动作，再继续安装下面的 GPT-GEAR 工具环境。上游文档中的其他模型训练或策略服务属于各项目自身流程，GPT-GEAR 使用自己的 Codex 控制入口。

接入时，`--env-root` 指向所选仿真仓库，`--sim-python` 指向该环境已安装依赖的 Python 解释器。GR1 还需提供 `--robosuite-root` 和包含任务 HDF5 环境配置的 `--data-root`，详见 [GR1 环境配置](environments/robocasa-gr1.zh-CN.md)。

## 2. 安装 GPT-GEAR

取得本仓库后，在仓库根目录执行：

```bash
python3.12 -m venv .venvs/codex-mcp
.venvs/codex-mcp/bin/python -m pip install -e '.[mcp]'
source .venvs/codex-mcp/bin/activate
gpt-gear --help
```

每次打开新终端后，在仓库根目录重新执行 `source .venvs/codex-mcp/bin/activate`。也可以直接调用 `.venvs/codex-mcp/bin/gpt-gear`，无需激活。

`.[mcp]` 安装固定版本的 MCP SDK。仿真通过 `--sim-python` 指定自己的解释器，无需向其中安装 MCP，也无需为本项目升级它的仿真依赖。启动器会为仿真子进程配置本项目的模块路径。

检查外部工具：

```bash
command -v codex
codex --version
ffmpeg -version
ffprobe -version
```

Codex 认证由当前系统用户自行配置。版本命令和 `doctor` 均不会验证模型认证；正式运行前，确认该用户的 Codex 能正常访问所选模型。GPT-GEAR 默认使用已有模型配置，也可以在 `run` / `queue` 后加 `--codex-model 模型名`。

## 3. 运行预检

以 LIBERO-plus 为例：

```bash
gpt-gear doctor --benchmark libero-plus --task libero_spatial/0 \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python
```

预检会核对所选环境的任务、资源与依赖，并检查 MCP 和 Codex CLI。通过后继续 [运行第一个任务](running.zh-CN.md)。它不会创建仿真场景，因此渲染、实际运动和模型连接仍需在后续运行中验证。

## 运行目录与配置

| 配置 | 默认行为 |
|---|---|
| 输出目录 | 每次 `run` 使用全新目录；队列可按原配置续跑 |
| 缓存 | 当前目录下 `.cache/gpt-gear`；可用 `--cache-dir` 修改 |
| GPU | `--device-id 0` |
| 本地控制端口 | `--port 8092`；并行启动独立运行时使用不同端口与输出目录 |
| MCP 解释器 | 默认使用启动 `gpt-gear` 的解释器；可用 `--codex-mcp-python` 指定 |

控制服务只监听 localhost。启动器为当前 Codex 子进程配置 MCP，不改全局 Codex 配置；该子进程使用 `danger-full-access` 和 `approval_policy=never`，提示词中的访问限制不构成操作系统隔离。

工具依赖由 [pyproject.toml](../pyproject.toml) 管理，按上面的安装命令即可安装。开发依赖和测试命令见 [贡献指南](../CONTRIBUTING.zh-CN.md)。
