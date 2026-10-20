# Architecture and developer guide

**English** | [简体中文](architecture.zh-CN.md)

[Documentation](README.md) · [Project overview](project-overview.md) · [Contributing](../CONTRIBUTING.md)

This guide is for developers who want to understand the control flow, change tools, or add environments. Start with processes and module responsibilities, then consult control, observations, and reference delivery as needed. For commands, see the [single-episode guide](running.md).

## How processes cooperate

The shared entry point is `gpt-gear`, implemented in `execution.cli`, with functional packages directly under `src/`. Commands use `--benchmark robodojo|libero-plus|robocasa-gr1|univtac|robotwin`. A benchmark selects a simulation task system; LIBERO's suite is part of the task identifier `suite/task_id`.

```text
gpt-gear run / queue
  → benchmark registry: preflight → resolve_task → launch_spec
  → selected simulation Python
      → native official environment
      → common Session + DeltaController
      → owner-thread native execute / observe / official result
  → Codex → persistent STDIO MCP → localhost HTTP → Session
```

## Where to start reading code

| Module | Main entry points | Responsibility |
|---|---|---|
| Execution | [launcher.py](../src/execution/launcher.py), [batch.py](../src/execution/batch.py) | Process orchestration and queues |
| Session | [session.py](../src/execution/session.py) | Request scheduling, observation storage, and episode state |
| Control | [controller.py](../src/control/controller.py), [profiles.py](../src/control/profiles.py) | Bounded servo control and environment control capabilities |
| Protocol | [mcp_server.py](../src/protocol/mcp_server.py), [contracts.py](../src/protocol/contracts.py) | Tool serving, capability handshake, and delivery |
| Perception | [perception/](../src/perception/) | Calibration, depth, and observation modalities |
| Environments | [backends.py](../src/environments/backends.py) | Load adapters by environment |
| References | [demonstrations/](../src/demonstrations/) | Video, trajectories, caching, and text generation |

Package initialization does not preload these implementations. Command dispatch imports them as needed, keeping simulation and MCP dependencies separate.

`execution/config.py` parses run arguments. Single episodes and queues share validation for seeds, mutually exclusive depth modes, and reference inputs. Simulator entry points read configuration directly without depending on the launcher. `execution/artifacts.py` provides atomic JSON writes using only the standard library; the simulation side explicitly supplies a NumPy serializer. Protocol guards use `write_guard`, syncing content before replacement and the parent directory afterward. Write failures propagate to the caller.

## Model tools and result delivery

| Tool | Purpose | Availability |
|---|---|---|
| `observe` | Read saved current or historical observations without advancing simulation | Always |
| `act` | Execute a bounded action from the latest observation and return feedback plus a new observation | Always |
| `status` | Query session state or final results | Always |
| `finish` | End control; the environment still determines success | Always |
| `read_reference` | Deliver reference images, text, and complete trajectories once | When references are configured |
| `read_depth` | Query measured depth from saved observations | GR1 with measured depth enabled |

`protocol/tools/` organizes MCP definitions and synchronous call adapters by tool name. `observe`, `act`, `status`, and `finish` are always enabled; `read_reference` and `read_depth` follow session capabilities. `rendering.py` shares feedback trimming, observation identity, and image validation. Reference assembly lives in `read_reference.py`. Only the MCP process loads these modules; the simulation side continues to schedule the controller and perception modules through `Session`.

`protocol/mcp_server.py` serializes tool calls and handles cancellation, auditing, and delivery acknowledgment. Tools make requests through a shared `ControlClient`. Actions and finish operations defer acknowledgment until the worker completes, cancellation checks pass, and the audit is written; the service then releases persisted protection. The first-observation prerequisite and one-time reference-delivery state are also acknowledged at this shared boundary.

## Environment adapters and process lifecycle

Each environment directory contains `backend.py`, `simulator.py`, `native.py`, `reference.py`, and environment-specific prompts. Preflight and launch configuration use the standard library; simulation dependencies load only in the selected simulation interpreter.

`environments/backends.py` lazily loads `environments/<environment>/backend.py` by benchmark. Each backend uses only the standard library and handles resource location, task identity, and subprocess commands/environment variables. `environments/common.py` shares launch arguments and reference caching. The common CLI and queues pass source and data paths.

LIBERO-plus, GR1, UniVTAC, and RoboTwin share the process lifecycle in `environments/simulator.py`. The shared entry point manages preflight, environment configuration, reference caches, Session, error results, and resource cleanup. Backends declare module origins and dependency lists; environment entry points provide callbacks for native-environment construction, prelaunch configuration, and application initialization. SIGINT/SIGTERM interrupt startup or set cancellation state in an active Session. Resources close in Session → native → application order; cleanup continues if a stage fails, and original signal handlers are restored. Startup failures record the original error using already-resolved identity instead of resolving the task again.

