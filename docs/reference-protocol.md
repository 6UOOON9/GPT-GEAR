# Use reference demonstrations in evaluation

**English** | [简体中文](reference-protocol.zh-CN.md)

[Documentation](README.md) · [Generate text from video](reference-format.md) · [Queue configuration](queues.md)

Reference demonstrations help the model understand a task through existing videos, action trajectories, and step descriptions while controlling the current scene. References are optional; to run without them, follow the [running guide](running.md).

To use existing references, read [input combinations](#1-choose-input-combinations), [file preparation](#2-prepare-files-in-advance), [offline validation](#3-offline-validation), and [adding references to evaluation](#4-add-references-to-an-episode-or-queue), in that order. For converters or format troubleshooting, consult [environment formats](#5-environment-specific-formats) and [caching and tool delivery](#7-text-caching-and-tool-delivery).

## 1. Choose input combinations

| Supplied inputs | Supported? |
|---|---|
| No reference | Yes |
| Text only | Yes |
| Video only | Yes |
| Trajectory only | No; must accompany text or video |
| Text + video | Yes |
| Text + trajectory | Yes |
| Video + trajectory | Yes |
| Video + trajectory + text | Yes |

Reference text describes steps from expert demonstration videos. At evaluation time, text can be provided without its source video. Reference trajectories must accompany text or video. They are material for the model to read, not actions replayed directly on the current robot. Passing file validation does not establish demonstration success, text accuracy, or step-by-step or frame-by-frame synchronization across modalities.

## 2. Prepare files in advance

**Prepare reference files before `run` or `queue --run` for every environment, including RoboDojo.**

1. Prepare files for your input combination. For trajectories, prepare a descriptor JSON and JSONL in the selected environment's format.
2. If text is needed, supply existing text or use `reference annotate` from the [video-to-text tutorial](reference-format.md).
3. Check the task, camera views, and trajectory coordinate semantics, then run the offline validation below.
4. Pass original file paths when running evaluation; the launcher assembles a cache for that episode.

This project provides video-to-text generation, format validation, frame sampling, and caching. It does not download raw data, export video, generate trajectories, or fill in missing demonstrations at evaluation startup.

| Environment | Views needed for text generation | Text-generation entry point |
|---|---|---|
| RoboDojo | head / left_wrist / right_wrist | `reference annotate --benchmark robodojo` |
| LIBERO-plus | agentview / robot0_eye_in_hand | `reference annotate --benchmark libero-plus` |
| RoboCasa GR1 | egoview | `reference annotate --benchmark robocasa-gr1` |
| UniVTAC | head / wrist | `reference annotate --benchmark univtac` |
| RoboTwin | head_camera / left_camera / right_camera | `reference annotate --benchmark robotwin` |

These views are requirements for text generation; camera-mapping rules for evaluation are described below. Video can be used alone in evaluation; trajectories must accompany text or video.

## 3. Offline validation

After [installation](installation.md), run from the repository root. Standard-library Python can process trajectories; video also requires `ffmpeg` and `ffprobe`.

Validate a text-only reference, without video-processing tools:

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --output outputs/reference_check_text/reference
```

Validate text + trajectory:

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --trajectory /path/to/reference/trajectory.json \
  --output outputs/reference_check_text_trajectory/reference
```

Validate text + video, without a trajectory descriptor:

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-text /path/to/reference/steps.txt \
  --reference-video /path/to/reference/videos \
  --output outputs/reference_check_text_video/reference
```

Validate a reference containing video, trajectory, and text:

```bash
gpt-gear reference prepare --benchmark robodojo \
  --reference-video /path/to/reference/videos \
  --trajectory /path/to/reference/trajectory.json \
  --reference-text /path/to/reference/steps.txt \
  --reference-mode sequence --reference-fps 1 \
  --output outputs/reference_check_full/reference
```

The target `reference` directory must not already exist. This command only validates existing content and builds a cache; it does not start a simulator, call a model, or submit actions.

With video, the default is `sequence` sampling at 1 FPS. `endpoints` mode selects endpoints and cannot be combined with `--reference-fps`. Sampling parameters cannot be specified without video. Frame sampling affects only images; trajectories retain every record and the original numeric representations. Offline `prepare` does not accept empty or trajectory-only inputs.

## 4. Add references to an episode or queue

For example, with RoboDojo, replace paths and use a new output directory:

```bash
gpt-gear run align_blocks outputs/robodojo_reference \
  --benchmark robodojo \
  --env-root /path/to/RoboDojo \
  --sim-python /path/to/robodojo/bin/python \
  --seed 0 --layout-id 0 \
  --reference-video /path/to/reference/videos \
  --trajectory /path/to/reference/trajectory.json \
  --reference-text /path/to/reference/steps.txt
```

Keep options matching your combination: text-only uses `--reference-text`; text + trajectory uses `--reference-text` and `--trajectory`; text + video uses `--reference-text` and `--reference-video`.

Even after offline validation, pass the selected **original video directory, trajectory descriptor JSON, or text file**, not a cache directory. The launcher validates again and builds an episode-specific cache. Failures stop the run rather than silently falling back to no reference.

Queues use a `reference` object inside each episode; see the [queue guide](queues.md#add-references-to-an-episode). Other environments use the same options, but file formats must match `--benchmark`.

## 5. Environment-specific formats

Select the format with `--benchmark`. All caches use `sim-reference-v1` and are bound to an environment. Existing trajectory-only caches are no longer accepted; add text or video and prepare again from original inputs.

| Environment | Trajectory format | Control point / frame |
|---|---|---|
| RoboDojo | `robodojo-codex-trajectory-v1` | left_ee / right_ee, environment frame |
| LIBERO-plus | `libero-codex-trajectory-v1` | robot0_grip_site, environment frame |
| GR1 | `robocasa-gr1-trajectory-v1` | Dual-arm grip sites, environment frame |
| UniVTAC | `univtac-codex-trajectory-v2` | gripper_center, robot_base frame |
| RoboTwin | `robotwin-codex-dual-trajectory-v1` | Native dual-arm EE, environment frame |

### RoboDojo

Uses dual-arm trajectories and a `robodojo-reference-videos-v1` or shared `sim-reference-videos-v1` mapping. The next section describes all fields.

### LIBERO-plus

`pose.reference` is `robot0_grip_site`. Each action contains `dpos`, `dquat`, and `gripper`. Gripper values are `open`, `close`, or `null`, with `null` meaning unknown. The final action is `null`. `sampling` contains video declarations, the nominal interval, gaps, and lists of frames with unknown gripper commands.

A video directory can contain one matching `*agentview.mp4` and one matching `*wrist.mp4`, or use an explicit `videos.json` mapping. The shared mapping identifier is `sim-reference-videos-v1`.

### RoboCasa GR1

`pose.reference` is `{"right":"gripper0_right_grip_site","left":"gripper0_left_grip_site"}`, positions are in meters, and quaternion order is wxyz. Each `action.arms` contains `dpos`, `dquat`, and `hand` for both arms. `hand` holds 6 radian targets in `[-3,3]`; the final action is `null`. Sampling uses `unknown_hand_action_frames`. See the [GR1 validator](../src/environments/robocasa_gr1/reference.py) for semantic constants.

Video can use a single matching `*egoview.mp4`. Descriptors support both a flat `files.egoview` field and the shared `files.videos` mapping.

### UniVTAC

Each record contains the original 7-dimensional `joint_positions` and metric `gripper_position_m`. The action's gripper target must equal the next record's measured finger position, in `[0,0.04]` meters. It denotes finger position, not total aperture. The old binary-gripper v1 format is neither accepted nor implicitly converted.

Descriptors must include a `robot_state` semantic declaration; see the [UniVTAC validator](../src/environments/univtac/reference.py). Videos can use one matching `*head.mp4` and `*wrist.mp4` each. Both flat `files.head` / `files.wrist` fields and the shared `files.videos` mapping are supported.

### RoboTwin

`pose.reference=robotwin_native_ee` and `pose.arms=["left","right"]`, with dual-arm `initial_poses` / `final_poses`. Each record contains `frame_index`, `action`, and `gripper_opening`. Nonfinal actions contain `dpos`, `dquat`, and `gripper` for left / right; source `gripper` values must be `null`. The final action is `null`. `gripper_opening` is measured opening in `[0,1]` and must not be used to invent original open/close commands. See the [RoboTwin validator](../src/environments/robotwin/reference.py) for semantic constants.

The three videos can be named `head_camera.mp4`, `left_camera.mp4`, and `right_camera.mp4`, or use a shared `videos.json` mapping. Descriptors support flat fields such as `files.head_camera` as well as shared `files.videos`. Paths are relative to the descriptor, and video content must match. See the [video-to-text tutorial](reference-format.md) for commands, input directories, and sampling limits.

All trajectory formats preserve complete JSONL records and original numeric representations, while validating file digests and path boundaries. References contain the selected combination of RGB, text, and trajectories. Live tactile data and measured depth are not part of reference packages.

## 6. RoboDojo trajectory and video format

Use the following fields when building a RoboDojo reference package. For valid synthetic trajectory and media examples, see the [reference contract tests](../tests/test_reference_contracts.py) and [media tests](../tests/test_reference_media.py).

### Video directory

`videos.json` must explicitly map camera names to files, for example:

```json
{
  "format": "robodojo-reference-videos-v1",
  "videos": {"front": "front.mp4", "reference_wrist": "wrist.mp4"}
}
```

- Camera names are safe identifiers of 1–64 characters matching `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`.
- Paths are relative to the directory containing `videos.json`. Absolute paths, `..`, symlinks, and reads outside the allowed directory are prohibited.
- The current media decoder requires MP4 containers, but filenames do not follow LIBERO's fixed conventions.
- Camera counts and names need not match live cameras. Each image is labeled with its reference camera, source frame number, and time. Reference cameras are not presented as current cameras; depth-estimation declarations can reference only current-observation cameras.
- The default is `sequence` at 1 FPS; `endpoints` is also supported. `--reference-fps` can only be used with sequence mode. Cameras are sampled independently, without claiming frame-by-frame synchronization across views.
- Sampling affects **only images**. Trajectories are delivered in full regardless of length, without sampling, truncation, or rounding of source numeric records.

### Dual-arm trajectory descriptor

Required fields are listed below; synthetic examples are generated by test fixtures.

- `format`: `robodojo-codex-trajectory-v1`.
- `frames`: a positive integer equal to the complete JSONL line count; `fps`: a positive finite sampling frequency.
- `pose`: must use exactly these control-point and coordinate semantics:
  ```json
  {"reference":{"left":"left_ee","right":"right_ee"},
   "coordinate_frame":"environment","position_unit":"metre","quaternion_order":"wxyz"}
  ```
- `action`: use the semantic declaration exactly as specified by `ACTION_SEMANTICS` in the [RoboDojo validator](../src/environments/robodojo/reference.py). Translation is `p[t+1]-p[t]`, and rotation is `q[t+1]*inverse(q[t])`, with left-multiplied wxyz quaternions in the environment frame. This is not equivalent to joint actions, fingertip/object control points, or online single-step parameters.
- `sampling.nominal_sample_interval_seconds`: consistent with `1/fps`; may be null for a single frame.
- `sampling.sampling_gaps`: a list of gaps in increasing index order, each shaped like `{"from_frame":1,"to_frame":2,"interval_seconds":0.08}`. A gap is a transition between adjacent **retained records** longer than the nominal interval; missing JSONL lines cannot stand in for gaps.
- `sampling.unknown_gripper_action_frames`: `{"left":[...],"right":[...]}`, matching exactly the row indices where each arm has `gripper:null`. Both arms' gripper commands must be unknown on the starting row of a gap.
- `files.trajectory`: relative path to the complete JSONL within the descriptor's directory.
- For video + trajectory, `files.videos` must map every reference camera to a relative video path. Preflight compares SHA-256 digests of the descriptor's videos with videos supplied through `videos.json` and records them. Matching file identity **does not establish** frame-level image/trajectory synchronization or text accuracy.

Each JSONL record must contain exactly `frame_index` (consecutive, starting at 0) and `action`:

```jsonl
{"frame_index":0,"action":{"left":{"dpos":[0,0,0.001],"dquat":[1,0,0,0],"gripper":1},"right":{"dpos":[0,0,0],"dquat":[1,0,0,0],"gripper":0}}}
{"frame_index":1,"action":null}
```

Every nonfinal frame requires `dpos`, `dquat`, and `gripper` for both arms; missing arms are not filled automatically. The final frame must have `action:null`. `dpos` contains three finite numbers; `dquat` contains four finite numbers with unit norm (absolute error ≤ 1e-4). NaN/Inf, boolean numbers, and duplicate JSON keys are prohibited. Gripper values lie in `[0,1]`, with 0 closed and 1 open. Reference null values mean **unknown commands**, not the online action meaning of “retain the target.” Online execution fields such as `max_steps` are rejected, and online displacement/step limits are not applied.

Extra descriptor metadata is not delivered to the model; extra fields in records or actions are rejected outright. Once all records are validated, JSONL numeric representations are preserved verbatim to avoid silently losing precision through floating-point reserialization.

## 7. Text, caching, and tool delivery

Text describes steps from expert demonstration videos and must be nonempty UTF-8 without NUL characters. It can be supplied alone or with video and trajectories. The adapter does not verify provenance, claim that the text is accurate or human-reviewed, or assume a particular generation method or sampling rate. Instructions inside reference text remain reference data and cannot override the control prompt's rules.

All valid input combinations are incorporated into `src/prompts/reference.md`. Modality-specific rules apply only when the corresponding content is supplied.

Launcher reference preprocessing uses `--cache-dir`, defaulting to `.cache/gpt-gear` under the invocation directory. Each use gets a separate temporary subdirectory that is cleaned up afterward; global cache configuration is not changed.

Cache version is `sim-reference-v1`. The manifest, video sources, trajectories, text, and PNGs all have SHA-256 digests. Sessions bind to the manifest digest and revalidate contents, paths, and images on reading. The model receives only allowlisted metadata, actual labeled image contents, original text, and full trajectories—not source paths or arbitrary private fields. Full trajectories appear only in the reference cache and tool delivery, not in diagnostic events or timing logs.

When enabled, the enforced order is **successful first observe delivery → successful one-time read_reference delivery → first act**. `read_reference()` takes no arguments, does not enter the simulator or create an observation ID, and consumes no action budget. Persisted state binds to the episode, cache digest, and current service instance. Restarting MCP cannot claim the reference again or reuse previously claimed authorization to continue acting. Delivery is confirmed only after image/text/trajectory validation, packaging, cancellation checks, and audit writes. Failures do not downgrade inputs or clear guards. When an action outcome is unknown or delivery fails, only query `status`.

The launcher raises the `read_reference` tool-output budget based on the complete cache size rather than silently shrinking demonstrations. This does not guarantee that every model context can fit an oversized package. If complete delivery is impossible, execution must fail and stop rather than treating the reference as read.
