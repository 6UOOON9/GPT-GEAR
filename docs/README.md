# Documentation

**English** | [简体中文](README.zh-CN.md)

[Back to the project](../README.md)

If you are new to GPT-GEAR, start with installation and a task without demonstrations. Once that works, try in-context learning (ICL) or batch evaluation. Documentation is available in English and Simplified Chinese; use the links beneath each title to switch languages. Commands, options, and data fields retain their code names.

Suggested reading order: [Installation](installation.md) → [Run a task](running.md) → [Inspect results](results.md) → [In-context learning (optional)](reference-protocol.md). You only need the configuration and commands for the environment you use.

Unless stated otherwise, run commands from the repository root with the tool environment activated. Replace `/path/to/...` with local paths. Each single-episode `run` needs a fresh output directory; queues can resume with the original configuration.

## Getting started

| Guide | What you will do |
|---|---|
| [Installation and environment setup](installation.md) | Install the tools and prepare simulation dependencies and separate interpreters |
| [Run your first task](running.md) | Choose an environment, check it, and launch one episode |
| [Results and troubleshooting](results.md) | Read official results, locate logs, and diagnose startup problems |
| [Queues and batch evaluation](queues.md) | Write configurations, inspect plans, run, and resume after a single episode works |
| [Project overview](project-overview.md) | Understand the roles of the model, tools, controller, and simulator |

<a id="reference-demonstrations-optional"></a>

## In-context learning (optional)

| Guide | When to use it |
|---|---|
| [In-context learning guide](reference-protocol.md) | Add video, trajectories, and text to evaluation, or build format converters |
| [Generate textual steps from video](reference-format.md) | Turn demonstration videos into readable instructions; skip this if text is already available |

## Environment configuration

All supported environments share the installation, run, and queue workflows. Guides in `environments/` cover their source trees, assets, specific options, and evaluation differences.

| Environment | Configuration topics |
|---|---|
| [RoboDojo](environments/robodojo.md) | Submodules, evaluation layouts, and seed/layout selection |
| [LIBERO-plus](environments/libero-plus.md) | Task variants, initial states, and native-step budgets |
| [LIBERO-GeoMotion](environments/libero-geomotion.md) | Fixed geometric scenes, initialization, and references |
| [RoboCasa GR1](environments/robocasa-gr1.md) | HDF5 environment configuration, dual-arm control, and measured depth |
| [UniVTAC](environments/univtac.md) | Tactile modes, continuous gripper control, and control frequency |
| [RoboTwin](environments/robotwin.md) | Clean/Random scenes, dual-arm control, and sample selection |

## Developer reference (optional)

You do not need these guides to run tasks. Consult them when changing the implementation or contributing.

| Guide | Topics |
|---|---|
| [Architecture](architecture.md) | Processes, modules, tool delivery, control, and environment adapters |
| [Contributing](../CONTRIBUTING.md) | Report issues, run tests, update documentation, and add environments |
