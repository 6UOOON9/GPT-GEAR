# Generate textual steps from demonstration videos

**English** | [简体中文](reference-format.zh-CN.md)

[Documentation](README.md) · Next: [Use in-context learning in evaluation](reference-protocol.md)

This tutorial shows how to turn demonstration videos you have prepared into English numbered steps in `steps.txt`. This project provides only text generation; prepare videos yourself in advance. Generating text does not require trajectories, the original dataset, or a simulation environment.

## 1. Install and prepare

If you have followed the [installation guide](installation.md), activate the tool environment from the repository root:

```bash
source .venvs/codex-mcp/bin/activate
```

If you only need text generation, you can instead run `python -m pip install -e .` in a separate Python environment without the MCP extra.

Ensure `ffmpeg`, `ffprobe`, and a configured `codex` command are available. Text generation calls the model through the local Codex CLI and uses its model configuration by default. The Python component needs only the standard library, without simulation dependencies. Network connections inherit proxy environment variables such as `HTTPS_PROXY`, `HTTP_PROXY`, and `NO_PROXY` from the current process. The program does not set a local proxy address or automatically retry failed or timed-out model calls.

Put one demonstration's videos in each directory. Keep different views of the same demonstration together and different demonstrations separate. Supported camera configurations are listed below. `--benchmark` selects the cameras and text-generation prompt; it does not start a simulator.

| Demonstration type | `--benchmark` | Required video views |
|---|---|---|
| RoboDojo | `robodojo` | `head`, `left_wrist`, `right_wrist` |
| LIBERO-plus | `libero-plus` | `agentview`, `robot0_eye_in_hand` |
| LIBERO-GeoMotion | `libero-geomotion` | `agentview`, `robot0_eye_in_hand` |
| UniVTAC | `univtac` | `head`, `wrist` |
| RoboCasa GR1 | `robocasa-gr1` | `egoview` |
| RoboTwin | `robotwin` | `head_camera`, `left_camera`, `right_camera` |

The command supports the configurations above, not arbitrary camera combinations.

## 2. Organize videos and generate text

Choose the configuration matching your videos: [RoboDojo](#robodojo-three-view-video) · [LIBERO-plus](#libero-plus-two-view-video) · [LIBERO-GeoMotion](#libero-geomotion-two-view-video) · [RoboCasa GR1](#robocasa-gr1-single-view-video) · [UniVTAC](#univtac-two-view-video) · [RoboTwin](#robotwin-three-view-expert-video).

### RoboDojo: three-view video

Prepare this directory:

```text
references/robodojo/stack_blocks/
├── head.mp4
├── left_wrist.mp4
└── right_wrist.mp4
```

These filenames require no `videos.json`. Filenames ending in `head.mp4`, `left_wrist.mp4`, and `right_wrist.mp4` are also supported, with exactly one match per suffix. To use other filenames, add a `videos.json` mapping, which takes precedence when present:

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "head": "head.mp4",
    "left_wrist": "left_wrist.mp4",
    "right_wrist": "right_wrist.mp4"
  }
}
```

Keep camera names unchanged. Adjust filenames to your videos; paths are relative to this directory. Then run the following command, which calls the model and writes the generated output:

```bash
gpt-gear reference annotate --benchmark robodojo references/robodojo/stack_blocks
```

### UniVTAC: two-view video

Prepare head and wrist MP4 videos, with filenames ending in `head.mp4` and `wrist.mp4`. Include one file for each view:

```text
references/univtac/insert_HDMI/
├── demo_head.mp4
└── demo_wrist.mp4
```

```bash
gpt-gear reference annotate --benchmark univtac references/univtac/insert_HDMI
```

With these names, `videos.json` is unnecessary. For other filenames, use the mapping format above with only the `head` and `wrist` camera keys and their corresponding filenames.

### RoboCasa GR1: single-view video

Prepare one MP4 file whose name ends in `egoview.mp4`:

```text
references/gr1/PnPCupToDrawerClose/
└── egoview.mp4
```

```bash
gpt-gear reference annotate --benchmark robocasa-gr1 references/gr1/PnPCupToDrawerClose
```

With this name, `videos.json` is unnecessary. For another filename, use the same mapping format with only the `egoview` camera key and its filename.

### LIBERO-plus: two-view video

Prepare external-view and wrist-view videos from the same demonstration. Filenames should end in `agentview.mp4` and `wrist.mp4`, with one file per view:

```text
references/libero/pick_up_bowl/
├── demo_agentview.mp4
└── demo_wrist.mp4
```

```bash
gpt-gear reference annotate --benchmark libero-plus references/libero/pick_up_bowl
```

With these names, `videos.json` is unnecessary. The wrist video's camera name is `robot0_eye_in_hand`. To use other filenames, add the following mapping and adjust filenames as needed:

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "agentview": "demo_agentview.mp4",
    "robot0_eye_in_hand": "demo_wrist.mp4"
  }
}
```

