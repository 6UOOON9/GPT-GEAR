<h1 align="center">GPT-<strong>G</strong>eneralist <strong>E</strong>nd-effector <strong>A</strong>ction <strong>R</strong>easoning</h1>

<p align="center"><strong>English</strong> | <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <strong>Exploring embodied capabilities and closed-loop robot control with vision-language models</strong><br>
  <sub>Perceive · Reason · Act · Verify</sub>
</p>

<p align="center">
  <a href="assets/Analysis_of_Astra_in_Robotic_Manipulation.pdf"><img src="https://img.shields.io/badge/Paper-PDF-B31B1B?style=flat-square" alt="Read the paper PDF"></a>
  <a href="https://6uooon9.github.io/GPT-GEAR/"><img src="https://img.shields.io/badge/Project-Page-357ABD?style=flat-square" alt="GPT-GEAR project page"></a>
  <a href="#results"><img src="https://img.shields.io/badge/Evaluation-5_Benchmarks-459B6C?style=flat-square" alt="Evaluation on five benchmarks"></a>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/Docs-Getting_Started-D78337?style=flat-square" alt="Getting started documentation"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT_%26_Apache--2.0-64748B?style=flat-square" alt="MIT and Apache-2.0 licenses"></a>
</p>

<p align="center">
  <a href="#news">News</a> &nbsp;·&nbsp;
  <a href="#overview">Overview</a> &nbsp;·&nbsp;
  <a href="#embodied-capabilities">Capabilities</a> &nbsp;·&nbsp;
  <a href="#results">Results</a> &nbsp;·&nbsp;
  <a href="#capability-profile">Real World</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="docs/README.md">Documentation</a>
</p>

---

**What happens when a general-purpose vision-language model directly takes control of a robot? Does it really perform as well as we expect?**

Welcome to **GPT-GEAR**! We provide a **robot control and evaluation framework spanning multiple simulation environments**, bringing model interaction, reference demonstrations, closed-loop execution, and batch evaluation together so you can explore what general-purpose models can do with robots. Here, a model observes a scene through cameras, learns from demonstrations, tries an action, and adjusts its next move using the robot's feedback. From understanding an instruction to completing a grasp, we ask: **what can the model already do, and where does it still struggle?**

Our work explores **depth perception, embodied in-context learning, and tactile understanding** across five environments: **LIBERO-plus, RoboTwin, UniVTAC, RoboCasa GR1, and RoboDojo**. Take a look at the paper and project page, try your own tasks with the code, and join us in exploring how general-purpose models can interact with the physical world!

<a id="news"></a>

## News

- ✨ **2026/10/21** — Our paper and project page are now available! Visit the project page for more demos, explore our method and results, and share your thoughts and feedback.
- 📄 **2026/10/20** — **Research report**: [*Large Multimodal Models for Direct Robot Control: GPT-6 as a Beginning*](assets/Analysis_of_Astra_in_Robotic_Manipulation.pdf). We share GPT-6 Astra's capabilities and limitations in robotic manipulation, along with questions for further exploration.

<a id="overview"></a>
<a id="method"></a>
<a id="工作方式"></a>

## Overview

**Observe, try, and adjust with feedback.** GPT-GEAR gives the model a set of tools for interacting with robots, turning its understanding of a scene into actions step by step. Camera images show what the scene looks like now, reference demonstrations offer clues about what to do, and execution feedback helps the model choose its next move. Along the way, it can revisit earlier observations, draw on demonstrated actions, and observe the scene again after each action. This loop connects reasoning with execution and makes each attempt an opportunity to understand the model's capabilities.

<p align="center">
  <a href="assets/readme/method.png">
    <img src="assets/readme/method.png" width="100%" alt="GPT-GEAR framework: task instructions, multi-camera observations, and camera calibration; Observe retrieves history, Reference reads video, text, and trajectories, Act executes actions, Status returns feedback, and Finish ends the episode.">
  </a>
</p>

<p align="center">
  <sub>GPT-GEAR Overview · Observations, references, actions, and feedback connect the model to the robot. <a href="assets/readme/method.png">View full-resolution figure ↗</a></sub>
</p>

<a id="embodied-capabilities"></a>

## Embodied Capabilities

**Getting a robot to complete a task starts with understanding space, learning from examples, and making sense of contact.** We explore these three abilities: can the model estimate and use depth, apply lessons from a demonstration to a new scene, and adjust its actions using tactile feedback? The figure below brings these questions together.

