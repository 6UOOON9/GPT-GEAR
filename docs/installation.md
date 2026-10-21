# Installation and environment setup

**English** | [简体中文](installation.zh-CN.md)

[Documentation](README.md) · Next: [Run your first task](running.md)

GPT-GEAR uses two Python environments: the tool environment runs the CLI and MCP service, while the simulation environment runs the installed simulator. This preserves each simulator's dependency versions.

## 1. Prepare prerequisites

| Component | Requirement |
|---|---|
| System | Linux is recommended; prepare the GPU, drivers, and rendering stack required by your simulator |
| Tool Python | Python 3.11+; the examples use Python 3.12 |
| Simulation Python | The simulator's existing interpreter; shared simulation modules support Python 3.10+ |
| Codex CLI | Available on the current user's `PATH` and authenticated |
| Video tools | Recording requires FFmpeg and a working encoder; video references require FFmpeg and FFprobe |
| Simulator source and assets | Installed separately; this repository does not include simulators, task assets, or demonstration data |

RoboDojo can use an existing Python 3.11 environment, and LIBERO-plus can use an existing Python 3.10 environment. Prefer the simulator's original interpreter and dependencies. See [environment configuration](README.md#environment-configuration) for source paths, assets, and task requirements.

### Install your simulation environment first

**Before running robot tasks, follow the upstream instructions to install your chosen simulator, dependencies, and assets, and run its native example. You only need the environments you plan to use, not every supported environment.** Installing GPT-GEAR does not install these environments or download assets automatically.

| Environment | Source | Installation and assets |
|---|---|---|
| RoboDojo | [RoboDojo-Benchmark/RoboDojo](https://github.com/RoboDojo-Benchmark/RoboDojo) | [Installation and downloads](https://robodojo-benchmark.com/doc/usage/install-and-download/) |
| LIBERO-plus | [sylvestf/LIBERO-plus](https://github.com/sylvestf/LIBERO-plus) | [README Installation section](https://github.com/sylvestf/LIBERO-plus#readme), including extra dependencies and asset downloads |
| LIBERO-GeoMotion | [uooon/LIBERO-GeoMotion](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion) | [Installation guide](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion#installation) |
| RoboCasa GR1 | [robocasa/robocasa-gr1-tabletop-tasks](https://github.com/robocasa/robocasa-gr1-tabletop-tasks) | [Getting Started](https://github.com/robocasa/robocasa-gr1-tabletop-tasks#getting-started), including the matching robosuite and scene assets |
| UniVTAC | [univtac/UniVTAC](https://github.com/univtac/UniVTAC) | [Installation Guide](https://github.com/univtac/UniVTAC/blob/main/docs/Installation.md) |
| RoboTwin | [RoboTwin-Platform/RoboTwin](https://github.com/RoboTwin-Platform/RoboTwin) | [Install & Download](https://robotwin-platform.github.io/doc/usage/robotwin-install.html) |

Confirm that the native example can create a scene, render images, and execute actions before installing the GPT-GEAR tool environment below. Model training or policy services described upstream belong to those projects' own workflows; GPT-GEAR uses its own Codex control entry point.

Set `--env-root` to the selected simulator repository and `--sim-python` to the interpreter with its dependencies installed. GR1 also needs `--robosuite-root` and `--data-root` containing task HDF5 environment configurations; see [GR1 configuration](environments/robocasa-gr1.md).

## 2. Install GPT-GEAR

After obtaining this repository, run from its root:

```bash
python3.12 -m venv .venvs/codex-mcp
.venvs/codex-mcp/bin/python -m pip install -e '.[mcp]'
source .venvs/codex-mcp/bin/activate
gpt-gear --help
```

In each new terminal, run `source .venvs/codex-mcp/bin/activate` again from the repository root. Alternatively, call `.venvs/codex-mcp/bin/gpt-gear` directly without activating it.

`.[mcp]` installs a pinned MCP SDK version. The simulator uses its own interpreter through `--sim-python`; it does not need MCP installed or its simulation dependencies upgraded for this project. The launcher sets this project's module path for the simulation subprocess.

Check external tools:

```bash
command -v codex
codex --version
ffmpeg -version
ffprobe -version
```

Configure Codex authentication for the current system user. Version commands and `doctor` do not verify model authentication; before a full run, confirm that this user's Codex can access the selected model. GPT-GEAR uses the existing model configuration by default, or you can append `--codex-model MODEL_NAME` to `run` / `queue`.

## 3. Run preflight checks

For example, with LIBERO-plus:

```bash
gpt-gear doctor --benchmark libero-plus --task libero_spatial/0 \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python
```

Preflight checks verify the selected environment's task, resources, and dependencies, along with MCP and the Codex CLI. Once they pass, continue to [your first task](running.md). Preflight does not create a simulation scene, so rendering, actual motion, and model connectivity still need validation during a run.

## Output directories and configuration

| Setting | Default behavior |
|---|---|
| Output directory | Each `run` uses a fresh directory; queues can resume with the original configuration |
| Cache | `.cache/gpt-gear` under the current directory; change with `--cache-dir` |
| GPU | `--device-id 0` |
| Local control port | `--port 8092`; use different ports and output directories for independent concurrent runs |
| MCP interpreter | The interpreter that launches `gpt-gear`; override with `--codex-mcp-python` |

The control service listens only on localhost. The launcher configures MCP for the current Codex subprocess without changing global Codex configuration. That subprocess uses `danger-full-access` and `approval_policy=never`; access restrictions in prompts do not provide operating-system isolation.

Tool dependencies are managed by [pyproject.toml](../pyproject.toml) and installed by the commands above. See [contributing](../CONTRIBUTING.md) for development dependencies and test commands.
