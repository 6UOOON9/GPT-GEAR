# LIBERO-GeoMotion configuration

**English** | [简体中文](libero-geomotion.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#libero-geomotion) · [Queues](../queues.md)

LIBERO-GeoMotion provides single-arm manipulation, two-view RGB, and 36 scenes across 9 task families. It is selected independently with `--benchmark libero-geomotion`. This page covers paths, task IDs, and reference options; see the [running guide](../running.md) for the shared workflow.

## Source code and assets

Prepare the environment using the [upstream installation guide](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion#installation). Point `--env-root` to the installed LIBERO-GeoMotion source directory and `--sim-python` to its simulation Python.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | `libero_rp/0` through `libero_rp/35`; see the [task list](../../src/environments/tasks.json) |
| Initialization | `--seed 0 --init-state-index 0`; only initial state 0 is supported |
| Observations | agentview / robot0_eye_in_hand RGB and single-arm state; `--image-size 256` |
| Budget | `--max-native-steps 4000`, with no initialization settling steps |
| Control frequency | 20 Hz |
| Depth | Model depth-estimation declarations enabled by default; disable with `--depth-estimation false`; no measured depth |

Before the first run, you can perform a [model-free interface check](../running.md#libero-geomotion-interface-check).

## References and evaluation configurations

Prepare demonstrations using the [upstream documentation](https://huggingface.co/datasets/uooon/LIBERO-GeoMotion). Select video, text, and trajectories through the shared reference options. Reference trajectories use `libero-codex-trajectory-v1`, with `robot0_grip_site` as the control point. See the [reference protocol](../reference-protocol.md#libero-geomotion) for fields and the [video-to-text guide](../reference-format.md#libero-geomotion-two-view-video) for text generation.

The [single-task configuration](../../configs/single_task/libero_geomotion.json) uses `libero_rp/0` without references. The [full queue](../../configs/queues/libero_geomotion.json) contains 36 scenes across 9 task families, each with seed 0, init state 0, and 4000 native steps.

**Six task families have demonstrations; the remaining three have none.** The 24 scenes in the six demonstrated families use their respective family references 0, 4, 8, 26, 28, and 34, with video, text, and trajectories. The three families covering scenes 12–15, 16–19, and 20–23 total 12 scenes and run without references; no additional demonstrations are required.

Replace the `/path/to/...` example paths before running. See the queue's `episodes` for complete task IDs and reference selections, and the [queue guide](../queues.md) for execution and resuming.
