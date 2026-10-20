# Project overview

**English** | [简体中文](project-overview.zh-CN.md)

[Documentation](README.md) · [Quick start](../README.md#quick-start) · [Architecture](architecture.md)

GPT-GEAR uses a persistent Codex session to run an observe → act → check-result loop in robot simulation tasks. It provides a shared workflow for execution, reference inputs, and result recording, making it easier to study vision-language model control across environments.

## How an episode runs

1. **Choose the task and initial conditions.** Specify the environment, task, seed, and any required layout or initialization options.
2. **Check and launch the simulator.** The launcher checks source code, resources, and interpreters, then creates a separate process and output directory for the episode.
3. **Let the model observe.** The model receives the task description, current camera RGB images, robot proprioception, calibration, and available tools.
4. **Execute an action.** The model submits bounded pose deltas through MCP; the controller converts them to native environment actions.
5. **Continue using feedback.** Tools return execution feedback and new observations. The model then decides what to do next. When references are enabled, the demonstration is read once before the first action.
6. **Save the official result.** At the end of the episode, the simulator determines task success, and the project saves the result, video, and execution records.

The model session lasts for one episode; the next episode in a queue starts a new session. Reference trajectories help the model understand the procedure and are not automatically replayed as actions.

## Common terms

| Term | Meaning in this project |
|---|---|
| benchmark | A simulation task suite such as RoboDojo or LIBERO-plus, selected with `--benchmark` |
| task | A specific task; LIBERO-plus uses `suite/task_id`, while other environments generally use task names |
| episode | A complete evaluation with a fixed task and initial conditions |
| attempt | One execution attempt for an episode; a queue retry creates a new attempt |
| native step | The execution-budget unit declared by the backend; it is not necessarily one physics tick |
| MCP | The interface through which the model calls structured tools such as `observe` and `act` |
| reference | Text, video, and optional trajectories prepared before evaluation; a trajectory must accompany text or video |
| smoke check | A small set of operations that checks whether the interface works, not whether a task can be completed |

## Responsibilities

| Component | Responsibility |
|---|---|
| Codex session | Plan and select the next tool call using visible inputs |
| MCP and control protocol | Validate requests, deliver images and feedback, and handle duplicate or uncertain requests |
| Controller | Execute bounded actions and track pose targets and budgets |
| Environment adapter | Connect the simulator's observation, action, initialization, and official-result interfaces |
| Simulator | Dynamics, task rules, success determination, and native scoring |
| Launcher and queue | Manage processes, configurations, output directories, resuming, and result aggregation |

Adapters live in this repository and load external environments through the selected simulation Python, without requiring changes to simulator source code. Tool and simulation Python environments are separate; see [installation](installation.md) for dependencies.

## Available model inputs

Every environment provides current RGB images and robot proprioception. Camera calibration helps interpret viewpoints; the adapter provides fixed calibration and wrist extrinsics. Object ground truth and task solvers are not exposed to the model.

| Optional input | Purpose | Availability |
|---|---|---|
| Reference video and trajectory | Show a related procedure; video can be used alone, while trajectories must accompany text or video | All five environments |
| Reference text | Describe steps, alone or combined with video, trajectories, or both | All five environments |
| Depth-estimation declarations | Require the model to record image-based depth estimates without providing measured ground truth | Enabled through run options |
| Measured depth | Query depth and back-projected positions for pixels in saved RGB observations | GR1 |
| Tactile images / resultant forces | Add observations for contact-rich manipulation | UniVTAC |

GR1 enables measured depth by default; other environments require depth-estimation declarations by default. The two modes cannot be enabled together. Prepare reference files in advance; this project only provides the video-to-text generation step. See [reference inputs](reference-protocol.md).

## Interpreting evaluation results

Task success follows the environment's official judgment. Reaching an end-effector target, executing a tool call successfully, or calling `finish` does not by itself establish task success.

Summaries distinguish valid successes, valid task failures, invalid samples, and runtime errors. When reporting results, specify tasks and initial conditions, the model and input settings, and counts of invalid and interrupted episodes. Raw scores are reported separately for each environment. See the [results guide](results.md).

## Further reading

- To run tasks, start with [installation](installation.md) and [single-episode commands](running.md).
- To compare conditions, read about [queues](queues.md) and [reference inputs](reference-protocol.md).
- To change the implementation, read the [architecture](architecture.md) and [contribution guide](../CONTRIBUTING.md).
