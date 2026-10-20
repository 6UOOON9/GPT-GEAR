# UniVTAC configuration

**English** | [简体中文](univtac.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#univtac) · [Queues](../queues.md)

UniVTAC provides single-arm manipulation, two-view RGB, and optional tactile inputs. This page covers dependencies, control budgets, and tactile modes; see the [running guide](../running.md) for the shared workflow. The adapter is experimental; a [model-free interface check](../running.md#model-free-interface-checks) is recommended before the first run.

## Source code and assets

Point `--env-root` to a UniVTAC repository with assets and simulation dependencies prepared; it must contain `envs/_base_task.py`. Use that environment's own interpreter for `--sim-python`. The entry point starts Isaac Lab before importing tasks.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | 8 tasks in the [task list](../../src/environments/tasks.json), such as `insert_HDMI`; names are case-sensitive |
| Initialization | Selected by `--seed`; layout-id / init-state-index are not accepted |
| RGB observations | head / wrist; `--image-width 480 --image-height 270` |
| Tactile inputs | `--tactile-mode force`, resultant tactile forces on both sides |
| Control-step budget | `--max-native-steps 400` |
| Action budget | `--max-policy-actions 40` |
| Control decimation | `--control-decimation 6`, at most 6 physics steps per control step, interrupted on success or early termination; initialization physics steps are recorded separately |
| Depth | Model depth-estimation declarations enabled by default; disable with `--depth-estimation false`; no measured depth |

### Tactile modes

| `--tactile-mode` | Inputs in addition to RGB and proprioception |
|---|---|
| `none` | None |
| `image` | Tactile images |
| `force` (default) | Resultant tactile forces on both sides |
| `image-force` | Tactile images and resultant forces |

Tactile images are separate from ordinary camera calibration. Resultant forces are converted from UIPC's last solver contact gradient, in N and the robot_base frame; they are not equivalent to independently calibrated physical force sensors. Disabling model inputs does not disable internal tactile updates, preserving official success determination.

### Gripper control and step accounting

Actions use `robot0.gripper_position_m` for finger position in meters, with range `[0,0.04]`. This is not total aperture or a binary open/close command. Control iterations, physics ticks, and model actions are counted separately. Match budgets, `control_decimation`, and tactile modes when comparing evaluations. See the [architecture guide](../architecture.md#univtac) for control implementation details.

## References and evaluation configurations

References use the continuous-gripper format `univtac-codex-trajectory-v2`. Old binary-gripper demonstrations are not automatically converted. Video views are head / wrist; reference packages do not contain live tactile data. See the [reference protocol](../reference-protocol.md#univtac) for fields and the [video-to-text guide](../reference-format.md) for text generation.

The [single-task configuration](../../configs/single_task/univtac.json) uses `insert_HDMI`. The [queue configuration](../../configs/queues/univtac.json) contains 8 tasks × 20 seeds, totaling 160 episodes. Seeds follow source-project presets, not an official seed split.

The queue defaults to `force`; set `tactile_mode` per episode to change it. Modality participates in episode identity, and summaries group results by modality. See the [queue guide](../queues.md) for execution and resuming.
