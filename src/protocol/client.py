"""Internal, stdlib-only session client. No command-line interface or action retries."""

from contextlib import contextmanager
import fcntl
import json
import math
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from execution.artifacts import write_guard

_UNSET = object()


class ClientError(ValueError):
    """A local rejection: no new request was submitted."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Even a local endpoint must never forward its bearer token elsewhere.
        return None


class ControlClient:
    def __init__(self, session_file):
        self.session_file = Path(session_file).expanduser().resolve()
        try:
            manifest = json.loads(self.session_file.read_text())
            endpoint = urllib.parse.urlsplit(manifest["endpoint"])
            timeout = manifest["request_timeout"]
            valid = (
                manifest["protocol"] == "sim-codex-v1"
                and endpoint.scheme == "http"
                and endpoint.hostname == "127.0.0.1"
                and endpoint.port is not None
                and endpoint.path == "/control"
                and not endpoint.username
                and not endpoint.password
                and not endpoint.query
                and not endpoint.fragment
                and isinstance(manifest["token"], str)
                and bool(manifest["token"])
                and isinstance(manifest["episode_id"], str)
                and bool(manifest["episode_id"])
                and not isinstance(timeout, bool)
                and math.isfinite(timeout)
                and timeout > 0
                and Path(manifest["output_dir"]).resolve() == self.session_file.parent
            )
            if not valid:
                raise ValueError()
        except (OSError, ValueError, TypeError, KeyError):
            raise ClientError("invalid or unreadable session manifest") from None
        from protocol.contracts import validate_capabilities
        try:
            validate_capabilities(manifest)
        except ValueError as exc:
            raise ClientError(str(exc)) from None
        self.measured_depth = manifest["measured_depth"]
        self.depth_estimation = manifest["depth_estimation"]
        self.reference_enabled = manifest["reference_enabled"]
        self.reference_owner = uuid.uuid4().hex
        self.reference_failed = False
        self.manifest = manifest
        self.output = self.session_file.parent
        self.timeout = timeout + 10
        self.result_path = self.output / "result.json"
        self.uncertain_path = self.output / "client_uncertain.json"
        self.pending_path = self.output / "client_pending.json"
        self.delivery_path = self.output / "client_delivery_failed.json"
        self.reference_state_path = self.output / "reference_state.json"
        self.mutex = threading.Lock()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    @contextmanager
    def transaction(self):
        if not self.mutex.acquire(blocking=False):
            raise ClientError("another client command is in progress")
        try:
            with (self.output / ".client.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ClientError("another client command is in progress") from None
                yield
        finally:
            self.mutex.release()

    def _mutation_allowed(self):
        if self.result_path.exists():
            raise ClientError("episode ended; inspect status")
        if self.uncertain_path.exists() or self.pending_path.exists():
            raise ClientError("previous communication outcome unknown; inspect status only")
        if self.delivery_path.exists():
            raise ClientError("observation delivery failed; inspect status only")

    def call(
        self, op, *, observation_id=_UNSET, action=None, reason=None, depth_estimates=_UNSET,
        render=None, metrics=None, defer_confirmation=False, camera=None, pixels_uv=None
    ):
        """Hold guards through result/image construction; a crash never authorizes replay.

        render runs within the transaction. It must not submit requests or retry delivery.
        The MCP caller waits for this operation on cancellation, rather than abandoning it.
        """
        if op not in ("observe", "act", "status", "finish", "read_depth"):
            raise ClientError("unknown operation")
        mutation = op in ("act", "finish")
        payload = dict(op=op, episode_id=self.manifest["episode_id"])
        if op == 'read_depth':
            if not self.measured_depth or observation_id is _UNSET:
                raise ClientError('read_depth requires enabled measured depth and observation_id')
            payload.update(camera=camera, pixels_uv=pixels_uv)
        if op in ('observe', 'read_depth') and observation_id is not _UNSET:
            if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id < 0:
                raise ClientError("observation_id must be a nonnegative integer")
            payload["observation_id"] = observation_id
        if mutation:
            if isinstance(observation_id, bool) or not isinstance(observation_id, int):
                raise ClientError("observation_id must be an integer")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
                raise ClientError("reason must contain 1–4000 characters")
            payload.update(observation_id=observation_id, reason=reason, request_id=uuid.uuid4().hex)
        if op == "act":
            if not isinstance(action, dict):
                raise ClientError("action must be a structured object")
            payload["action"] = action
            if self.depth_estimation and depth_estimates is _UNSET:
                raise ClientError("depth_estimates required when depth estimation is enabled")
            if depth_estimates is not _UNSET:
                if not self.depth_estimation:
                    raise ClientError("depth_estimates disabled for this session")
                payload["depth_estimates"] = depth_estimates
        try:
            data = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError):
            raise ClientError("request must contain finite JSON values") from None
        if metrics is not None:
            metrics["request_id"] = payload.get("request_id")
        with self.transaction():
            if op == "status" and self.result_path.exists():
                result = json.loads(self.result_path.read_text())
                return render(result) if render else result
            if op != "status":
                # A failed/uncertain delivery permits status only, including after restart.
                self._mutation_allowed()
            if op == "act" and self.reference_enabled:
                state = self._reference_state()
                if (self.reference_failed or state["phase"] not in ("delivered", "acting")
                        or state.get("owner") != self.reference_owner):
                    raise ClientError("reference not delivered in this service; act is blocked")
            if mutation:
                if op == "act" and self.reference_enabled:
                    self._save_reference_state("acting")
                with (self.output / "client_requests.jsonl").open("a") as log:
                    log.write(json.dumps(dict(time=time.time(), request=payload)) + "\n")
                write_guard(self.pending_path, payload)
            request = urllib.request.Request(
                self.manifest["endpoint"],
                data=data,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.manifest["token"]},
            )
            start = time.monotonic()
            try:
                try:
                    with self.opener.open(request, timeout=self.timeout) as response:
                        result = json.load(response)
                except urllib.error.HTTPError as exc:
                    # Treat unparseable errors as unknown, not proof that nothing happened.
                    result = json.loads(exc.read())
                    if exc.code >= 500:
                        result["fatal"] = True
                if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
                    raise ValueError("invalid control response")
                if mutation and result.get("ok") is False and not result.get("no_execution"):
                    result["outcome_unknown"] = True
                if result.get("fatal") or result.get("outcome_unknown"):
                    write_guard(self.uncertain_path, dict(request=payload, response=result))
            except (OSError, ValueError, TypeError, urllib.error.URLError):
                # Never include exception text: transport exceptions may contain credentials.
                result = dict(
                    ok=False,
                    error="control communication failed",
                    outcome_unknown=mutation,
                    guidance="Do not replay. Inspect status and public logs only.",
                )
                if mutation:
                    write_guard(self.uncertain_path, dict(request=payload, response=result))
                if op == "status" and self.result_path.exists():
                    result = json.loads(self.result_path.read_text())
            finally:
                if metrics is not None:
                    metrics["http_seconds"] = time.monotonic() - start
            try:
                delivered = render(result) if render else result
            except Exception:
                # Motion may be confirmed, but no further action is safe without delivered RGB.
                write_guard(
                    self.delivery_path,
                    dict(op=op, request_id=payload.get("request_id"), error="observation delivery failed"),
                )
                raise ClientError("observation delivery failed; inspect status only") from None
            if mutation and not defer_confirmation and not self.uncertain_path.exists():
                self.pending_path.unlink()
            return delivered

    def confirm_delivery(self):
        """Commit only after the MCP task has checked for cancellation."""
        with self.transaction():
            if not self.uncertain_path.exists() and not self.delivery_path.exists():
                self.pending_path.unlink(missing_ok=True)

    def _reference_state(self):
        """All reference state access is under the shared client transaction."""
        if not self.reference_state_path.exists():
            return dict(episode_id=self.manifest["episode_id"], phase="unobserved")
        try:
            state = json.loads(self.reference_state_path.read_text())
            if (state["episode_id"] != self.manifest["episode_id"]
                    or state.get("reference_manifest_sha256") != self.manifest["reference_manifest_sha256"]
                    or state["phase"] not in
                    ("unobserved", "observed", "consumed", "delivered", "acting", "failed")):
                raise ValueError()
            return state
        except (OSError, ValueError, TypeError, KeyError):
            raise ClientError("invalid reference state; act is blocked") from None

    def _save_reference_state(self, phase, **extra):
        write_guard(self.reference_state_path, dict(episode_id=self.manifest["episode_id"],
                   reference_manifest_sha256=self.manifest["reference_manifest_sha256"],
                   owner=self.reference_owner, phase=phase, updated_at=time.time(), **extra))

    def confirm_reference_observation(self):
        if self.reference_enabled:
            with self.transaction():
                if self._reference_state()["phase"] in ("unobserved", "observed"):
                    self._save_reference_state("observed")

    def read_reference(self, *, render, metrics):
        if not self.reference_enabled or self.reference_failed:
            raise ClientError("references are disabled or delivery has failed")
        with self.transaction():
            self._mutation_allowed()
            state = self._reference_state()
            if state["phase"] != "observed" or state.get("owner") != self.reference_owner:
                raise ClientError("read_reference requires initial observe and is allowed only once before act")
            try:
                latest = json.loads((self.output / "latest.json").read_text())
                if (latest["episode_id"] != self.manifest["episode_id"] or
                        latest["observation_id"] != 0 or latest["episode_status"]["terminal"]):
                    raise ValueError()
            except (OSError, ValueError, KeyError, TypeError):
                raise ClientError("reference requires the live initial observation") from None
            # Consume BEFORE opening any reference content. Death/failed delivery can never reset the quota.
            metrics["reference_consumed"] = True
            self._save_reference_state("consumed")
            try:
                return render(metrics)
            except Exception:
                self._save_reference_state("failed", error="reference content delivery failed")
                write_guard(self.delivery_path, dict(op="read_reference", error="reference content delivery failed"))
                raise ClientError("reference content delivery failed; act is blocked") from None

    def confirm_reference_delivery(self):
        with self.transaction():
            state = self._reference_state()
            if (state["phase"] != "consumed" or state.get("owner") != self.reference_owner
                    or self.delivery_path.exists()):
                raise ClientError("reference delivery uncertain; act is blocked")
            self._save_reference_state("delivered")

    def fail_reference_delivery(self, error):
        # Block this service even when disk failure prevents persisting the failure.
        # A replacement service has a different owner and cannot reuse delivery permission.
        self.reference_failed = True
        try:
            with self.transaction():
                self._save_reference_state("failed", error=error)
        except (OSError, ClientError):
            pass
