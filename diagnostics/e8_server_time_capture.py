"""Read-only E8 server-time forensic capture.

This module records evidence from Shopee PDP get_pc responses without
participating in trigger, evaluation, checkout, or safety decisions.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path


TARGET_PATH = "/api/v4/pdp/get_pc"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_like_fields(value, path="$", results=None):
    if results is None:
        results = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if re.search(
                r"(time|timestamp|start|end|ctime|mtime|date|promotion|event)",
                str(key),
                re.IGNORECASE,
            ):
                results.append(
                    {
                        "path": child_path,
                        "key": str(key),
                        "value": child,
                    }
                )
            _timestamp_like_fields(child, child_path, results)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            _timestamp_like_fields(child, f"{path}[{index}]", results)

    return results


class E8ServerTimeCapture:
    """Passive run-scoped evidence collector for get_pc responses."""

    def __init__(self, output_path=None, max_responses=20):
        self.output_path = Path(
            output_path
            or Path("forensics") / "e8" / "server_time_capture.json"
        )
        self.max_responses = max_responses
        self.records = []
        self.started_at_utc = None

    @property
    def complete(self):
        return len(self.records) >= self.max_responses

    def should_capture(self, response):
        return TARGET_PATH in getattr(response, "url", "")

    async def capture(self, response, body=None):
        if self.complete or not self.should_capture(response):
            return

        if self.started_at_utc is None:
            self.started_at_utc = _utc_now()

        received_monotonic_ns = time.perf_counter_ns()

        try:
            headers = await response.all_headers()
        except Exception as exc:
            headers = {"__capture_error__": str(exc)}

        interesting_headers = {
            key.lower(): value
            for key, value in headers.items()
            if (
                key.lower() in {"date", "age", "server", "via"}
                or key.lower().startswith("x-cache")
                or "cdn" in key.lower()
                or "cache" in key.lower()
                or "time" in key.lower()
            )
        }

        body_error = None
        parsed_body = body

        if parsed_body is None:
            try:
                raw_body = await response.body()
                parsed_body = json.loads(raw_body.decode("utf-8"))
            except Exception as exc:
                body_error = str(exc)

        try:
            timing = dict(response.request.timing or {})
        except Exception as exc:
            timing = {"__timing_error__": str(exc)}

        record = {
            "capture_index": len(self.records) + 1,
            "captured_at_utc": _utc_now(),
            "local_received_monotonic_ns": received_monotonic_ns,
            "url": response.url,
            "status": response.status,
            "headers": headers,
            "interesting_headers": interesting_headers,
            "request": {
                "method": response.request.method,
                "url": response.request.url,
                "timing": timing,
            },
            "timestamp_like_fields": _timestamp_like_fields(parsed_body)
            if parsed_body is not None
            else [],
            "body": parsed_body,
            "body_error": body_error,
        }

        self.records.append(record)
        self._write()

    def _write(self):
        payload = {
            "schema_version": 1,
            "purpose": "E8 server-time evidence only",
            "target": TARGET_PATH,
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": _utc_now(),
            "responses_captured": len(self.records),
            "requested_responses": self.max_responses,
            "records": self.records,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
