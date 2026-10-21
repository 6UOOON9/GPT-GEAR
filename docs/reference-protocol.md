# Embodied In-Context Learning

**English** | [简体中文](reference-protocol.zh-CN.md)

[Documentation](README.md) · [Run your first task](running.md) · [Inspect results](results.md) · [Generate text from video](reference-format.md) · [Queue configuration](queues.md)

Embodied in-context learning (ICL) supplies demonstration text, video, and action trajectories in the model’s context to help it act in the current scene. This guide covers preparing demonstration files and adding them to evaluation. Demonstrations are optional; to run without them, follow the [running guide](running.md).

The name follows the 📄 [paper’s capability evaluation](https://arxiv.org/html/2610.28259v1#S4.SS4.SSS2). Commands and configuration fields use `reference`, such as `--reference-text` and `--reference-video`.

To use existing demonstrations, read [input combinations](#1-choose-input-combinations), [file preparation](#2-prepare-files-in-advance), [offline validation](#3-offline-validation), and [adding references to evaluation](#4-add-references-to-an-episode-or-queue), in that order. For converters or format troubleshooting, consult [environment formats](#5-environment-specific-formats).

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

**Prepare reference files before `run` or `queue --run` for every environment.**

1. Prepare files for your input combination. For trajectories, prepare a descriptor JSON and JSONL in the selected environment's format.
2. If text is needed, supply existing text or use `reference annotate` from the [video-to-text tutorial](reference-format.md).
3. Check the task, camera views, and trajectory coordinate semantics, then run the offline validation below.
4. Pass original file paths when running evaluation; the launcher assembles a cache for that episode.

This project provides video-to-text generation, format validation, frame sampling, and caching. It does not download raw data, export video, generate trajectories, or fill in missing demonstrations at evaluation startup.

| Environment | Views needed for text generation | Text-generation entry point |
|---|---|---|
| RoboDojo | head / left_wrist / right_wrist | `reference annotate --benchmark robodojo` |
| LIBERO-plus | agentview / robot0_eye_in_hand | `reference annotate --benchmark libero-plus` |
| LIBERO-GeoMotion | agentview / robot0_eye_in_hand | `reference annotate --benchmark libero-geomotion` |
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

The video mapping file `videos.json` uses `format: "sim-reference-videos-v1"`, with a `videos` object mapping camera names to video file paths. This identifier describes a mapping file structure shared by all environments; `--benchmark` selects the environment, and camera names follow that environment. It serves a different purpose from the trajectory format identifiers below, which describe robot poses and actions.

The trajectory descriptor JSON points to the complete JSONL file through `files.trajectory`, relative to the descriptor's directory. When providing video with a trajectory, the descriptor must also map every reference camera through `files.videos`; some environments also support the flat fields listed below. Validation checks that the descriptor's videos and the input videos have matching file digests. File paths must remain within the descriptor's directory; absolute paths, `..`, and symbolic links are rejected.

| Environment | Trajectory format | Control point / frame |
|---|---|---|
| RoboDojo | `robodojo-codex-trajectory-v1` | left_ee / right_ee, environment frame |
| LIBERO-plus | `libero-codex-trajectory-v1` | robot0_grip_site, environment frame |
| LIBERO-GeoMotion | `libero-codex-trajectory-v1` | robot0_grip_site, environment frame |
| GR1 | `robocasa-gr1-trajectory-v1` | Dual-arm grip sites, environment frame |
| UniVTAC | `univtac-codex-trajectory-v2` | gripper_center, robot_base frame |
| RoboTwin | `robotwin-codex-dual-trajectory-v1` | Native dual-arm EE, environment frame |

### RoboDojo

`pose.reference` is `{"left":"left_ee","right":"right_ee"}`, using environment coordinates, positions in meters, and wxyz quaternions. Each non-final action contains `left` / `right`, each with `dpos`, `dquat`, and `gripper`. Gripper targets are in `[0,1]`, where 0 means closed, 1 means open, and `null` means unknown rather than hold. The final action is `null`. `sampling` contains the nominal sample interval, sampling gaps, and separate lists of frames with unknown gripper commands for each arm. See the [RoboDojo validator](../src/environments/robodojo/reference.py) for semantic constants.

A video directory can contain one matching `*head.mp4`, `*left_wrist.mp4`, and `*right_wrist.mp4` each, or use an explicit `videos.json` mapping, which takes precedence when present. The mapping uses `sim-reference-videos-v1` as described above; `robodojo-reference-videos-v1` is also accepted with the same mapping structure. Text generation requires `head`, `left_wrist`, and `right_wrist` views. See the [video-to-text tutorial](reference-format.md#robodojo-three-view-video) for a directory example. Whether to provide trajectories and video still follows the input combinations above.

### LIBERO-plus

`pose.reference` is `robot0_grip_site`. Each action contains `dpos`, `dquat`, and `gripper`. Gripper values are `open`, `close`, or `null`, with `null` meaning unknown. The final action is `null`. `sampling` contains video declarations, the nominal interval, gaps, and lists of frames with unknown gripper commands.

A video directory can contain one matching `*agentview.mp4` and one matching `*wrist.mp4`, or use an explicit `videos.json` mapping as described above.

### LIBERO-GeoMotion

Uses the [LIBERO trajectory format](#libero-plus) with `agentview` and wrist videos, each 256 × 256, selected with `--benchmark libero-geomotion`. See [environment configuration](environments/libero-geomotion.md#references-and-evaluation-configurations) for reference inputs and queue settings. Cache, modality, and delivery rules are shared with the other environments.

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
