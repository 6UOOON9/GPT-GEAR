# Contributing

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

[Project home](README.md) · [Documentation](docs/README.md) · [Architecture](docs/architecture.md)

Issue reports, documentation improvements, tests, and environment adapters are welcome. A small, self-contained reproduction usually helps others diagnose a problem more effectively than a complete run directory.

## Reporting issues

Describe the expected behavior, actual outcome, and minimal reproduction steps in a repository Issue. Include the relevant details:

| Information | Example or explanation |
|---|---|
| Project version | Current commit or release |
| Environment and source | Benchmark, host commit, and any local changes |
| Task conditions | Task name, seed, layout / init-state / task-config |
| How you ran it | Command or minimal queue configuration; paths may be replaced with placeholders |
| Software and hardware | Both Python versions, GPU, simulation dependencies, and Codex CLI version |
| Input settings | Model, reference, depth, and tactile options |
| Error evidence | `doctor` output, relevant log excerpts, and `summarize` output |

`session.json` contains a session token; do not upload it. Remove credentials and unrelated personal paths before sharing logs. See [results and troubleshooting](docs/results.md) for file locations.

When reporting compatibility with a new environment, distinguish between passing configuration checks, passing a model-free interface check, completing an episode with a real model, and achieving official task success.

## Setting up a development environment

Run from the repository root using a separate tool environment:

```bash
python3.12 -m venv .venvs/codex-mcp
.venvs/codex-mcp/bin/python -m pip install -e '.[mcp,test]'
source .venvs/codex-mcp/bin/activate
```

Continue using the simulator's original interpreter. Shared code should remain compatible with Python 3.10; MCP-related code uses Python 3.11+. Package imports and command help must not load simulation dependencies prematurely.

## Running checks

Offline tests do not require a GPU, simulation assets, or model calls:

```bash
python -m pytest -q
gpt-gear --help
gpt-gear reference annotate --help
gpt-gear reference prepare --help
```

CI runs the full CPU test suite on Python 3.11 / 3.12 and checks the simulation core on Python 3.10. Tests cover real HTTP / STDIO MCP communication, mock hosts, control contracts, reference media, and queues. Passing offline tests does not replace validation in a real simulator.

For documentation-only changes, check links, code blocks, command options, and example configurations against the current implementation. For control or adapter changes, add tests that reproduce the behavior difference and record which checks actually ran.

## Changing code or adding environments

Read the [architecture guide](docs/architecture.md) first. Environment-specific code lives in `src/environments/<environment>/`; shared modules manage sessions, protocols, and queues.

1. Declare preflight checks, task resolution, and launch behavior in `backend.py`, keeping this layer dependent only on the standard library.
2. Connect initialization, observations, execution, termination, and official results in the native adapter.
3. Define the control point, coordinate frames, gripper units, budget units, and observations that may be exposed.
4. Provide an environment-specific validator if references are supported; update that environment's prompt when it needs dedicated rules.
5. Run offline tests, check the interface on a prepared simulation machine, then complete a real-model episode with fixed initial conditions.

Preserve shared constraints such as main-thread execution, latest-observation validation, request deduplication, and stopping on uncertain results. Do not change official success criteria, automatically replay actions, or hide failures to make checks pass.

## Writing documentation

Write for readers who are new to the project. Start with purpose, prerequisites, and the shortest workflow, then explain options and formats. Use `gpt-gear` in commands and `/path/to/...` for paths. State whether a command starts a simulator or calls a model.

Use [docs/README.md](docs/README.md) as the documentation entry point and put guides in `docs/`. Describe currently supported features and workflows; older implementations remain available through Git history. Files in `src/prompts/` and environment `prompts/` directories are runtime model instructions. Editing them changes evaluation behavior and is not ordinary documentation formatting.

English is the default at the existing `.md` paths. Each user-facing guide has a sibling `*.zh-CN.md` version, with a language switch beneath the title. Keep both versions in sync, link to guides in the same language, and update section anchors when translating headings. Runtime prompts and license texts are not part of this translation workflow.

Keep installation, preflight, single-episode, model-free check, and queue workflows in the corresponding shared guides. The running guide keeps the shortest commands for each environment; environment-specific configuration belongs in `docs/environments/` to avoid repeating common procedures. When adding an environment, update the home page's environment table and documentation index. Maintain reference-file fields centrally in the reference protocol. When moving a document, update incoming links and relative paths.

## Submitting a pull request

Describe the problem, final behavior, and validation results. For environment adapters, state the source version, whether you ran a real simulator, whether you called a model, and what remains unverified. Update documentation when usage changes.

Keep changes focused on a clear problem. Do not commit virtual environments, assets, reference datasets, session credentials, or execution outputs. Preserve existing copyright headers and provenance records; see [NOTICE](NOTICE) and [LICENSE](LICENSE) for external implementations.
