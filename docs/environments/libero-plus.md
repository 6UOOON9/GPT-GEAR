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

Reference trajectories use `libero-codex-trajectory-v1`, with `robot0_grip_site` as the control point. See the [in-context learning guide](../reference-protocol.md#libero-plus) for video views and action fields, and the [video-to-text guide](../reference-format.md) for text generation.

The [single-task configuration](../../configs/single_task/libero_plus.json) uses `libero_spatial/0`. The [queue configuration](../../configs/queues/libero_plus.json) contains 50 variants of 5 base tasks, each with seed 0, init state 0, 600 native steps, and video, text, and trajectory references matched by base task (`sequence`, 1 fps). Replace `/path/to/reference_demo` with your local demonstration root before running. See its `episodes` for complete task IDs and execution order. For execution and resuming, see the [queue guide](../queues.md).

The reference collection includes 40 LIBERO-Plus base-task demonstrations. Download them using the [demonstration download guide](../reference-protocol.md#download-reference-demo). The directory ranges under `/path/to/reference_demo/LIBERO-Plus/` are:

| Demonstration directory | Suite | Count |
|---|---|---:|
| `base_00`–`base_09` | `libero_spatial` | 10 |
| `base_10`–`base_19` | `libero_object` | 10 |
| `base_20`–`base_29` | `libero_goal` | 10 |
| `base_30`–`base_39` | `libero_10` | 10 |

Match a variant to its base task before selecting a demonstration. `base_XX` identifies a demonstration, not `suite/task_id`. For example, `libero_goal/0` is a variant of `open_the_middle_drawer_of_the_cabinet` and uses `base_20`. All variants of that base task share the same reference:

```json
"reference": {
  "video": "/path/to/reference_demo/LIBERO-Plus/base_20/videos",
  "trajectory": "/path/to/reference_demo/LIBERO-Plus/base_20/trajectory.json",
  "text": "/path/to/reference_demo/LIBERO-Plus/base_20/steps.txt",
  "mode": "sequence",
  "fps": 1
}
```

Each demonstration includes external (`agentview`) and wrist (`robot0_eye_in_hand`) video, textual steps, and an action trajectory. Keep the complete directory, including `trajectory.jsonl` and `videos/videos.json`.

To run the bundled queue, replace `env_root`, `sim_python`, and every `/path/to/reference_demo` prefix in its JSON with local absolute paths. The `--env-root` option only overrides the simulator path; it does not rewrite reference paths. Then inspect the plan and run:

```bash
gpt-gear queue configs/queues/libero_plus.json outputs/libero_plus_reference
gpt-gear queue configs/queues/libero_plus.json outputs/libero_plus_reference --run
```

The first command only prints the plan. If you previously ran this queue without references, use a new output directory for the configuration with references. Each queue JSON is self-contained; recipients can run their own file with `gpt-gear queue <config.json> <output-directory> --run` after updating its paths.
