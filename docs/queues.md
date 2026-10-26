# Queues and batch evaluation

**English** | [简体中文](queues.zh-CN.md)

[Documentation](README.md) · Prerequisite: [Single-episode runs](running.md) · Next: [Inspect results](results.md)

A queue defines tasks, seeds, and environment options in JSON and executes them serially in list order. Each episode uses a new simulation process, Codex session, and output directory. Use queues to expand evaluation after a single episode works.

## 1. Start from an existing configuration

Configurations are grouped into `configs/queues/` for reproducing evaluation procedures and comparing conditions, and `configs/single_task/` for individual tasks with exactly one episode per file. Both are loaded by `gpt-gear queue`. See the [configuration guide](../configs/README.md) for the full list and single-task examples.

Copy a suitable configuration and update its environment paths. Repository examples use `/path/to/...` placeholders for environment paths; replace all of them with your installation paths. Adjust relative paths when copying a file to another directory. Available queue configurations are:

| Configuration | Content | Fields to update |
|---|---|---|
| [libero_plus.json](../configs/queues/libero_plus.json) | LIBERO-plus: 50 task variants, one run each | `env_root`, `sim_python` |
| [robocasa_gr1.json](../configs/queues/robocasa_gr1.json) | GR1: 24 tasks × 20 seeds | All four environment paths |
| [univtac.json](../configs/queues/univtac.json) | UniVTAC: 8 tasks × 20 seeds, `force` mode | `env_root`, `sim_python` |
| [robotwin.json](../configs/queues/robotwin.json) | 50 tasks × 2 configurations × 5 seeds: `0–4` for both clean and random, 500 episodes total | `env_root`, `sim_python` |
| [robodojo.json](../configs/queues/robodojo.json) | RoboDojo: 42 tasks, 34 with references | Environment paths and all reference paths |

GR1's four paths are `env_root`, `robosuite_root`, `data_root`, and `sim_python`. Seeds in the GR1 and UniVTAC batch queues come from source-project presets, not official seed splits.

Executing configurations in `single_task/` also calls the model. See [model-free checks](running.md#model-free-interface-checks) for checks without one. Reference data is not included in the repository.

## 2. Inspect the plan, then execute

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run
gpt-gear summarize outputs/robotwin_queue
```

The first command only parses the configuration and prints the plan. It does not create episode directories or start a simulator or model. Plan inspection is not environment preflight; run `doctor` before using an environment for the first time.

## 3. Write your own queue

Configurations use `version: 2`. `environments` defines named environments and paths; `episodes` defines the runs. Save the following as `configs/queues/my_robotwin_queue.json`, replace the paths, and run it:

```json
{
  "version": 2,
  "environments": {
    "twin": {
      "benchmark": "robotwin",
      "env_root": "/path/to/RoboTwin",
      "sim_python": "/path/to/robotwin/bin/python"
    }
  },
  "episodes": [
    {"environment": "twin", "task": "adjust_bottle", "seed": 0, "task_config": "clean"},
    {"environment": "twin", "task": "adjust_bottle", "seed": 1, "task_config": "clean"},
    {"environment": "twin", "task": "adjust_bottle", "seed": 0, "task_config": "random"}
  ]
}
```

```bash
gpt-gear queue configs/queues/my_robotwin_queue.json outputs/my_robotwin_queue
gpt-gear queue configs/queues/my_robotwin_queue.json outputs/my_robotwin_queue --run
```

To create a mixed-environment queue, add named environments and select the appropriate `environment` in each episode.

### Path and parameter rules

| Location or setting | Rule |
|---|---|
| Paths in JSON | Relative to the configuration file's directory; absolute paths are recommended, without shell variables such as `$HOME` |
| Paths on the command line | Relative to the current working directory |
| Seeds, initialization, budgets, modalities | Put them in each episode using underscore field names such as `max_native_steps` |
| Model, GPU, port, cache | Set through shared `queue` command options |
| Context window | Set top-level `codex_context_window` for the whole queue; precedence: explicit `--codex-context-window`, queue value, default 272000. |
| Environment selection | Use `benchmark`; there is no command-line `--backend` alias |

With only one named environment, you can override two paths on the command line:

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_override \
  --env-root /path/to/RoboTwin \
  --sim-python /path/to/robotwin/bin/python --run
```

GR1's `robosuite_root` and `data_root` must still be updated in JSON. Do not pass a single `--benchmark` for a mixed-environment queue.

### Add references to an episode

Prepare the original reference files, then add `reference` to the episode. For example, this entry can be placed in `episodes`:

```json
{
  "environment": "twin",
  "task": "adjust_bottle",
  "seed": 0,
  "task_config": "clean",
  "reference": {
    "video": "/path/to/reference/videos",
    "trajectory": "/path/to/reference/trajectory.json",
    "text": "/path/to/reference/steps.txt",
    "mode": "sequence",
    "fps": 1
  }
}
```

Supply `text`, `video`, and `trajectory` as needed. A trajectory must accompany text or video. Without video, `mode` and `fps` cannot be specified. Point options to the original files, not the cache generated by `reference prepare`. See the [in-context learning guide](reference-protocol.md) for complete rules.

Additional supported `reference` combinations are shown below. Relative paths are resolved against the queue configuration's directory:

```json
{"text": "/path/to/reference/steps.txt"}
```

```json
{"text": "/path/to/reference/steps.txt", "trajectory": "/path/to/reference/trajectory.json"}
```

```json
{"text": "/path/to/reference/steps.txt", "video": "/path/to/reference/videos"}
```

### What counts as the same episode

Queues identify episodes by environment paths, task, seed, and initialization choices. GR1's measured-depth setting, UniVTAC's tactile mode, and RoboTwin's `task_config` also participate in identity.

Duplicate identities are not allowed within a queue. Changing only the budget, model, reference, or depth-estimation declaration setting does not make the same task and initialization a distinct episode. To compare these conditions, run separate queues with different output directories. Put budget, reference, and depth-estimation changes in each run's configuration, and select the model with `--codex-model` on each command.

## 4. Resume and retry

To continue an unfinished queue, run it again with the original configuration and output directory:

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run
```

| Previous state | Resume behavior |
|---|---|
| Not started | Start a new episode |
| `success` | Skip; already completed |
| `task_failure` | Skip; a valid evaluation has completed |
| `invalid` / `runtime_error` | Skip by default; add `--retry-failed` to create a new attempt |

```bash
gpt-gear queue configs/queues/robotwin.json outputs/robotwin_queue --run --retry-failed
```

A retry creates a new `attempt` from the initial state. It does not restore or replay old actions. Use a new output directory after changing queue contents, environment paths, or budgets. The manifest in the original output directory is used to check resume consistency.

Resume validation compares resolved episode configurations and environment paths. It **does not include command-line model, GPU, port, cache, or MCP interpreter settings**. Keep those options consistent when resuming. Use a new output directory when comparing a different model; changing models does not automatically rerun completed episodes.

## 5. Inspect queue artifacts

```text
outputs/robotwin_queue/
├── queue.json
├── status.jsonl
└── <episode_id>/
    ├── attempt-0001/
    ├── attempt-0001.queue.log
    └── attempt-0002/          # If retried
```

`summarize` uses the latest attempt for each episode and groups by benchmark. UniVTAC is additionally grouped by tactile mode, and RoboTwin by Clean/Random. Raw scores are not averaged across environments.

See the [results guide](results.md) for field meanings and troubleshooting.
