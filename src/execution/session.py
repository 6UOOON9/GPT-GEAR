"""Single-owner local control session. Only run() touches the simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import queue
import secrets
import threading
import time
import uuid

import numpy as np
from PIL import Image

from perception.calibration import EpisodeCalibration
from protocol.contracts import capabilities
from control.controller import ControlCancelled, DeltaController
from perception.depth import validate_estimates
from protocol.feedback import compact_feedback
from demonstrations.cache import load_manifest
from execution.artifacts import write_json


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


@dataclass
class Pending:
    payload: dict
    done: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    response: dict | None = None


class NativeClient:
    """Local servo interface; no network, policy or model calls."""
    def __init__(self, native):
        self.native = native
        self.uncertain = False

    def status(self):
        return self.native.status()

    def observe(self):
        return self.native.observe()

    def execute(self, commands):
        if (not isinstance(commands, list) or not 1 <= len(commands) <= len(self.native.control_profile["arms"])
                or len({command.get('arm') for command in commands if isinstance(command, dict)}) != len(commands)):
            raise ValueError('servo executes one atomic increment for one or two distinct arms')
        before = self.status()['action_count']
        try:
            result = self.native.execute(commands)
            self.native.ended()
            return dict(result, executed_actions=self.status()['action_count'] - before,
                        status=self.status(), robot_state=self.observe()['robot_state'])
        except Exception:
            self.uncertain = True
            raise


class Session:
    def __init__(self, native, output, *, port=8092, connect_timeout=600.,
                 idle_timeout=600., request_timeout=600., depth_estimation=True, reference_manifest_sha256=None):
        for value in (connect_timeout, idle_timeout, request_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('timeouts must be finite and positive')
        self.capabilities = capabilities(depth_estimation, reference_manifest_sha256, native.benchmark, getattr(native, 'tactile_mode', None), getattr(native, 'measured_depth', None))
        self.depth_estimation = depth_estimation
        self.measured_depth = self.capabilities['measured_depth']
        self.reference_manifest_sha256 = reference_manifest_sha256
        self.execution_started = False
        self.native = native
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        if (self.output / 'session.json').exists():
            raise ValueError('refusing to reuse a previous session output')
        if reference_manifest_sha256 is not None:
            manifest = load_manifest(self.output, reference_manifest_sha256)
            if manifest["benchmark"] != native.benchmark:
                raise ValueError("reference benchmark mismatch")
        self.episode_id = uuid.uuid4().hex
        self.token = secrets.token_urlsafe(32)
        self.port = port
        self.connect_timeout, self.idle_timeout = connect_timeout, idle_timeout
        self.request_timeout = request_timeout
        self.pending = queue.Queue(maxsize=16)
        self.cancelled = threading.Event()
        self.closed = False
        self.requests = {}
        self.version = -1
        self.latest = None
        self.reason = None
        self.calibration = EpisodeCalibration()
        self.client = NativeClient(native)
        self.controller = DeltaController(self.client, self.check_cancelled)
        self.server = None
        self.owner = None

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise ControlCancelled('request timed out or session cancelled; do not replay')

    def record(self, event):
        with (self.output / 'history.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(dict(time=time.time(), **event), default=json_default, allow_nan=False) + '\n')

    def snapshot(self):
        raw = self.native.observe()
        specs = self.calibration.view_specs(raw)
        self.version += 1
        directory = self.output / 'observations' / f'{self.version:06d}'
        directory.mkdir(parents=True, exist_ok=False)
        images = {}
        depth_views = {}
        for index, (name, view) in enumerate(raw['views'].items()):
            # Camera names never become filesystem paths.
            path = directory / f'camera_{index}.png'
            Image.fromarray(view['rgb']).save(path)
            images[name] = str(path)
            if self.measured_depth:
                depth = np.asarray(view['depth_m'], dtype=np.float32)
                if depth.shape != view['rgb'].shape[:2] or not np.isfinite(depth).all() or np.any(depth <= 0):
                    raise ValueError('invalid RGB-aligned metric depth')
                depth_path = directory / f'depth_{index}.npy'
                np.save(depth_path, depth, allow_pickle=False)
                depth_views[name] = dict(shape=list(depth.shape), unit='m',
                    convention='positive optical-axis Z; visible surface at the same RGB pixel',
                    access_tool='read_depth', sha256=hashlib.sha256(depth_path.read_bytes()).hexdigest())
        state = dict(episode_id=self.episode_id, observation_id=self.version,
                     captured_at=raw.get('captured_at', time.time()),
                     task_language=raw['instruction'], images=images, view_specs=specs,
                     robot_state=raw['robot_state'], episode_status=self.native.status())
        if self.measured_depth:
            state['depth_views'] = depth_views
        profile = self.capabilities['observation_profile']
        if 'tactile_mode' in profile:
            from perception.modalities import validate_force
            state['tactile_mode'] = profile['tactile_mode']
            if profile['tactile_images']:
                state['tactile_specs'] = {}
                for index, name in enumerate(profile['tactile_images']):
                    rgb = raw['tactile_images'][name]
                    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
                        raise ValueError('invalid tactile RGB')
                    path = directory / f'tactile_{index}.png'
                    Image.fromarray(rgb).save(path)
                    images[name] = str(path)
                    state['tactile_specs'][name] = dict(shape=list(rgb.shape[:2]), signal='native_tactile_rgb')
            if profile['contact_forces']:
                state['contact_forces'] = {name: validate_force(raw['contact_forces'][name])
                                           for name in profile['contact_forces']}
        from perception.modalities import validate_observation
        validate_observation(state, profile)
        # Construct from an allowlist; raw camera metadata and private paths stay private.
        write_json(directory / 'state.json', state, default=json_default)
        self.latest = dict(state, state_path=str(directory / 'state.json'))
        write_json(self.output / 'latest.json', self.latest, default=json_default)
        self.record(dict(event='observation', observation_id=self.version,
                         state_path=self.latest['state_path']))
        return self.latest

    def read_observation(self, observation_id):
        """Read public records without capturing or advancing the current version."""
        if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id < 0:
            raise ValueError('observation_id must be a nonnegative integer')
        if self.latest is None or observation_id > self.version:
            raise ValueError('observation not found')
        directory = self.output / 'observations' / f'{observation_id:06d}'
        path = directory / 'state.json'
        # Reject symlinked directories/files before reading public history.
        if directory.resolve() != directory or path.resolve() != path:
            raise ValueError('invalid observation path')
        if observation_id == self.version:
            observation = self.latest
        else:
            if not path.is_file():
                raise ValueError('observation not found')
            observation = dict(json.loads(path.read_text(encoding='utf-8')), state_path=str(path))
        if (observation.get('episode_id') != self.episode_id
                or type(observation.get('observation_id')) is not int
                or observation['observation_id'] != observation_id):
            raise ValueError('invalid observation identity')

        from perception.modalities import validate_observation
        validate_observation(observation, self.capabilities['observation_profile'])

        preceding_action = None
        requests = {}
        history_path = self.output / 'history.jsonl'
        if history_path.resolve() != history_path:
            raise ValueError('invalid history path')
        with history_path.open(encoding='utf-8') as history:
            for line in history:
                event = json.loads(line)
                if event.get('event') == 'request':
                    request = event['request']
                    requests[request['request_id']] = request
                elif event.get('event') == 'response':
                    response = event['response']
                    request = requests.get(event['request_id'])
                    if (response.get('ok') is True
                            and response.get('observation', {}).get('observation_id') == observation_id
                            and request is not None and request.get('op') == 'act'
                            and request.get('episode_id') == self.episode_id
                            and response['observation'].get('episode_id') == self.episode_id):
                        preceding_action = {key: request[key] for key in
                                            ('request_id', 'observation_id', 'action', 'reason')}
                        preceding_action['feedback'] = compact_feedback(response.get('feedback'))
                        if 'depth_estimates' in request:
                            preceding_action['depth_estimates'] = request['depth_estimates']
                        break
        return dict(ok=True, observation=observation, latest_observation_id=self.version,
                    is_latest=observation_id == self.version, preceding_action=preceding_action)

    def dispatch(self, payload):
        if threading.get_ident() != self.owner:
            raise RuntimeError('simulation calls must run on the owner thread')
        if not isinstance(payload, dict):
            raise ValueError('request must be an object')
        op = payload.get('op')
        if op not in ('observe', 'act', 'status', 'finish', 'read_depth'):
            raise ValueError('unknown operation')
        if payload.get('episode_id') != self.episode_id:
            raise ValueError('stale episode')
        if op == 'status':
            return dict(ok=True, observation=self.latest, stop_reason=self.reason)
        if op == 'read_depth':
            from perception.measured_depth import read_depth
            return read_depth(self, payload.get('observation_id'), payload.get('camera'), payload.get('pixels_uv'))
        if op == 'observe':
            return self.read_observation(payload.get('observation_id', self.version))
        request_id = payload.get('request_id')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            raise ValueError('mutation requires a nonempty request_id of at most 128 characters')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if request_id in self.requests:
            previous_digest, response = self.requests[request_id]
            if previous_digest != digest:
                raise ValueError('request_id reused with different content')
            return response
        self.check_cancelled()
        if payload.get('observation_id') != self.version or isinstance(payload.get('observation_id'), bool):
            raise ValueError('stale observation; inspect the latest observation before acting')
        if self.native.status()['terminal']:
            raise ValueError('episode is terminal')
        reason = payload.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
            raise ValueError('a brief visible-evidence/action reason is required (1–4000 characters)')
        if op == 'act':
            action = payload.get('action')
            if not isinstance(action, dict):
                raise ValueError('action must be an object')
            # All argument validation occurs before the controller submits native motion.
            self.controller.validate_action(**action)
            if self.depth_estimation:
                validate_estimates(payload.get('depth_estimates'), self.latest)
            elif 'depth_estimates' in payload:
                raise ValueError('depth_estimates disabled for this session')
            if self.reference_manifest_sha256 is not None:
                try:
                    state = json.loads((self.output / 'reference_state.json').read_text())
                    if (state['episode_id'] != self.episode_id
                            or state['reference_manifest_sha256'] != self.reference_manifest_sha256
                            or state['phase'] not in ('delivered', 'acting')):
                        raise ValueError()
                except (OSError, KeyError, TypeError, ValueError):
                    raise ValueError('reference not delivered; act is blocked') from None
            # All validation is complete; persist intent BEFORE submitting motion.
            self.record(dict(event='request', request=payload))
            started = time.monotonic()
            self.execution_started = True
            try:
                feedback = self.controller.act_delta(**action)
                after_action = getattr(self.native, 'after_policy_action', None)
                if after_action is not None:
                    self.reason = after_action() or self.reason
                self.record(dict(event='execution', request_id=request_id,
                                 execution_seconds=time.monotonic() - started, feedback=feedback))
            except Exception as exc:
                raise RuntimeError(f'controller runtime failed: {exc}') from exc
            if feedback.get('stop_reason') in ('runtime_failure', 'outcome_unknown', 'cancelled'):
                self.reason = feedback['stop_reason']
                self.cancelled.set()
            try:
                response = dict(ok=True, feedback=feedback, observation=self.snapshot())
                if feedback.get('stop_reason') in ('runtime_failure', 'outcome_unknown', 'cancelled'):
                    response.update(fatal=True, outcome_unknown=bool(feedback.get('outcome_unknown')))
            except Exception as exc:
                raise RuntimeError(f'post-action observation failed: {exc}') from exc
        else:
            self.record(dict(event='request', request=payload))
            self.execution_started = True
            self.reason = 'codex_finish: ' + reason
            try:
                self.native.finalize()
                response = dict(ok=True, observation=self.snapshot(), stop_reason=self.reason)
            except Exception as exc:
                raise RuntimeError(f'finalization failed: {exc}') from exc
        self.requests[request_id] = (digest, response)
        self.record(dict(event='response', request_id=request_id, response=response))
        return response

    def start_http(self):
        session = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                code, response = 200, None
                try:
                    if self.path != '/control' or not secrets.compare_digest(
                            self.headers.get('Authorization', ''), 'Bearer ' + session.token):
                        self.send_error(403)
                        return
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 65536:
                        raise ValueError('JSON request body must be 1–65536 bytes')
                    payload = json.loads(self.rfile.read(length),
                                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                    request = Pending(payload)
                    session.pending.put_nowait(request)
                    if not request.done.wait(session.request_timeout):
                        request.cancelled.set()
                        session.cancelled.set()
                        code, response = 504, dict(ok=False, error='outcome_unknown; no replay', fatal=True)
                    else:
                        response = request.response
                except (ValueError, TypeError, queue.Full) as exc:
                    code, response = 400, dict(ok=False, error=str(exc), no_execution=True)
                body = json.dumps(response, default=json_default, allow_nan=False).encode()
                try:
                    self.send_response(code)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    # The recorded request/result remains authoritative; never replay.
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        manifest = dict(protocol='sim-codex-v1', episode_id=self.episode_id,
                        endpoint=f'http://127.0.0.1:{self.server.server_port}/control', token=self.token,
                        output_dir=str(self.output), identity=self.native.identity,
                        request_timeout=self.request_timeout,
                        native_control=self.native.control_metadata(), **self.capabilities)
        write_json(self.output / 'session.json', manifest, default=json_default)
        (self.output / 'session.json').chmod(0o600)
        print(f'[Codex] ready: {self.output / "session.json"}', flush=True)

    def run(self):
        self.owner = threading.get_ident()
        connected = False
        progress = time.monotonic()
        try:
            self.snapshot()
            self.start_http()
            while not self.native.status()['terminal'] and not self.cancelled.is_set():
                limit = self.idle_timeout if connected else self.connect_timeout
                if time.monotonic() - progress >= limit:
                    self.reason = 'idle_timeout' if connected else 'connect_timeout'
                    break
                try:
                    request = self.pending.get(timeout=min(.2, limit))
                except queue.Empty:
                    continue
                if request.cancelled.is_set():
                    continue
                before = self.native.status()['action_count']
                self.execution_started = False
                try:
                    request.response = self.dispatch(request.payload)
                    if not connected:
                        connected, progress = True, time.monotonic()
                    if self.native.status()['action_count'] > before:
                        progress = time.monotonic()
                except (ValueError, TypeError) as exc:
                    request.response = dict(ok=False, error=str(exc), no_execution=not self.execution_started)
                    if self.execution_started:
                        self.reason = 'runtime_failure: post-submission validation error'
                        self.cancelled.set()
                        request.response.update(fatal=True, outcome_unknown=True)
                except Exception as exc:
                    self.reason = f'runtime_failure: {type(exc).__name__}: {exc}'
                    self.cancelled.set()
                    request.response = dict(ok=False, error=self.reason, fatal=True)
                finally:
                    request.done.set()
            status = self.native.status()
            ending = ('native_success' if status.get('success') else
                      'task_early_stop' if status.get('task_early_stop') else
                      'budget_exhausted' if status.get('remaining_steps') == 0 else 'native_terminal')
            if self.native.benchmark not in ('robocasa-gr1', 'univtac', 'robotwin'):
                ending = 'native_terminal'
            self.reason = self.reason or ('cancelled' if self.cancelled.is_set() else ending)
            if self.client.uncertain or (self.reason or '').startswith(('runtime_failure', 'outcome_unknown')):
                raise RuntimeError(self.reason)
            self.native.finalize()
        except Exception as exc:
            self.reason = f'runtime_failure: {type(exc).__name__}: {exc}'
            raise
        finally:
            self.close()

    def complete(self, eval_result=None):
        result = self.native.result(eval_result)
        if self.reason in ('idle_timeout', 'connect_timeout', 'cancelled') or (self.reason or '').startswith(('runtime_failure', 'outcome_unknown')):
            result.update(complete=False, valid_for_success_rate=False)
        write_json(self.output / 'result.json', dict(
            result, format='sim-result-v1', benchmark=self.native.benchmark,
            identity=self.native.identity, episode_id=self.episode_id,
            stop_reason=self.reason, episode_status=self.native.status()), default=json_default)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        while True:
            try:
                request = self.pending.get_nowait()
            except queue.Empty:
                break
            request.response = dict(ok=False, error='session ended; read result.json', fatal=True)
            request.done.set()
