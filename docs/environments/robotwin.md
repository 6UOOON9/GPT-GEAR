# RoboTwin configuration

**English** | [简体中文](robotwin.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#robotwin) · [Queues](../queues.md)

RoboTwin provides dual-arm manipulation, three-view RGB, and Clean/Random scene configurations. This page covers assets, control options, and evaluation differences; see the [running guide](../running.md) for the shared workflow. The adapter is experimental; a [model-free interface check](../running.md#model-free-interface-checks) is recommended before the first run.

## Source code and assets

Point `--env-root` to an installed RoboTwin repository with task source code, task descriptions, `env_cfg/task_config/`, and `assets/` ready. Use the environment's own interpreter for `--sim-python`, with SAPIEN, PyTorch, NumPy, Pillow, PyYAML, and the host's planning and rendering dependencies. Recording requires FFmpeg/libx264.

The adapter currently supports a single shared dual-arm robot in the configuration. `_embodiment_config.yml` identifies the robot directory and its `config.yml`; asset paths in that file must work on your machine.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | Host task name, such as `adjust_bottle`, not a sorted numeric ID |
| Initialization | `--seed 0`; layout-id / init-state-index are not accepted |
| Scene configuration | `--task-config clean`; `clean` / `random` use `demo_clean.yml` / `demo_randomized.yml` respectively |
| Observations | head_camera / left_camera / right_camera RGB and dual-arm state; `--image-size 256` |
| Budget | `--max-native-steps 1000`, measured in native synchronized dual-arm calls; initialization is excluded and physics steps are counted separately |
| Actions | Synchronized pose deltas for both arms; grippers use `open` / `close`, while omitted or `null` values retain the target |
| Depth | Model depth-estimation declarations enabled by default; disable with `--depth-estimation false`; no measured depth |

Keep tasks, seeds, budgets, and input conditions matched when comparing Clean and Random. This adapter evaluates the specified seeds directly, without expert filtering or automatically filling valid-sample quotas. Match sample-selection procedures when comparing against other evaluations.

## References and evaluation configurations

Reference trajectories use `robotwin-codex-dual-trajectory-v1`. Prepare files in advance. See the [reference protocol](../reference-protocol.md#robotwin) for video mappings and action semantics, and the [text-generation guide](../reference-format.md#robotwin-three-view-expert-video) for three-view video annotation.

The [single-task configuration](../../configs/single_task/robotwin.json) uses `adjust_bottle`, seed 0, and `clean`. The [queue configuration](../../configs/queues/robotwin.json) contains 50 tasks × 2 configurations × 5 seeds, totaling 500 episodes. See the [queue guide](../queues.md) for execution and resuming, and the [results guide](../results.md) for videos and logs.
