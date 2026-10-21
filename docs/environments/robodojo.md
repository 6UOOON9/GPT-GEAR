# RoboDojo configuration

**English** | [简体中文](robodojo.zh-CN.md)

[Documentation](../README.md) · [Installation](../installation.md) · [Single-episode command](../running.md#robodojo) · [Queues](../queues.md)

RoboDojo provides dual-arm manipulation, three-view RGB, and evaluation scenes selected by seed/layout. This page covers source code, layouts, and evaluation options; see the [running guide](../running.md) for the shared workflow.

## Source code and assets

Use an installed RoboDojo source tree and its simulation Python, with submodules and `Assets` prepared. Point `--env-root` to RoboDojo. Each task needs its corresponding evaluation layout:

```text
Assets/Eval_Layout/RoboDojo/arx_x5/<seed>/<task>_<layout_id>.json
```

`seed` and `layout_id` jointly select the initial scene. Missing layouts cause preflight errors. Keep the simulator's existing interpreter and dependencies; a prepared Python 3.11 environment can be used.

## Task and observation options

| Option or capability | Default and meaning |
|---|---|
| Task | A host task name such as `align_blocks`, with a matching evaluation layout |
| Initialization | `--seed 0 --layout-id 0` |
| Observations | head / left_wrist / right_wrist RGB and dual-arm state |
| Budget and results | Host-native execution budget, scoring, and video |
| Depth | Model depth-estimation declarations enabled by default; disable with `--depth-estimation false`; no measured depth |

RoboDojo does not accept `--init-state-index` or `--max-native-steps`. Run the shared `doctor` preflight first, then validate actual execution with the [single-episode command](../running.md#robodojo). A shared `--smoke` entry point is not currently available.

## References and evaluation configurations

Prepare reference files before evaluation. Trajectories use `robodojo-codex-trajectory-v1` with dual-arm `left_ee` / `right_ee` semantics. See the [in-context learning guide](../reference-protocol.md#robodojo) for trajectory and video formats, and the [video-to-text guide](../reference-format.md) for text generation.

The [single-task configuration](../../configs/single_task/robodojo.json) uses `align_blocks`, seed 0, layout 0. The [queue configuration](../../configs/queues/robodojo.json) contains 42 tasks with seed 0 and layout 9, including 34 with references. Update environment and reference paths before running. See the [queue guide](../queues.md) for execution and resuming.