<p align="center">
  <a href="assets/readme/embodied-capabilities.png">
    <img src="assets/readme/embodied-capabilities.png" width="100%" alt="Three areas of embodied capability analysis: estimating depth from RGB and using measured depth for spatial grounding; learning manipulation from reference demonstrations; interpreting tactile images and pressure to adjust actions.">
  </a>
</p>

<p align="center">
  <sub>Depth perception · Embodied in-context learning · Tactile understanding. <a href="assets/readme/embodied-capabilities.png">View full-resolution figure ↗</a></sub>
</p>

<a id="results"></a>

## Results

**How does the same model handle different robotic manipulation challenges?** We evaluate it on five benchmarks. The red marks below show **GPT-6 Astra**'s performance, highlighting both its potential and the gaps that remain.

<p align="center">
  <a href="assets/readme/results.png">
    <img src="assets/readme/results.png" width="100%" alt="Five-benchmark comparison. GPT-6 Astra success rates: LIBERO-Plus 83.50%, RoboTwin 2.0 76.00%, UniVTAC 72.50%, RoboCasa GR1 18.96%, and RoboDojo 26.92%; RoboDojo Score is 35.17.">
  </a>
</p>

<p align="center">
  <sub>Performance across five robotic manipulation benchmarks. <a href="assets/readme/results.png">View full-resolution figure ↗</a></sub>
</p>

<a id="capability-profile"></a>

## Capability Profile & Real-World Validation

**From simulation scores to a real robot's grasp, we want to build a fuller picture of what the model can do.** The radar charts below bring together benchmark performance and individual capabilities, while the right-hand panel shows real-world manipulation and compares zero-shot execution with in-context learning (ICL). Visit our [project page](https://6uooon9.github.io/GPT-GEAR/) for more demos and to see the robot in action!

<p align="center">
  <a href="assets/readme/capability-profile-real-world.png">
    <img src="assets/readme/capability-profile-real-world.png" width="100%" alt="Radar charts compare benchmark performance and latency, plus generalization, task understanding, long-horizon behavior, high-order operation, precision, and memory. Real-world validation shows a mango-grasping sequence and zero-shot versus ICL results across five tasks.">
  </a>
</p>

<p align="center">
  <sub>Benchmark performance · Capability profile · Real-world validation. <a href="assets/readme/capability-profile-real-world.png">View full-resolution figure ↗</a></sub>
</p>

