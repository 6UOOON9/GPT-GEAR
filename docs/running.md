# Run your first task

**English** | [简体中文](running.zh-CN.md)

[Documentation](README.md) · Prerequisite: [Installation](installation.md) · Next: [Inspect results](results.md) · [In-context learning (optional)](reference-protocol.md)

This page provides single-episode commands for all supported environments. Each run creates a separate simulation process and Codex session. The examples below run without demonstrations. To provide demonstration text, video, or trajectories, follow the [in-context learning (ICL) guide](reference-protocol.md).

Read [before you run](#before-you-run), then choose your environment: [RoboDojo](#robodojo) · [LIBERO-plus](#libero-plus) · [LIBERO-GeoMotion](#libero-geomotion) · [RoboCasa GR1](#robocasa-gr1) · [UniVTAC](#univtac) · [RoboTwin](#robotwin). Consult other sections as needed: [Common options](#common-run-options) · [Model-free interface checks](#model-free-interface-checks) · [Results and next steps](#after-the-run).

## Before you run

Activate the tool environment from the repository root and replace `/path/to/...` in examples with your paths:

```bash
source .venvs/codex-mcp/bin/activate
```

Run `doctor` for the task you plan to use first. Replace `run TASK_NAME OUTPUT_DIRECTORY` in the commands below with `doctor --task TASK_NAME`, retaining environment paths and task options. For example:

```bash
gpt-gear doctor --benchmark robotwin --task adjust_bottle \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python --task-config clean
```

`doctor` does not start the simulator or model, or verify model authentication. Environments that support it can first use a [model-free interface check](#model-free-interface-checks) to confirm scene loading and recording.

The output directory for each `run` must not already exist. Do not create it beforehand or reuse it. Relative paths are resolved against the current working directory.

## RoboDojo

```bash
gpt-gear run align_blocks outputs/robodojo_one \
  --benchmark robodojo \
  --env-root /path/to/RoboDojo \
  --sim-python /path/to/robodojo/bin/python \
  --seed 0 --layout-id 0
```

Replace `align_blocks` with a task supported by the host and equipped with evaluation layouts. `--layout-id` selects a layout for the specified seed and defaults to `0`. RoboDojo uses the host's native execution budget, scoring, and recording.

See [RoboDojo configuration](environments/robodojo.md) for source code, submodules, and evaluation-layout requirements.

## LIBERO-plus

```bash
gpt-gear run libero_spatial/0 outputs/libero_one \
  --benchmark libero-plus \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python \
  --seed 0 --init-state-index 0 --max-native-steps 600
```

Tasks use `suite/task_id`. `--init-state-index` selects the task's initial state and defaults to `0`. Images default to 256×256, with a 20 Hz control frequency. The 600-native-step budget includes the first 10 initialization settling steps.

See [LIBERO-plus configuration](environments/libero-plus.md) for source code, assets, and initial states.

## LIBERO-GeoMotion

```bash
gpt-gear run libero_rp/0 outputs/geomotion_one \
  --benchmark libero-geomotion \
  --env-root /path/to/LIBERO-GeoMotion \
  --sim-python /path/to/geomotion/bin/python \
  --seed 0 --init-state-index 0 --max-native-steps 4000
```

Tasks range from `libero_rp/0` to `libero_rp/35`, with initial state 0. Images default to 256×256, with a 20 Hz control frequency. The budget is 4000 native steps without initialization settling.

See [LIBERO-GeoMotion configuration](environments/libero-geomotion.md) for environment paths and references. Add demonstrations using the [in-context learning guide](reference-protocol.md).

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

GR1 additionally needs robosuite source and an HDF5 data directory. The example task requires `PnPCupToDrawerClose.hdf5` under `data_root`; its environment configuration creates the scene and is required even without references.

Default inputs are RGB + measured depth. The 1,000-native-step budget includes 10 initialization settling steps. For RGB only, use `--measured-depth false --depth-estimation false`.

See the [task list](../src/environments/tasks.json) for the 24 available tasks and [GR1 configuration](environments/robocasa-gr1.md) for depth options.

## UniVTAC

```bash
gpt-gear run insert_HDMI outputs/univtac_one \
  --benchmark univtac \
  --env-root /path/to/UniVTAC \
  --sim-python /path/to/univtac/bin/python \
  --seed 1468828686 --tactile-mode force
```

Task names are case-sensitive. See the [task list](../src/environments/tasks.json) for the 8 supported tasks. The default budget is 400 control steps and 40 model actions. Each control step executes at most 6 physics steps; success or early termination interrupts remaining physics steps.

`--tactile-mode` accepts `none`, `image`, `force`, or `image-force`: no tactile inputs, tactile images, resultant tactile forces, or both. Every mode retains RGB and proprioception; the default is `force`.

See [UniVTAC configuration](environments/univtac.md) for tactile semantics and action parameters.

## RoboTwin

```bash
gpt-gear run adjust_bottle outputs/robotwin_one \
  --benchmark robotwin \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python \
  --seed 0 --task-config clean --max-native-steps 1000
```

Use a host task name such as `adjust_bottle`. `--task-config` accepts `clean` or `random` and defaults to `clean`. The default budget is 1,000 native synchronized dual-arm calls, excluding initialization.

See [RoboTwin configuration](environments/robotwin.md) for assets, observations, and Clean/Random evaluation details.

## Common run options

| Option | Purpose |
|---|---|
| `--codex-model MODEL_NAME` | Override the local default model configuration |
| `--codex-context-window TOKENS` | Codex context window, default 272000. Use a size supported by the selected model; automatic context compaction remains enabled. |
| `--reference-max-frames 48` | Maximum sequence images per view (minimum 2); see [reference sampling](reference-protocol.md#4-add-references-to-an-episode-or-queue). |
| `--device-id 0` | Select the GPU |
| `--port 8092` | Select the local control port |
| `--depth-estimation false` | Disable required model depth-estimation declarations |
| `--cache-dir PATH` | Set the cache root used for reference preprocessing and related operations |
| `--codex-mcp-python PATH` | Select a separate MCP interpreter |
| `--codex-startup-timeout 600` | Seconds to wait for simulator readiness |
| `--codex_connect_timeout 600` | Session connection timeout in seconds |
| `--codex_idle_timeout 600` | Timeout in seconds without native-action-count progress after connection; read-only queries do not reset it |
| `--codex_request_timeout 600` | Request-processing timeout in seconds |

GR1 enables measured depth and disables estimation declarations by default. Other environments enable estimation declarations by default. These declarations are the model's image-based estimates, not ground-truth simulation depth.

Environment-specific options cannot be used across environments. Include the benchmark when viewing full help, for example:

```bash
gpt-gear run --benchmark univtac --help
```

## Model-free interface checks

LIBERO-plus, LIBERO-GeoMotion, GR1, UniVTAC, and RoboTwin support `--smoke`. This starts a real simulator, saves the initial observation, executes one hold action, then saves the final state and video. It does not start Codex or call a model. The result is `interface_smoke_only` and does not count toward task success rate. RoboDojo does not currently provide this entry point; use the preflight and single-episode commands above.

Complete `doctor` preflight first, then select your environment's command below. Run from the repository root and add this project's `src` to the simulation process's `PYTHONPATH`. Replace all paths; the output directory must not already exist:

```bash
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

### LIBERO-plus interface check

```bash
/path/to/libero/bin/python -m environments.libero_plus.simulator \
  libero_spatial/0 outputs/libero_interface --smoke \
  --benchmark libero-plus --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python --seed 0 --init-state-index 0
```

### LIBERO-GeoMotion interface check

```bash
/path/to/geomotion/bin/python -m environments.libero_geomotion.simulator \
  libero_rp/0 outputs/geomotion_interface --smoke \
  --benchmark libero-geomotion --env-root /path/to/LIBERO-GeoMotion \
  --sim-python /path/to/geomotion/bin/python --seed 0 --init-state-index 0
```

### RoboCasa GR1 interface check

```bash
/path/to/robocasa/bin/python -m environments.robocasa_gr1.simulator \
  PnPCupToDrawerClose outputs/gr1_interface --smoke \
  --benchmark robocasa-gr1 --env-root /path/to/robocasa-gr1-tabletop-tasks \
  --robosuite-root /path/to/robosuite-gr1 --data-root /path/to/robocasa_data \
  --sim-python /path/to/robocasa/bin/python
```

### UniVTAC interface check

```bash
/path/to/univtac/bin/python -m environments.univtac.simulator \
  insert_HDMI outputs/univtac_interface --smoke \
  --benchmark univtac --env-root /path/to/UniVTAC \
  --sim-python /path/to/univtac/bin/python --tactile-mode force
```

### RoboTwin interface check

```bash
/path/to/robotwin/bin/python -m environments.robotwin.simulator \
  adjust_bottle outputs/robotwin_interface_clean --smoke \
  --benchmark robotwin --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python \
  --task-config clean --seed 0 --max-native-steps 10
```

To check Random, change `--task-config` to `random` and use a fresh output directory.

### Inspecting check results

`smoke.json` records the interface-check result, and `host.json` records loaded source code and dependencies. Inspect images in `observations/` and encoding status in `video.json`. These commands run the simulation entry point directly, so exceptions appear in the current terminal; when launched with `gpt-gear run`, inspect `server.log` instead. See the [results guide](results.md) for troubleshooting.

A passing interface check only establishes that scene loading, a hold action, and video recording work. Full control and model connectivity still require a single-episode run.

## After the run

```bash
gpt-gear summarize outputs/libero_one
```

Replace the path with your output directory and follow the [results guide](results.md) to inspect success, videos, and logs.

Next, you can:

- Try [in-context learning (ICL)](reference-protocol.md): prepare demonstration text, video, or trajectories, then start a new episode.
- Use a [queue](queues.md) to evaluate more tasks.

### Save a single-task configuration in JSON (optional)

You can also specify a task with JSON in [`configs/single_task/`](../configs/single_task/). Each file contains one episode. Update environment paths, task, and seed, then run:

```bash
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_config_one
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_config_one --run
```

The first command prints the plan; the second runs one episode. See the [configuration guide](../configs/README.md) for all supported environments. Use `configs/queues/` for batch reproduction.
