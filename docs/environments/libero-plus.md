# LIBERO-plus configuration

**English** | [简体中文](libero-plus.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#libero-plus) · [Queues](../queues.md)

LIBERO-plus provides single-arm manipulation, two-view RGB, and multiple task variants. This page covers source code, task IDs, and initialization options; see the [running guide](../running.md) for the shared workflow.

## Source code and assets

Use an installed LIBERO-plus source tree and its simulation Python. Point `--env-root` to the LIBERO-plus directory. The `libero/libero/assets`, `bddl_files`, and `init_files` directories in that tree must be ready. You can use an existing Python 3.10 simulation environment while retaining its dependencies.

Each episode generates its own `libero_config/config.yaml`, selected through the subprocess's `LIBERO_CONFIG_PATH`. The global `~/.libero/config.yaml` is not modified.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | `suite/task_id`, such as `libero_spatial/0`; IDs are zero-based |
| Initialization | `--seed 0 --init-state-index 0` |
| Observations | agentview / robot0_eye_in_hand RGB and single-arm state; `--image-size 256` |
| Budget | `--max-native-steps 600`, including 10 initialization settling steps; minimum 11 |
| Control frequency | 20 Hz |
| Depth | Model depth-estimation declarations enabled by default; disable with `--depth-estimation false`; no measured depth |

`--init-state-index` selects a task's initial state. `initstate_N` in a task variant name is not this option. LIBERO-plus does not accept `--layout-id`. Before the first run, you can perform a [model-free interface check](../running.md#model-free-interface-checks).

## References and evaluation configurations

Reference trajectories use `libero-codex-trajectory-v1`, with `robot0_grip_site` as the control point. See the [reference protocol](../reference-protocol.md#libero-plus) for video views and action fields, and the [video-to-text guide](../reference-format.md) for text generation.

The [single-task configuration](../../configs/single_task/libero_plus.json) uses `libero_spatial/0`. The [queue configuration](../../configs/queues/libero_plus.json) contains 50 variants of 5 base tasks, each with seed 0, init state 0, 600 native steps, and no references. See its `episodes` for complete task IDs and execution order. For execution and resuming, see the [queue guide](../queues.md).