`Session` does not read host-specific environment fields. It relies on the native adapter's `benchmark`, `identity`, `control_profile`, `control_metadata()`, `observe()`, `execute()`, `status()`, `ended()`, `finalize()`, and `result()`. Each adapter implements host calls and result conversion; see [environment-specific differences](#environment-specific-adapter-differences).

Adapters that count model actions can implement `after_policy_action()`. Session calls it once after a controller call returns and before saving the new observation; it returns a stop reason or `None`. Rejected or deduplicated requests do not trigger it. UniVTAC uses this callback for its model-action budget; Session does not access internal counters, termination fields, or launch arguments. Tactile observations are selected through the observation profile rather than environment-name checks in the storage layer.

## Control contract and budgets

The control protocol is `sim-codex-v1`, capability version is `sim-control-v2`, and feedback format is `compact-arms-v1`. The handshake binds the benchmark, control profile, observation profile, measured depth, and reference digest. Version mismatches are rejected immediately; old active sessions are incompatible. Actions have shape `action.arms[arm_id]`, and every configured arm must appear explicitly. Single-arm robot0 and dual-arm left/right share bounded closed-loop servo control. Displacements are in meters in the environment frame declared by the capability profile; delta quaternions use wxyz and left multiplication. Each arm can finish or reach its budget independently and hold, while native execution remains a single synchronized step.

Depending on capabilities, grippers use a continuous ratio, open/close, metric finger position, or six-dimensional hand targets. Backends declare budget units and initialization accounting rules.

Metric gripper ranges are declared per arm in the control profile's `gripper_position_limits_m`. The shared controller and MCP parameter schema read the same configuration. Completion uses the profile's `gripper_tolerance_m`; the controller does not import environment-specific gripper modules. Range fields participate in the full capability handshake, and missing or modified configurations are rejected.

## Observations and calibration

Camera RGB and robot proprioception are delivered through an allowlist. Fixed calibration is read once; moving-camera extrinsics combine current measured body poses with fixed mounts. Object ground truth is not exposed. Session delivers modalities selected by the observation profile, and MCP validates the image set, specifications, units, and frames. Historical observations follow the same contract. Ordinary cameras and tactile images have separate calibration. Visual perturbations from official wrappers are preserved, not bypassed through another render.

## Reference inputs and caching

See the [reference-input guide](reference-protocol.md) for usage and formats.

Reference caches use `sim-reference-v1` and explicitly bind the benchmark. The five benchmarks have separate trajectory validators but share video processing, digests, path-boundary checks, and the delivery state machine. Successful observe delivery must precede one-time read_reference delivery before act is allowed. Complete original trajectory numbers are not rewritten.

`demonstrations/reference.py` handles only the CLI. `media.py` handles view discovery, sampling, decoding, and image validation. `trajectory.py` dispatches environment validators and packages trajectories losslessly. `cache.py` assembles and reads caches and sets output budgets. Environment validators reuse checks for frame indices, counts, finite vectors, and unit quaternions from `common.py`. Each environment still defines action semantics, unknown gripper values, dual-arm structure, and sampling-gap rules.

Users prepare references for every environment before evaluation, including RoboDojo. Video export and trajectory generation happen outside this project; this project only provides optional text generation from existing videos. `run` / `queue --run` validate existing files, sample video frames, assemble caches, and deliver them. They do not call the text generator. `reference prepare` is an offline preflight entry point for that cache workflow, not a generator of demonstrations from raw data.

All five environments share `video_to_steps.py` and `prepare_reference_text.py` for text generation. Each environment's `reference.py` declares required cameras and an optional image limit, while `prompts/reference_text.md` defines visual annotation rules, including for RoboDojo. The generator loads the environment-specific prompt without falling back to a shared annotation prompt. The shared layer handles independent video sampling, read-only model calls, numbering validation, atomic publication, and auditing. RoboTwin retains three cameras and a total limit of 42 images. `--reference-fps` selects the sampling rate, defaulting to 1 FPS; the actual rate is written to the prompt, audit, and any existing provenance.

## Failure handling and run isolation

Only the simulator's main thread accesses the environment. Request deduplication, latest-observation validation, persisted pending/uncertain/delivery guards, timeout cancellation, and fail-closed behavior are preserved. Old active sessions are not resumed; queue retries use a new process and attempt. Output directories are exclusive, and runtime errors are counted separately from official task failures.

Action metrics associate events and MCP timing through parameter fingerprints. Old logs without fingerprints are no longer matched by call order; records that cannot be associated remain missing or unmatched. The CLI parser rejects old reference options as unknown arguments.

