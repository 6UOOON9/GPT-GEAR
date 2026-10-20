"""Shared MCP text and observation images, including delivery-time validation."""
import base64
import json
from pathlib import Path
import time
import zlib

from mcp import types

from protocol.feedback import FEEDBACK_FORMAT_VERSION, model_visible_result


def text(value):
    return types.TextContent(type="text", text=json.dumps(value, ensure_ascii=False, allow_nan=False))


def validate_png(raw):
    """Reject truncated/corrupted files before presenting them as delivered images."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG signature")
    offset = 8
    chunks = []
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset : offset + 4], "big")
        end = offset + 8 + size
        if end + 4 > len(raw):
            raise ValueError("truncated PNG chunk")
        kind = raw[offset + 4 : offset + 8]
        checksum = int.from_bytes(raw[end : end + 4], "big")
        if zlib.crc32(raw[offset + 4 : end]) != checksum:
            raise ValueError("corrupted PNG chunk")
        chunks.append(kind)
        offset = end + 4
        if kind == b"IEND":
            if size != 0 or offset != len(raw) or chunks[0] != b"IHDR" or b"IDAT" not in chunks:
                raise ValueError("invalid PNG layout")
            return
    raise ValueError("incomplete PNG")


def render_result(client, op, result, metrics):
    start = time.monotonic()
    # Enforce the model-facing allowlist without mutating stored host records.
    projected = model_visible_result(result)
    state_text = text(projected)
    metrics.update(feedback_format_version=FEEDBACK_FORMAT_VERSION,
                   result_text_bytes_before=len(text(result).text.encode("utf-8")),
                   result_text_bytes_after=len(state_text.text.encode("utf-8")))
    content = [state_text]
    observation = result.get("observation")
    count = size = 0
    if op in ("observe", "act", "finish") and result.get("ok") and observation is None:
        raise ValueError("missing observation")
    if op != "status" and result.get("ok") and observation is not None:
        if observation["episode_id"] != client.manifest["episode_id"]:
            raise ValueError("observation from another episode")
        version = observation["observation_id"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError("invalid observation identity")
        expected = client.output / "observations" / f"{version:06d}"
        if expected.resolve() != expected or not expected.is_dir():
            raise ValueError("invalid observation directory")
        images = observation["images"]
        if not isinstance(images, dict) or not images:
            raise ValueError("missing RGB views")
        from perception.modalities import validate_observation
        specs = validate_observation(observation, client.manifest['observation_profile'])
        for name, filename in images.items():
            path = Path(filename).resolve(strict=True)
            if not path.is_relative_to(expected) or path.suffix != ".png":
                raise ValueError("image outside current observation")
            raw = path.read_bytes()
            validate_png(raw)
            width = int.from_bytes(raw[16:20], "big")
            height = int.from_bytes(raw[20:24], "big")
            if specs[name].get("shape") != [height, width]:
                raise ValueError("RGB size disagrees with calibration")
            content.extend(
                [
                    text(dict(camera=name, observation_id=version)),
                    types.ImageContent(
                        type="image", mimeType="image/png", data=base64.b64encode(raw).decode("ascii")
                    ),
                ]
            )
            count += 1
            size += len(raw)
    if op == "observe" and result.get("ok") and observation is not None:
        metrics["initial_observation"] = observation["observation_id"] == 0 and result.get("is_latest") is True
    metrics.update(image_seconds=time.monotonic() - start, image_count=count, image_bytes=size)
    return types.CallToolResult(
        content=content,
        isError=(result.get("ok") is False or bool(result.get("fatal") or result.get("outcome_unknown"))),
    )
