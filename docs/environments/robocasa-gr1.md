# RoboCasa GR1 configuration

**English** | [简体中文](robocasa-gr1.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#robocasa-gr1) · [Queues](../queues.md)

RoboCasa GR1 provides dual-arm manipulation and measured depth aligned with RGB. This page covers source code, HDF5 configuration, and depth options; see the [running guide](../running.md) for the shared workflow. The adapter is experimental; a [model-free interface check](../running.md#model-free-interface-checks) is recommended before the first run.

## Source code and assets

Prepare installed RoboCasa and robosuite source trees with their simulation Python. Retain their MuJoCo, Mink, and NumPy dependency configuration.

| Option | Required content |
|---|---|
| `--env-root` | RoboCasa source directory |
| `--robosuite-root` | robosuite source directory |
| `--data-root` | Directory containing `<task_name>.hdf5` |
| `--sim-python` | Python interpreter with simulation dependencies installed |

The HDF5 field `data.attrs['env_args']` supplies the official environment configuration. **Creating an environment requires this configuration even without reference demonstrations.** It must use `WHOLE_BODY_MINK_IK` with absolute/base/axis_angle inputs, not joint-angle inputs.

The source adapter uses the `nvidia/PhysicalAI-Robotics-GR00T-Teleop-Sim` dataset. This project does not download it automatically.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | 24 tasks in the [task list](../../src/environments/tasks.json), such as `PnPCupToDrawerClose` |
| Initialization | Selected by `--seed`; layout-id / init-state-index are not accepted |
| Observations | egoview RGB, dual-arm state, and measured depth; `--image-size 256` |
| Budget | `--max-native-steps 1000`, including 10 initialization settling steps; minimum 11 |
| Control frequency | 20 Hz |
| Depth | `--measured-depth true --depth-estimation false` by default |

### Depth modes

| Desired inputs | Options |
|---|---|
| RGB + measured depth (default) | No additional options |
| RGB only, without depth declarations | `--measured-depth false --depth-estimation false` |
| RGB + model depth-estimation declarations | `--measured-depth false --depth-estimation true` |

Setting only `--measured-depth false` restores the default requirement for model depth-estimation declarations. Measured depth and estimation declarations cannot be enabled together.

RGB and depth are rendered together and flipped consistently to a top-left origin. Each observation saves float32 depth in meters with a SHA-256 digest. With measured depth enabled, the model can query 1–64 pixels through `read_depth(observation_id, camera="egoview", pixels_uv=[[u,v], ...])`; `u` is the column and `v` is the row.

Queries return positive optical-axis Z depth and visible-surface coordinates back-projected with calibration from the same observation, not object centers. Historical queries do not advance physics time. Corrupt files, out-of-bounds pixels, or disabled depth cause rejection. This tool is available only in GR1 sessions with measured depth enabled.

## References and evaluation configurations

Reference trajectories use `robocasa-gr1-trajectory-v1`, and video uses egoview. Prepare files in advance; the HDF5 needed to create the environment is not automatically converted to reference video or trajectories. Reference packages do not contain live measured depth. See the [in-context learning guide](../reference-protocol.md#robocasa-gr1) for fields and the [video-to-text guide](../reference-format.md) for text generation.

The [single-task configuration](../../configs/single_task/robocasa_gr1.json) uses `PnPCupToDrawerClose`. The [queue configuration](../../configs/queues/robocasa_gr1.json) contains 24 tasks × 20 seeds, totaling 480 episodes. Seeds follow source-project presets, not an official seed split. The measured-depth setting participates in episode identity. See the [queue guide](../queues.md) for execution and resuming.