This workflow uses LIBERO-plus's visual annotation prompt and only video images, camera labels, and time labels. It does not require the LIBERO simulator or trajectories. The two videos are sampled independently; frame-by-frame synchronization is not required. During evaluation, the generated `steps.txt` can be used alone or with video, trajectories, or both. See the [in-context learning guide](reference-protocol.md).

### LIBERO-GeoMotion: two-view video

Use the exported `agentview.mp4` and `wrist.mp4` (each 256 × 256) and their `videos.json`, with the GeoMotion benchmark identifier:

```bash
gpt-gear reference annotate --benchmark libero-geomotion /path/to/geomotion-references-256/task_000
```

### RoboTwin: three-view expert video

Put three separate views from the same expert demonstration in one directory:

```text
references/robotwin/beat_block_hammer/videos/
├── head_camera.mp4
├── left_camera.mp4
└── right_camera.mp4
```

```bash
gpt-gear reference annotate --benchmark robotwin \
  references/robotwin/beat_block_hammer/videos
```

Filenames ending in these camera names plus `.mp4` are also supported. Alternatively, use `videos.json` to specify other filenames:

```json
{
  "format": "sim-reference-videos-v1",
  "videos": {
    "head_camera": "front.mp4",
    "left_camera": "left.mp4",
    "right_camera": "right.mp4"
  }
}
```

No RoboTwin simulator, task source code, or trajectories are required. The model reads only sampled images and camera/time labels. It produces English numbered steps describing visible operations, uncertainties, and scene conditions to check before execution.

The default is 1 FPS, with at most 42 images across all three views. Exceeding the limit fails before the model call. For longer videos, explicitly lower the sampling rate, for example with `--reference-fps 0.5`. First and last frames are always retained; excess attachments are not silently dropped. Lower sampling rates may miss brief actions, so review the generated output.

## 3. Inspect generated output

By default, the input video directory gains:

```text
steps.txt                 # Generated English numbered steps
annotation/
├── frames/               # Sampled images supplied to the model
├── prompt.txt            # Prompt used
├── response.txt          # Raw model response
└── audit.json            # Sampling and generation record
```

Each video is sampled independently at 1 FPS by default, adjustable with `--reference-fps`, while retaining first and last frames. The model describes visible operations using those images and their camera/time labels. Check `steps.txt` against the videos after generation. The program checks numbering format, not the accuracy of the steps or whether the demonstration succeeded.

## 4. Batch processing and common options

You can process several demonstration directories of the same type in one command. Their final directory names must be distinct:

```bash
gpt-gear reference annotate --benchmark univtac \
  references/univtac/insert_HDMI \
  references/univtac/insert_USB
```

To save text separately, use `--output-root`:

```bash
gpt-gear reference annotate --benchmark univtac \
  references/univtac/insert_HDMI \
  --output-root outputs/reference_text
```

This example saves `outputs/reference_text/insert_HDMI/steps.txt` and the adjacent `annotation/`, while leaving videos in their original directory. The output subdirectory must not exist or must be empty. Existing text, generation records, or recorded failure states are not overwritten. Use a fresh output root when saving a new generation separately.

If the source directory has `provenance.json`, the program copies it and checks its text status. Existing `text.status=complete`, `text.status=failed`, or a text digest prevents generation even with a new `--output-root`, preserving existing evidence. Failure information is written to its `text` field only when provenance already exists. A failed run may not leave `annotation/`; retain the terminal error output.

| Option | Purpose |
|---|---|
| `--benchmark` | Select the demonstration type; default `robodojo`, but explicit selection is recommended |
| `--output-root` | Save under `<input_directory_name>/` within this root; default is the input directory |
| `--codex-model` | Select a model; default is the local Codex configuration |
| `--reference-fps` | Sampling rate, default `1`; must be finite and positive; lower it if RoboTwin exceeds 42 images |
| `--timeout` | Model-call timeout in seconds, default `600` |

View complete command help:

```bash
gpt-gear reference annotate --help
```

## 5. Use text in evaluation

Text generation only needs video. When adding `steps.txt` to evaluation, supply text alone or combine it with video, trajectories, or both. Trajectories cannot be used alone. Review generated steps first, run offline validation as described in the [in-context learning guide](reference-protocol.md), and pass selected original file paths to `run` or a queue.

## Common problems

| Situation | What to do |
|---|---|
| Camera mismatch or several videos with the same suffix | Keep one demonstration per directory; check camera keys or explicitly add `videos.json` |
| Output directory already contains text or audit records | Use a new `--output-root`; completed or failed states in source provenance still prevent generation |
| Model timeout or authentication failure | Check Codex configuration, networking, and terminal errors; inspect the `text` field if provenance exists; there is no automatic retry |
| RoboTwin sampling exceeds 42 images | Lower `--reference-fps` and prepare again using a new output directory |
| You want to generate directly from HDF5 / LeRobot | Prepare videos with external tools first; this project does not export raw data |
