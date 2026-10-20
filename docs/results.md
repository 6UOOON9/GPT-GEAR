# Results and troubleshooting

**English** | [简体中文](results.zh-CN.md)

[Documentation](README.md) · [Single-episode runs](running.md) · [Queues](queues.md)

After an episode, start with the summary, then inspect official results, videos, and logs as needed. A final model message saying “done,” or a call to `finish`, does not replace the simulator's success judgment.

## View a summary

Single episodes and queues use the same command:

```bash
gpt-gear summarize outputs/libero_one
gpt-gear summarize outputs/robotwin_queue
```

The command prints JSON containing status counts, valid episode counts, success rates, environment statistics, and per-episode records. Queues count only the latest attempt for each entry.

| Status | Meaning | Included in the success-rate denominator |
|---|---|---|
| `success` | Complete run, valid sample, official success | Yes |
| `task_failure` | Complete run, valid sample, official failure | Yes |
| `invalid` | Run ended but did not meet valid-evaluation conditions | No |
| `runtime_error` | Incomplete execution or result recording, or an invalid result format | No |
| `pending` | Queue episode not yet attempted | No |

Success rate is `success / (success + task_failure)`, or `null` when no valid episodes exist. When comparing evaluations, also report counts of invalid episodes, runtime errors, and unexecuted episodes.

Raw scores from different environments are not directly averaged. UniVTAC provides additional grouping by tactile mode, and RoboTwin by Clean/Random.

## Where to find artifacts

| File or directory | Contents |
|---|---|
| `result.json` | `sim-result-v1` result: task identity, validity, official success, and termination reason |
| `launcher.json` | Launcher state and process exit information |
| `official_result.json` | Detailed official judgment for backends that provide this file |
| `observations/` | Saved RGB, state, and other enabled observations |
| `history.jsonl` | Control-session history |
| `episode.mp4` / `video.json` | Shared video recording and camera order, frame counts, and encoding result |
| `host.json` | Actual source versions and loaded module paths; shared simulator entry points also record interpreter and dependency versions |
| `codex_run.json` / `codex_events.jsonl` | Model launch information and session events |
| `action_metrics.json` | Per-action timing and usage where records can be associated |
| `server.log` / `codex_stderr.log` | Simulator-side and model-side diagnostic logs |
| `session.json` | Local connection information containing a token; do not publish it |

RoboDojo uses native scoring and videos in `eval_result/` under the simulator directory; see result files for exact paths. LIBERO-plus recordings show two cameras side by side; RoboTwin shows three and uses `video_timeline.jsonl` to map video frames to physics time and native calls.

RoboTwin samples at 25 fps using actual physics time, including initial and final states but excluding model inference waiting time. If encoding fails, `episode.mp4` is not published; existing partial files are retained, and the episode is summarized as `runtime_error`, outside the success rate. Its result also records that expert filtering was not performed.

Queue artifacts are stored in `<queue_directory>/<episode_id>/attempt-0001/`. `attempt-0001.queue.log` sits alongside that directory and can help diagnose failures before an episode output directory is created.

Per-action token usage remains `null` when it cannot be reliably associated; this does not mean zero usage. `host.json` and model launch records help reproduction, but local outputs, assets, and authentication are not included in the repository.

## Common problems

### `gpt-gear` is not found

Activate `.venvs/codex-mcp` from the repository root, or call `.venvs/codex-mcp/bin/gpt-gear` directly. See [installation](installation.md).

### `doctor` passes, but the model fails to start

`doctor` does not check model authentication. Inspect `codex_stderr.log` and verify the current system user's authentication, network, and model access. The local model configuration is used by default; override it with `--codex-model`.

### A layout, task, or HDF5 file is missing

RoboDojo layouts depend on task, seed, and layout together. LIBERO-plus tasks use `suite/task_id`. UniVTAC task names are case-sensitive. GR1 requires environment configuration from `<task_name>.hdf5` even without references. Check options against the [running guide](running.md).

### The output directory already exists

Use a fresh path for a single episode; do not run `mkdir` beforehand. To resume a queue, use the original configuration and queue output directory. Do not remove session guard files to continue old actions.

### The queue plan prints, but execution fails

Planning only parses configuration. Check that JSON paths resolve relative to the configuration file, run `doctor` for the environment, then inspect the `.queue.log` beside the episode directory.

### A queue cannot resume after configuration changes

Resuming requires the saved queue manifest to match the currently resolved configuration. Use a new output directory after changing tasks, paths, budgets, references, or similar settings. `--retry-failed` does not rerun valid task failures; it handles only invalid or interrupted episodes.

### Simulator readiness times out

First inspect `server.log` for asset, rendering, GPU, or dependency errors. If the output directory has not been created, check the adjacent `<output_path>.server.log` and `<output_path>.launcher.json`. Increase `--codex-startup-timeout` only after confirming that loading is simply slow.

### Reference validation fails

Check existing files separately with `reference prepare`. Common causes include missing video mappings, format mismatches, digest mismatches, paths escaping allowed boundaries, or supplying a trajectory without text or video. Text-only references are supported; without video, `mode` and `fps` cannot be specified. Correct the original files and use a new output directory. See [reference inputs](reference-protocol.md).

### An action result is uncertain, or tool image delivery fails

The current session stops further actions. Inspect `status` and logs; do not replay requests or remove guard files to resume motion. A queue can use `--retry-failed` to create a fresh attempt from the beginning.

## Sharing reproductions or reporting issues

Provide the benchmark, task, seed, initialization options, source versions, command, summary, and relevant error logs. Exclude `session.json`, credentials, and unrelated personal paths; large videos can be shared separately. See [contributing](../CONTRIBUTING.md) for the information an issue report should include.
