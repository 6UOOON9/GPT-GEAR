"""Launch one simulator and a fresh Codex policy session using only the stdlib.

This process never connects to the control endpoint or issues robot actions.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

PACKAGE_DIR = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(PACKAGE_DIR))
from execution.config import FINALIZE_GRACE, parse_args, positive_seconds
from execution.artifacts import write_json
from protocol.contracts import capabilities, validate_capabilities
from protocol.feedback import DEFAULT_TOOL_OUTPUT_TOKEN_LIMIT, FEEDBACK_FORMAT_VERSION
from execution.prompts import evaluation_prompt
from demonstrations.cache import (
    DIRECTORY, MANIFEST, TOOL as REFERENCE_TOOL,
    load_manifest, output_token_limit, prepare as prepare_reference,
)
from demonstrations.common import reference_enabled, sha256_file

MCP_SERVER = PACKAGE_DIR / 'protocol/mcp_server.py'
POLL_SECONDS = 0.1
STOP_GRACE = 5.0


class LaunchError(Exception):
    def __init__(self, reason, code=1):
        super().__init__(reason)
        self.code = code


class Interrupted(LaunchError):
    def __init__(self, signum):
        super().__init__(f'interrupted by signal {signum}', 128 + signum)


def sanitize_event(value, secrets=()):
    """Redact diagnostic copies only; never touch the model's MCP image stream.

    Codex can wrap an MCP result in JSON serialized inside a text content block.
    Decode those nested objects as well as ordinary image blocks.
    """
    if isinstance(value, dict):
        result = {}
        reference_records = value.get('source') == 'reference_trajectory'
        image = value.get('type') in ('image', 'input_image')
        for key, item in value.items():
            if key.lower() in ('token', 'authorization'):
                result[key] = '[redacted]'
            elif reference_records and key == 'records':
                result['records_omitted'] = True
                result['record_count'] = len(item) if isinstance(item, list) else None
            elif key == 'trace':
                result[key] = '[execution detail omitted]'
            elif image and key in ('data', 'image_url'):
                result[key] = '[image body omitted]'
                result[key + '_omitted_chars'] = len(item) if isinstance(item, str) else None
            else:
                result[key] = sanitize_event(item, secrets)
        return result
    if isinstance(value, list):
        return [sanitize_event(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
        if value.lstrip().startswith(('{', '[')):
            try:
                nested = json.loads(value)
            except ValueError:
                # A truncated serialized result must not leak a partial image.
                if '"data"' in value or 'base64,' in value or '"records"' in value:
                    return '[malformed serialized payload omitted]'
            else:
                return json.dumps(sanitize_event(nested, secrets), ensure_ascii=False)
        return re.sub(r'data:image/[^;\s]+;base64,[A-Za-z0-9+/=]+',
                      '[image body omitted]', value)
    return value


class EventLog:
    """Drain Codex stdout continuously, persisting only sanitized JSON events."""

    def __init__(self, source, destination, secrets=()):
        self.source = source
        self.secrets = secrets
        self.destination = destination
        self.failed = threading.Event()
        self.thread = threading.Thread(target=self._drain, name='codex-event-log', daemon=True)
        self.thread.start()

    def _drain(self):
        try:
            for line in self.source:
                if self.failed.is_set():
                    continue  # Still drain so a failed disk cannot block the child.
                try:
                    try:
                        event = sanitize_event(json.loads(line), self.secrets)
                    except (ValueError, UnicodeError):
                        event = {'type': 'diagnostic.omitted', 'reason': 'non-JSON stdout'}
                    self.destination.write(json.dumps(event, ensure_ascii=False) + '\n')
                    self.destination.flush()
                except Exception:
                    self.failed.set()
        except Exception:
            self.failed.set()
        finally:
            self.source.close()

    def check(self):
        if self.failed.is_set():
            raise LaunchError('Codex event log failed (diagnostic payload not recorded)')

    def finish(self):
        # Call after owned process groups have been stopped, so all pipe writers exit.
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise LaunchError('Codex event log did not drain after process cleanup')
        self.check()


def toml_string(text):
    # JSON strings (with literal Unicode) are TOML basic strings as well.
    return json.dumps(text, ensure_ascii=False).replace('\x7f', '\\u007f')


def codex_command(executable, args, prompt, session):
    # Keep Codex's normal config compatibility: existing user configs can contain
    # legacy keys. Strict validation would abort before any model/control work.
    command = [executable, 'exec', '--skip-git-repo-check', '-C', str(args.output),
               '--sandbox', 'danger-full-access',
               '-c', 'approval_policy="never"',
               '-c', 'features.code_mode.direct_only_tool_namespaces=["mcp__sim"]',
               '-c', f'tool_output_token_limit={DEFAULT_TOOL_OUTPUT_TOKEN_LIMIT}',
               '-c', f'model_context_window={args.codex_context_window}',
               '-c', 'developer_instructions=' + toml_string(prompt),
               '--json', '--color', 'never',
               '--output-last-message', str(args.output / 'codex_final.txt')]
    config = dict(command=str(args.codex_mcp_python),
                  args=[str(MCP_SERVER), '--session', str(args.output / 'session.json')],
                  cwd=str(args.output), required=True, enabled=True,
                  startup_timeout_sec=30, tool_timeout_sec=session['request_timeout'] + 30,
                  enabled_tools=['observe', 'act', 'status', 'finish']
                                + (['read_depth'] if getattr(args, 'measured_depth', False) else [])
                                + ([REFERENCE_TOOL] if reference_enabled(args) else []))
    for key, value in config.items():
        encoded = json.dumps(value, ensure_ascii=False)
        command.extend(['-c', f'mcp_servers.sim.{key}={encoded}'])
    if reference_enabled(args):
        limit = output_token_limit(args.output)
        command.extend(['-c', f'mcp_servers.sim.tools.{REFERENCE_TOOL}.output_token_limit={limit}'])
    if args.codex_model:
        command.extend(['--model', args.codex_model])
    # No task strategy, credentials or prompt file content in the user message.
    command.append('Connect to the existing simulation episode; do not start simulation or another Codex.\n'
                   f'Session file: {json.dumps(str(args.output / "session.json"), ensure_ascii=False)}\n'
                   'Use only the configured sim MCP tools for control.\n'
                   + ('References ENABLED: call read_reference once after observe and before act.\n'
                      if reference_enabled(args) else 'References DISABLED.\n') +
                   'Begin with observe() for the initial saved record; act returns each new observation.\n'
                   'observe(observation_id=N) reads history only, never captures a new frame.\n'
                   'Inspect all RGB images attached to tool results directly; '
                   'no separate image-opening call is needed.')
    return command


def preflight_mcp(args):
    if not MCP_SERVER.is_file() or not args.codex_mcp_python.is_file():
        raise LaunchError("MCP tool environment/entrypoint missing; run pip install -e '.[mcp]' from "
                          "the project root in the tool environment, or set --codex-mcp-python", 2)
    try:
        checked = subprocess.run([str(args.codex_mcp_python), str(MCP_SERVER), '--check',
                                  '--depth-estimation', str(args.depth_estimation).lower()]
                                 + ['--measured-depth', str(getattr(args, 'measured_depth', False)).lower()]
                                 + (['--reference'] if reference_enabled(args) else []),
                                 cwd=PACKAGE_DIR, capture_output=True, text=True, check=True, timeout=30)
        info = json.loads(checked.stdout)
        if (info['mcp_version'] != '1.29.1'
                or info['depth_estimation'] != args.depth_estimation
                or info['tools'] != ['observe', 'act', 'status', 'finish']
                    + (['read_depth'] if getattr(args, 'measured_depth', False) else [])
                    + ([REFERENCE_TOOL] if reference_enabled(args) else [])):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        raise LaunchError("MCP preflight failed; run pip install -e '.[mcp]' from the project root using "
                          "--codex-mcp-python's interpreter (no simulation was started)", 2) from None
    return info


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def validate_session(value, args):
    """Do not echo manifest contents: they contain a local bearer token."""
    if not isinstance(value, dict):
        raise LaunchError('invalid session manifest (expected JSON object)')
    try:
        validate_capabilities(value)
        if any(value[k] != v for k, v in capabilities(
                args.depth_estimation, args.reference_manifest_sha256, args.benchmark, getattr(args, 'tactile_mode', None), getattr(args, 'measured_depth', None)).items()):
            raise ValueError('session capabilities disagree')
        endpoint = urlsplit(value['endpoint'])
        valid = (value['protocol'] == 'sim-codex-v1'
                 and endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1'
                 and endpoint.port is not None and endpoint.path == '/control'
                 and not endpoint.username and not endpoint.password
                 and not endpoint.query and not endpoint.fragment
                 and Path(value['output_dir']).resolve() == args.output
                 and value['identity'] == args.host_info['identity']
                 and isinstance(value['token'], str) and bool(value['token'])
                 and isinstance(value['episode_id'], str) and bool(value['episode_id'])
                 and not isinstance(value['request_timeout'], bool))
        positive_seconds(value['request_timeout'])
    except (KeyError, TypeError, ValueError, argparse.ArgumentTypeError):
        valid = False
    if not valid:
        raise LaunchError('invalid session manifest (protocol, endpoint, identity or timeout)')


def wait_ready(simulator, args, check_cancelled=lambda: None):
    deadline = time.monotonic() + args.codex_startup_timeout
    while True:
        check_cancelled()
        code = simulator.poll()
        if code is not None:
            raise LaunchError(f'simulator exited before session readiness (exit {code})',
                              code if code > 0 else 1)
        path = args.output / 'session.json'
        value = read_json(path)
        if value is not None:
            validate_session(value, args)
            return value
        if time.monotonic() >= deadline:
            reason = 'invalid/unreadable session.json' if path.exists() else 'session.json not created'
            raise LaunchError(f'simulator startup timed out: {reason}')
        time.sleep(POLL_SECONDS)


def result_valid(output):
    result = read_json(output / 'result.json')
    return (isinstance(result, dict) and result.get('complete') is True
            and result.get('valid_for_success_rate') is True)


def monitor(simulator, agent, args, check_cancelled=lambda: None):
    drain_deadline = None
    agent_deadline = None
    while True:
        check_cancelled()
        sim_code, agent_code = simulator.poll(), agent.poll()
        now = time.monotonic()
        if sim_code is not None:
            if sim_code != 0:
                raise LaunchError(f'simulator failed (exit {sim_code})', sim_code if sim_code > 0 else 1)
            if not result_valid(args.output):
                raise LaunchError('simulator exited without a complete valid official result')
            if agent_code is not None:
                if agent_code != 0:
                    raise LaunchError(f'Codex failed (exit {agent_code})', agent_code if agent_code > 0 else 1)
                return
            if agent_deadline is None:
                agent_deadline = now + FINALIZE_GRACE
            if now >= agent_deadline:
                raise LaunchError('Codex did not exit after simulator finalization')
        elif agent_code is not None:
            if drain_deadline is None:
                drain_deadline = now + args.drain_timeout
                print(f'[Codex launcher] Codex exited (exit {agent_code}); '
                      'waiting for environment finalization.', flush=True)
                if agent_code != 0:
                    print(f'[Codex launcher] Codex failed; inspect {args.output / "codex_stderr.log"} '
                          f'and {args.output / "codex_events.jsonl"}.', file=sys.stderr, flush=True)
            if now >= drain_deadline:
                raise LaunchError(f'environment did not finalize after Codex exit ({agent_code})')
        time.sleep(POLL_SECONDS)


def stop_processes(processes):
    """Signal entire owned groups, including descendants of exited leaders."""
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + STOP_GRACE
    for process in processes:
        try:
            process.wait(timeout=max(0., deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in processes:
        process.wait()


def run(args):
    from environments.backends import get_backend
    try:
        args.host_info = get_backend(args.benchmark).preflight(args)
        if not args.sim_python.is_file():
            raise ValueError('simulation interpreter does not exist')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise LaunchError(f'host preflight failed: {exc}', 2) from None
    # Do not pre-create output: entry.prepare reserves it exclusively in the simulator.
    if not reference_enabled(args):
        return _run(args)
    try:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary_directory = tempfile.TemporaryDirectory(
            prefix='sim-reference-', dir=args.cache_dir)
    except OSError as exc:
        raise LaunchError(f'reference temporary directory failed: {args.cache_dir}: {exc}', 2) from None
    with temporary_directory as temporary:
        args.reference_cache = Path(temporary) / DIRECTORY
        try:
            prepare_reference(args.reference_video, args.reference_cache, trajectory=args.trajectory,
                              text=args.reference_text, mode=args.reference_mode, fps=args.reference_fps,
                              benchmark=args.benchmark, max_frames=args.reference_max_frames)
            args.reference_manifest_sha256 = sha256_file(args.reference_cache / MANIFEST)
            load_manifest(Path(temporary), args.reference_manifest_sha256)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise LaunchError(f'reference preflight failed ({type(exc).__name__}): {exc}', 2) from None
        return _run(args)


def _run(args):
    output = args.output
    server_log = Path(str(output) + '.server.log')
    fallback_status = Path(str(output) + '.launcher.json')
    if any(p.exists() or p.is_symlink() for p in (output, server_log, fallback_status)):
        raise LaunchError(f'Refusing to reuse output or log: {output}', 2)
    prompt_bytes = evaluation_prompt(args).encode('utf-8')
    prompt = prompt_bytes.decode('utf-8')
    if not prompt.strip():
        raise LaunchError('missing/empty evaluation prompt', 2)
    executable = shutil.which('codex')
    if executable is None:
        raise LaunchError('Codex executable not found in PATH', 2)
    try:
        version = subprocess.run([executable, '--version'], capture_output=True, text=True,
                                 check=True, timeout=10).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        raise LaunchError('cannot query Codex version; check the local installation', 2) from None
    mcp_info = preflight_mcp(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    from execution import __version__
    metadata = dict(started_at=time.time(), task_name=args.task,
                    tool_version=__version__, host=args.host_info,
                    simulator_python=str(args.sim_python),
                    requested_layout_id=args.layout_id,
                    codex_version=version, model_override=args.codex_model,
                    codex_context_window=args.codex_context_window,
                    control_transport='mcp', mcp_version=mcp_info['mcp_version'],
                    mcp_python=str(args.codex_mcp_python),
                    prompt_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
                    instruction_role='developer', sandbox='danger-full-access',
                    network_access=True, approval_policy='never',
                    **capabilities(args.depth_estimation, args.reference_manifest_sha256, args.benchmark, getattr(args, 'tactile_mode', None), getattr(args, 'measured_depth', None)),
                    feedback_storage_version=FEEDBACK_FORMAT_VERSION,
                    tool_output_token_limit=DEFAULT_TOOL_OUTPUT_TOKEN_LIMIT)
    processes = []
    saved_handlers = {}
    failure = None
    simulator = agent = None
    event_log = None
    requested_signal = None

    def interrupted(signum, _frame):
        # Do not throw between spawning a child and registering its process group.
        nonlocal requested_signal
        requested_signal = requested_signal or signum

    def check_cancelled():
        if event_log is not None:
            event_log.check()
        if requested_signal is not None:
            raise Interrupted(requested_signal)

    with ExitStack() as stack:
        # Exclusive sidecar log reserves this invocation without pre-creating the
        # output directory, which the simulator itself must create exclusively.
        log = stack.enter_context(server_log.open('x', encoding='utf-8'))
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                saved_handlers[signum] = signal.signal(signum, interrupted)
            from environments.backends import get_backend
            spec = get_backend(args.benchmark).launch_spec(args)
            print(f'[Codex launcher] Starting simulation; log: {server_log}', flush=True)
            simulator = subprocess.Popen(spec['command'], cwd=spec['cwd'], env=spec['env'],
                                         stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True)
            processes.append(simulator)
            session = wait_ready(simulator, args, check_cancelled)
            metadata.update(episode_id=session['episode_id'], identity=session['identity'])
            metadata['native_control'] = session.get('native_control')
            if reference_enabled(args):
                manifest = load_manifest(output, args.reference_manifest_sha256)
                metadata['reference'] = {k: manifest[k] for k in
                                         ('format', 'modalities', 'camera_order', 'image_count')}
                metadata['reference'].update(mode=args.reference_mode, fps=args.reference_fps,
                                             output_token_limit=output_token_limit(output))
            else:
                metadata['reference'] = {'enabled': False}
            # Keep an exact byte-for-byte record of the string used in this invocation.
            (output / 'codex_prompt.md').write_bytes(prompt_bytes)
            write_json(output / 'codex_run.json', metadata)
            events = stack.enter_context((output / 'codex_events.jsonl').open('x', encoding='utf-8'))
            errors = stack.enter_context((output / 'codex_stderr.log').open('x', encoding='utf-8'))
            print('[Codex launcher] Session ready; starting Codex with developer instructions '
                  '(no sandbox; commands run with the launching user permissions).', flush=True)
            check_cancelled()
            agent = subprocess.Popen(codex_command(executable, args, prompt, session), cwd=args.output,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
                                     start_new_session=True)
            processes.append(agent)
            event_log = EventLog(agent.stdout, events, secrets=(session["token"],))
            monitor(simulator, agent, args, check_cancelled)
            check_cancelled()
        except LaunchError as exc:
            failure = exc
        except (OSError, ValueError) as exc:
            # Do not log command arguments, manifest contents or environment variables.
            failure = LaunchError(f'launcher I/O or configuration failure ({type(exc).__name__})')
        finally:
            if requested_signal is not None and failure is None:
                failure = Interrupted(requested_signal)
            for signum in saved_handlers:
                signal.signal(signum, signal.SIG_IGN)
            try:
                # Record original return codes, before cleanup might change them.
                metadata.update(simulator_exit=simulator.poll() if simulator else None,
                                codex_exit=agent.poll() if agent else None)
                stop_processes(processes)
                if event_log is not None:
                    try:
                        event_log.finish()
                    except LaunchError as exc:
                        failure = failure or exc
                if output.is_dir():
                    try:
                        from execution.metrics import write_report
                        report = write_report(output)
                        metadata['action_metrics'] = report['summary']
                    except Exception as exc:
                        metadata['action_metrics_error'] = type(exc).__name__
                metadata.update(finished_at=time.time(), complete=failure is None,
                                exit_code=failure.code if failure else 0,
                                stop_reason=str(failure) if failure else 'completed')
                destination = output / 'launcher.json' if output.is_dir() else fallback_status
                write_json(destination, metadata)
                log.flush()
                if output.is_dir() and not (output / 'server.log').exists():
                    server_log.replace(output / 'server.log')
            finally:
                for signum, handler in saved_handlers.items():
                    signal.signal(signum, handler)
    if failure:
        raise failure
    print(f'[Codex launcher] Evaluation complete; official result: {output / "result.json"}', flush=True)
    return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except LaunchError as exc:
        print(f'[Codex launcher] {exc}', file=sys.stderr)
        return exc.code
    except (OSError, UnicodeError) as exc:
        print(f'[Codex launcher] preflight/artifact failure ({type(exc).__name__})', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
