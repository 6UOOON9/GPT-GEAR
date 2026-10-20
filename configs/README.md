# Run configurations

**English** | [简体中文](README.zh-CN.md)

[Documentation](../docs/README.md) · [Single-episode runs](../docs/running.md) · [Queue guide](../docs/queues.md)

Configurations are grouped by purpose:

- **`queues/`: queued evaluation.** Fix tasks, seeds, initialization, and input conditions to reproduce evaluation procedures or compare settings.
- **`single_task/`: single-task tests.** Each file contains exactly **one episode** for trying an environment, debugging a task, or evaluating one run.

Both use `version: 2` and are loaded by `gpt-gear queue`; `episodes` in `single_task/` contains only one entry. To specify a task directly on the command line without JSON, use [`gpt-gear run`](../docs/running.md).

## Evaluation queues

| Configuration | Evaluation | Episodes |
|---|---|---:|
| [robodojo.json](queues/robodojo.json) | RoboDojo: 42 tasks, seed 0, layout 9; 34 with reference inputs and 8 without | 42 |
| [libero_plus.json](queues/libero_plus.json) | LIBERO-plus: 5 base tasks × 10 perturbation variants, one run each | 50 |
| [robocasa_gr1.json](queues/robocasa_gr1.json) | RoboCasa GR1: 24 tasks × 20 preset seeds | 480 |
| [univtac.json](queues/univtac.json) | UniVTAC: 8 tasks × 20 preset seeds, `force` mode by default | 160 |
| [robotwin.json](queues/robotwin.json) | RoboTwin: 50 tasks × 2 configurations × 5 seeds (`0–4` for each) | 500 |

GR1 and UniVTAC batch seeds follow presets from the source projects; they are not official seed splits. Prepare reference data separately.

The RoboTwin queue sorts tasks lexicographically. For each task, it runs `clean` with seeds `0–4`, then `random` with seeds `0–4`, for 250 clean and 250 random episodes. The 50 task names were checked against task modules and descriptions in RoboTwin's `envs/` directory and cross-checked with RPent's RoboTwin evaluation task set. Seeds follow this queue's rules.

To select UniVTAC modalities, set `tactile_mode` on each JSON episode to `none`, `image`, `force`, or `image-force`; the default is `force`. With `gpt-gear run`, use `--tactile-mode`.

For complete LIBERO-plus task identifiers and execution order, see `episodes` in the [queue configuration](queues/libero_plus.json). `task` uses `suite/task_id` with a zero-based task ID, not the one-based Classification ID. Each entry retains `seed=0`, `init_state_index=0`, and `max_native_steps=600` from the single-task configuration, with no reference inputs. `initstate_N` in a task name is part of the variant name, not an `init_state_index` value.

## Single-task tests

| Configuration | Task | Initial conditions / mode |
|---|---|---|
| [robodojo.json](single_task/robodojo.json) | RoboDojo `align_blocks` | seed 0, layout 0 |
| [libero_plus.json](single_task/libero_plus.json) | LIBERO-plus `libero_spatial/0` | seed 0, init state 0 |
| [robocasa_gr1.json](single_task/robocasa_gr1.json) | RoboCasa GR1 `PnPCupToDrawerClose` | seed 1365783547 |
| [univtac.json](single_task/univtac.json) | UniVTAC `insert_HDMI` | seed 1468828686, `force` |
| [robotwin.json](single_task/robotwin.json) | RoboTwin `adjust_bottle` | seed 0, `clean` |

Change `task`, `seed`, and supported environment options in the sole episode to select your test. Keeping one entry in `episodes` runs exactly one episode. Single-task configurations also call the model when executed; see the [running guide](../docs/running.md#model-free-interface-checks) for checks without a model.

## Usage

Run from the repository root. Copy a configuration and replace every `/path/to/...` environment-path placeholder with your installation paths first. Relative paths in JSON are resolved against **the directory containing the configuration file**, so adjust them when copying a file elsewhere. Absolute paths are recommended; shell variables such as `$HOME` cannot be used in JSON. GR1 also needs `robosuite_root` and `data_root`.

```bash
# Run one episode: inspect the plan, then execute.
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_one
gpt-gear queue configs/single_task/libero_plus.json outputs/libero_one --run

# Reproduce queued evaluation: inspect the plan, then execute.
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20 --run

gpt-gear summarize outputs/gr1_24x20
```

Without `--run`, the command only parses and prints the plan; it does not validate the simulation installation. Run `doctor` before using an environment for the first time. Reproducing evaluation also requires matching environment versions, assets, reference data, and model settings; see [installation](../docs/installation.md). For resuming, retries, and field rules, see the [queue guide](../docs/queues.md).