Find more experiments and analysis in the paper linked above. Want to try it yourself? Start with the environments below and the [quick start](#quick-start), and let us know what you discover!

---

## Supported environments

| Environment | Example task | Default inputs | Guide |
|---|---|---|---|
| RoboDojo | `align_blocks` | Three-view RGB, dual-arm state | [Environment setup](docs/environments/robodojo.md) |
| LIBERO-plus | `libero_spatial/0` | Two-view RGB, single-arm state | [Environment setup](docs/environments/libero-plus.md) |
| RoboCasa GR1 | `PnPCupToDrawerClose` | RGB, dual-arm state, measured depth | [Environment setup](docs/environments/robocasa-gr1.md) |
| UniVTAC | `insert_HDMI` | RGB, robot state, resultant tactile forces | [Environment setup](docs/environments/univtac.md) |
| RoboTwin | `adjust_bottle` | Three-view RGB, dual-arm state | [Environment setup](docs/environments/robotwin.md) |

See the [installation guide](docs/installation.md) for dependencies and assets.

## Installation

Before running robot tasks, install the simulation environment you plan to use, prepare its assets, and run its native example. You do not need all five environments. The installation guide lists [upstream repositories and setup instructions](docs/installation.md#install-your-simulation-environment-first). The following commands install only the GPT-GEAR tools.

We recommend a separate Python 3.11+ tool environment on Linux. The example below uses Python 3.12. Run it from the repository root:

```bash
python3.12 -m venv .venvs/codex-mcp
.venvs/codex-mcp/bin/python -m pip install -e '.[mcp]'
source .venvs/codex-mcp/bin/activate

gpt-gear --help
```

You also need:

- An installed and authenticated Codex CLI. The existing local model configuration is used by default.
- At least one working simulation environment, with its own Python interpreter, assets, and rendering dependencies.
- FFmpeg for recording and video references; video references also require FFprobe.

Keep the simulation Python separate from the tool Python. Installing this project does not install simulators or download assets. See the [installation guide](docs/installation.md) for the complete setup.

## Quick start

The example below assumes LIBERO-plus is ready to use. Run all commands from the repository root and replace `/path/to/...` with local paths. Commands for other environments are in the [running guide](docs/running.md).

### 1. Check the environment

```bash
gpt-gear doctor --benchmark libero-plus --task libero_spatial/0 \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python
```

`doctor` checks the task, resources, interpreter, and tool dependencies. It does not start the simulator or model, or verify model authentication.

### 2. Run a task

```bash
gpt-gear run libero_spatial/0 outputs/libero_first_run \
  --benchmark libero-plus \
  --env-root /path/to/LIBERO-plus \
  --sim-python /path/to/libero/bin/python \
  --seed 0 --init-state-index 0 --max-native-steps 600
```

This starts the simulator and calls the model. The output directory must not already exist; do not create it beforehand. To select a model, append `--codex-model MODEL_NAME`.

### 3. Inspect the results

```bash
gpt-gear summarize outputs/libero_first_run
```

`result.json` stores the official result, `episode.mp4` stores the recording, and `observations/` stores observations. See [results and troubleshooting](docs/results.md) for result categories and diagnosis.

## Batch evaluation

Configurations are grouped into [`configs/queues/`](configs/queues/) for reproducing evaluation procedures and comparing conditions, and [`configs/single_task/`](configs/single_task/) for individual tasks with exactly one episode per file. See the [configuration guide](configs/README.md) for the full list.

The following example uses RoboCasa GR1's 24-task × 20-seed queue. First update the environment paths in the [configuration](configs/queues/robocasa_gr1.json), then inspect and run the plan:

```bash
# Print the plan without starting the simulator or model.
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20

# Execute the queue.
gpt-gear queue configs/queues/robocasa_gr1.json outputs/gr1_24x20 --run
gpt-gear summarize outputs/gr1_24x20
```

A queue can contain multiple tasks, seeds, or environments. See the [queue guide](docs/queues.md) for configuration, resuming, and retries.

## Reference demonstrations

Reference inputs are optional. Supply text or video alone, or combine text, video, and trajectories to explore different input settings. Astra draws on the demonstrated procedure while making decisions for the current scene.

Prepare reference files before evaluation for every environment. This project generates textual steps from existing videos, validates inputs, and reads references. It does not download data, export videos, or generate trajectories; export those from your simulation environment.

- [Use reference demonstrations in evaluation](docs/reference-protocol.md)
- [Generate textual steps from existing videos (optional)](docs/reference-format.md)

## Documentation and code

| Topic | Where to start |
|---|---|
| Installation through your first task | [Installation](docs/installation.md) → [Running a task](docs/running.md) → [Results](docs/results.md) |
| Multi-task evaluation and result analysis | [Queues](docs/queues.md) → [Results and troubleshooting](docs/results.md) |
| Assets, observations, and evaluation options | [Guides for the five environments](docs/README.md#environment-configuration) |
| Control, protocols, and environment adapters | [Architecture](docs/architecture.md) |
| Tests, issue reports, and contributions | [Contributing](CONTRIBUTING.md) |

```text
src/
├── execution/       # Launching, queues, sessions, video, and results
├── control/         # Robot control and pose deltas
├── protocol/        # MCP tools, HTTP communication, and feedback
├── perception/      # Camera calibration, depth, and observation modalities
├── environments/    # Adapters for the five simulation environments
├── demonstrations/  # Reference processing and video-to-text generation
└── prompts/         # Shared model instructions
configs/
├── queues/          # Evaluation reproduction and condition comparisons
└── single_task/     # Single-task tests, one episode per file
tests/               # Offline regression tests
docs/                # User and developer documentation
└── environments/    # Environment-specific configuration guides
```

## Join the community

Use repository Issues to share questions, reproduction notes, and requests for new environments. Documentation improvements, tests, and environment adapters are welcome too! Before contributing, read the [contribution guide](CONTRIBUTING.md) and include your environment, reproduction steps, and validation scope.

## License and acknowledgments

This project reuses implementations from [RoboDojo](https://github.com/robodojo-benchmark/RoboDojo), [RPent](https://github.com/RLinf/RPent), and related environment adapters. Files from different sources retain their respective MIT or Apache-2.0 licenses and attribution. See [LICENSE](LICENSE), [NOTICE](NOTICE), and the [license directory](licenses/). Simulation environments, datasets, and assets must be prepared separately.
