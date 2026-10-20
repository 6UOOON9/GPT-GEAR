"""STDIO registration, serialized calls and delivery guards for one episode.

Tool schemas and call adapters live in protocol.tools. This entrypoint never
imports simulation libraries or starts a model.
"""

from __future__ import annotations

import argparse
from functools import partial
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

BOOT_STARTED = time.monotonic()

if sys.version_info < (3, 11):
    raise RuntimeError("MCP requires an independent Python 3.11+ interpreter")

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# Allow absolute-path launch with an independent tool interpreter and arbitrary cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol.client import ClientError, ControlClient
from execution.artifacts import write_guard
from execution.metrics import arguments_hash
from protocol.tools import enabled_tools, tool_definitions
from protocol.tools import read_reference
from protocol.tools.rendering import text


SDK_VERSION = "1.29.1"


class EpisodeTools:
    def __init__(self, client):
        self.client = client
        self.busy = False
        self.calls = 0
        self.tools = enabled_tools(client.reference_enabled, client.measured_depth)
        if client.reference_enabled:
            read_reference.check_cache(client)
        self.server = Server("sim")
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)
        self.record(
            dict(
                event="service_started",
                pid=os.getpid(),
                depth_estimation=client.depth_estimation, reference_enabled=client.reference_enabled,
                sdk_version=importlib.metadata.version("mcp"),
                startup_seconds=time.monotonic() - BOOT_STARTED,
            )
        )

    def record(self, event):
        with (self.client.output / "mcp_metrics.jsonl").open("a") as log:
            log.write(json.dumps(dict(time=time.time(), **event), allow_nan=False) + "\n")
            log.flush()
            os.fsync(log.fileno())

    async def list_tools(self):
        return tool_definitions(
            reference=self.client.reference_enabled,
            depth_estimation=self.client.depth_estimation,
            profile=self.client.manifest["control_profile"],
            measured_depth=self.client.measured_depth,
        )

    async def call_tool(self, name, arguments):
        if name not in self.tools:
            return types.CallToolResult(content=[text(dict(ok=False, error="unknown tool"))], isError=True)
        if self.busy:
            return types.CallToolResult(
                content=[text(dict(ok=False, error="another client command is in progress"))], isError=True
            )
        self.busy = True
        self.calls += 1
        start = time.monotonic()
        metrics = dict(
            event="tool_call",
            tool=name,
            call=self.calls,
            observation_id=arguments.get("observation_id") if isinstance(arguments, dict) else None,
            http_seconds=0.0,
            image_seconds=0.0,
            image_count=0,
            image_bytes=0,
        )
        recorded = False
        try:
            metrics["arguments_sha256"] = arguments_hash(arguments)
            # Shield the transaction from cancellation. Process death leaves the disk guard in place.
            with anyio.CancelScope(shield=True):
                operation = partial(self.tools[name].call, self.client, arguments, metrics)
                result = await anyio.to_thread.run_sync(operation)
            # The HTTP worker must finish, but a cancelled caller has not received
            # its observation. Leave its durable guard until this checkpoint passes.
            await anyio.lowlevel.checkpoint()
            metrics["ok"] = not result.isError
            metrics["tool_seconds"] = time.monotonic() - start
            # Audit must reach disk BEFORE removing the durable pending guard.
            self.record(metrics)
            recorded = True
            if name in ("act", "finish"):
                self.client.confirm_delivery()
            if not result.isError:
                if name == read_reference.NAME:
                    self.client.confirm_reference_delivery()
                elif name == "observe" and metrics.get("initial_observation"):
                    self.client.confirm_reference_observation()
            return result
        except anyio.get_cancelled_exc_class():
            metrics["ok"] = False
            metrics["error"] = "tool response cancelled"
            if metrics.get("reference_consumed"):
                self.client.fail_reference_delivery(metrics["error"])
            write_guard(self.client.delivery_path, dict(op=name, error="tool response cancelled"))
            raise
        except ClientError as exc:
            metrics["ok"] = False
            metrics["error"] = str(exc)
            if metrics.get("reference_consumed"):
                self.client.fail_reference_delivery(metrics["error"])
            return types.CallToolResult(content=[text(dict(ok=False, error=str(exc)))], isError=True)
        except Exception as exc:
            metrics["ok"] = False
            metrics["error"] = "internal tool failure: " + type(exc).__name__
            if metrics.get("reference_consumed"):
                self.client.fail_reference_delivery(metrics["error"])
            return types.CallToolResult(
                content=[text(dict(ok=False, error="internal tool failure; inspect status only"))], isError=True
            )
        finally:
            metrics["tool_seconds"] = time.monotonic() - start
            try:
                if not recorded:
                    self.record(metrics)
                elif not metrics.get("ok"):
                    self.record(dict(event="tool_delivery_failed", tool=name, call=self.calls,
                                     error=metrics.get("error", "delivery failed")))
            except OSError:
                # Pending remains for mutations; block even read-side delivery failures.
                write_guard(self.client.delivery_path, dict(error="MCP metrics persistence failed"))
                print("MCP metrics write failed; mutations blocked", file=sys.stderr)
            finally:
                self.busy = False

    async def run(self):
        async with stdio_server() as (read, write):
            await self.server.run(read, write, self.server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--session", type=Path)
    parser.add_argument("--reference", action="store_true", help="Include the optional tool in --check")
    parser.add_argument(
        "--check", action="store_true", help="Validate the isolated tool environment without connecting"
    )
    from perception.depth import boolean_string
    parser.add_argument("--depth-estimation", type=boolean_string, default=None)
    parser.add_argument("--measured-depth", type=boolean_string, default=False)
    if any(arg.split("=", 1)[0] == "--demonstration" for arg in sys.argv[1:]):
        parser.error("--demonstration has been removed; use --reference")
    args = parser.parse_args()
    if importlib.metadata.version("mcp") != SDK_VERSION:
        parser.error(f"install the pinned tool dependency mcp=={SDK_VERSION}")
    if args.check:
        # Exercise lazy async backend imports in the exact absolute-script
        # invocation used by Codex, before starting the expensive simulator.
        async def check_backend():
            await anyio.sleep(0)
        anyio.run(check_backend)
        print(json.dumps(dict(mcp_version=SDK_VERSION,
                              tools=list(enabled_tools(args.reference, args.measured_depth)),
                              depth_estimation=True if args.depth_estimation is None else args.depth_estimation)))
        return
    if args.session is None:
        parser.error("--session is required")
    client = ControlClient(args.session)
    if args.depth_estimation is not None and args.depth_estimation != client.depth_estimation:
        parser.error("explicit depth-estimation disagrees with session capabilities")
    if args.reference:
        parser.error("--reference is only for --check; runtime reference configuration comes from the session")
    tools = EpisodeTools(client)
    anyio.run(tools.run)


if __name__ == "__main__":
    main()