Simulation Python and MCP Python are separate. Core simulation modules support Python 3.10, while the MCP SDK requires Python 3.11+. LIBERO_CONFIG_PATH, PYTHONPATH, and cache settings apply only to subprocesses, without changing global configuration or editable installations.

## Environment-specific adapter differences

The following sections describe host interfaces, action conversion, and observation differences. Shared launch, control-contract, and delivery behavior is covered above.

### RoboDojo

RoboDojo uses the original factory and `run_eval`. Temporary reference replacements are restored after environment creation, and control methods are bound only to the current instance without changing host source. Actions execute through native IK and `take_action`; `result(eval_result)` wraps native scoring. See [RoboDojo configuration](environments/robodojo.md) for layouts and run options.

### LIBERO-plus

LIBERO-plus calls the original `OffScreenRenderEnv`, `set_init_state`, `step`, and `check_success`, without changing host source. Before host modules are imported, `prepare_environment` generates episode-specific `libero_config/config.yaml` and obtains suite/task_id from the preflight identity.

Actions invert scaling using `OSC_POSE`'s actual input/output ranges, with the real grip site as control point. Initialization steps count toward the native-step budget. `result()` wraps `check_success` and video recording. See [LIBERO-plus configuration](environments/libero-plus.md) for tasks and initialization options.

### RoboCasa GR1

The entry point is `environments.robocasa_gr1.simulator`, which reads environment configuration from HDF5 `env_args`. In the shared servo, GR1 selects `reference_trajectory` by capability and advances reference targets independently of measurement lag. The native adapter converts synchronized dual-arm world-frame targets into native absolute/base IK actions. Each arm's optional `hand` contains six raw radian targets; stopped arms retain their latest targets.

GR1 saves RGB-aligned measured depth by default. Enabling measured depth disables model depth-estimation declarations; the two are mutually exclusive. `read_depth` reads only saved frames with digests and back-projects using intrinsics/extrinsics from the same observation, without refreshing cameras or physics time. Other environments do not provide measured depth. Head-camera extrinsics are composed from current body poses. See [GR1 configuration](environments/robocasa-gr1.md) for run and depth options.

### UniVTAC

The entry point is `environments.univtac.simulator`, which starts Isaac Lab before importing tasks. Actions use the robot_base frame, required `robot0.gripper_position_m`, and gripper-center DLS. Finger targets are rate-limited to 0.0005 m per physics step, using `gripper_position_limits_m` from the control profile. Completion checks both pose and measured gripper error. Control iterations, physics ticks, and model actions are counted separately.

The four tactile modes change only exposed inputs; internal tactile updates remain active. Images and resultant forces are independently selectable. Modes without resultant forces do not require the UIPC `contact_gradient` interface. Wrist-camera extrinsics are composed from current body poses. See [UniVTAC configuration](environments/univtac.md) for run and tactile options.

### RoboTwin

The RoboTwin backend uses the selected simulation Python to check YAML, base dependencies, and video encoders. Tasks are resolved by host name. clean/random map to native configurations and participate in episode identity. The adapter does not use the source package's sorted task IDs, expert filtering, or valid-sample quota scheduling.

The native adapter converts each active arm's delta into an absolute EE pose, retaining inactive arms' measured poses and latest gripper targets. It calls take_action(ee) with a 16-dimensional dual-arm vector. Native calls and physics steps are counted separately; counting anomalies or interrupted execution mark the episode uncertain and stop it. Planning failures are retained as feedback from executed calls. Success is determined by eval_success or check_success; finish does not overwrite it.

Observations contain head_camera / left_camera / right_camera and proprioception, using shared fixed calibration and composed wrist extrinsics. Video samples RGB by physics time after the instance's scene.step; encoding and artifact finalization reuse EpisodeVideo. Instance hooks are restored on exit. References use a dedicated RoboTwin trajectory validator that preserves complete source numbers and unknown gripper commands; caching and one-time delivery remain shared. See [RoboTwin configuration](environments/robotwin.md) for options and the [running guide](running.md#model-free-interface-checks) for interface checks.

## Prompt assembly

`prompts.evaluation_prompt` reads shared rules and environment-specific rules under `environments/<environment>/prompts/` through package resources. Every environment has its own `control.md`; GR1 also has `measured_depth.md`. Shared prompts do not enumerate other environments' gripper semantics. Depth-estimation declarations are constrained to the arms actually configured. Capability JSON and reference/depth switches are generated from episode configuration; the launcher saves the final text and computes its digest. Wheels include both shared and environment-specific prompts, so loading does not depend on the working directory.

## Suggested order for adding an environment

Define task identity and control/observation capabilities first, then implement the native adapter and connect the shared lifecycle. After offline contract tests pass, check observations, hold actions, and resource cleanup in a real simulator. Finally, run a model episode with fixed initial conditions. See [contributing](../CONTRIBUTING.md) for required test and reproduction information.
