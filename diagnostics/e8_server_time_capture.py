"""E8 server-time synchronization and evidence capture.

E8 is observational: it derives a bounded server-time estimate from
Shopee HTTP Date metadata and response timing, records uncertainty, and
compares that estimate with Shopee event timestamps found in get_pc.

It does not participate in trigger, evaluation, checkout, or safety
decisions.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


TARGET_PATH = "/api/v4/pdp/get_pc"
HTTP_DATE_RESOLUTION_MS = 1000.0


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


def _parse_http_date(value):
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


class ShopeeTimeSynchronizer:
    """Run-scoped, uncertainty-aware estimate of Shopee server time.

    HTTP Date is treated as a synchronization signal, not as proven
    authoritative promotion-event time. The estimate is anchored to a
    local monotonic clock so later wall-clock adjustments do not change
    the synchronized time unexpectedly.
    """

    def __init__(self):
        self.offset_seconds = None
        self.uncertainty_ms = None
        self.last_sync_monotonic = None
        self.last_sync_wall = None
        self.last_measurement = None

    def update_from_response(
        self,
        server_date_timestamp,
        request_sent_wall,
        response_received_wall,
        request_sent_monotonic,
        response_received_monotonic,
    ):
        if server_date_timestamp is None:
            return None

        rtt_seconds = max(
            0.0,
            response_received_monotonic - request_sent_monotonic,
        )
        local_midpoint = (request_sent_wall + response_received_wall) / 2.0

        # Offset is server Date minus the local midpoint of the request.
        # This avoids treating the response-receive instant as the server
        # observation instant.
        offset_seconds = server_date_timestamp - local_midpoint

        # HTTP Date has one-second resolution. The half-second quantization
        # uncertainty is combined with half the measured RTT.
        uncertainty_ms = (
            (HTTP_DATE_RESOLUTION_MS / 2.0)
            + (rtt_seconds * 1000.0 / 2.0)
        )

        self.offset_seconds = offset_seconds
        self.uncertainty_ms = uncertainty_ms
        self.last_sync_monotonic = response_received_monotonic
        self.last_sync_wall = response_received_wall
        self.last_measurement = {
            "server_date_timestamp": server_date_timestamp,
            "request_sent_wall": request_sent_wall,
            "response_received_wall": response_received_wall,
            "request_sent_monotonic": request_sent_monotonic,
            "response_received_monotonic": response_received_monotonic,
            "rtt_ms": rtt_seconds * 1000.0,
            "local_midpoint": local_midpoint,
            "offset_ms": offset_seconds * 1000.0,
            "uncertainty_ms": uncertainty_ms,
        }
        return self.last_measurement

    def current_time(self):
        """Return estimated Shopee Unix time and current uncertainty."""
        if self.offset_seconds is None or self.last_sync_monotonic is None:
            return None

        now_monotonic = time.perf_counter()
        elapsed_since_sync = max(
            0.0,
            now_monotonic - self.last_sync_monotonic,
        )
        estimated_time = (
            self.last_sync_wall
            + elapsed_since_sync
            + self.offset_seconds
        )
        return {
            "timestamp": estimated_time,
            "uncertainty_ms": self.uncertainty_ms,
            "age_ms": elapsed_since_sync * 1000.0,
        }


class E8ServerTimeCapture:
    """Server-time synchronization and evidence collector for get_pc."""

    def __init__(self, output_path=None, max_responses=20):
        self.output_path = Path(
            output_path
            or Path("forensics") / "e8" / "server_time_capture.json"
        )
        self.max_responses = max_responses
        self.records = []
        self.started_at_utc = None
        self.synchronizer = ShopeeTimeSynchronizer()

    @property
    def complete(self):
        return len(self.records) >= self.max_responses

    def should_capture(self, response):
        return TARGET_PATH in getattr(response, "url", "")

    @staticmethod
    def _request_timing_absolute(response, captured_wall):
        try:
            timing = dict(response.request.timing or {})
        except Exception:
            return None

        start_time = timing.get("startTime")
        request_start = timing.get("requestStart")
        response_end = timing.get("responseEnd")

        if not all(
            isinstance(value, (int, float))
            for value in (start_time, request_start, response_end)
        ):
            return None

        # Playwright's Resource Timing startTime is an epoch-based
        # millisecond value in the captured get_pc evidence. Preserve the
        # source values and derive wall-clock request/response boundaries.
        request_sent_wall = (start_time + request_start) / 1000.0
        response_received_wall = (start_time + response_end) / 1000.0

        # Fall back to the actual capture instant if the resource timing
        # appears to be in a different clock domain.
        if response_received_wall <= 0 or response_received_wall > captured_wall + 60:
            return None

        request_sent_monotonic = time.perf_counter() - max(
            0.0,
            captured_wall - request_sent_wall,
        )
        response_received_monotonic = time.perf_counter()

        return {
            "request_sent_wall": request_sent_wall,
            "response_received_wall": response_received_wall,
            "request_sent_monotonic": request_sent_monotonic,
            "response_received_monotonic": response_received_monotonic,
            "timing_source": "playwright_resource_timing",
        }

    async def capture(self, response, body=None):
        if self.complete or not self.should_capture(response):
            return

        if self.started_at_utc is None:
            self.started_at_utc = _utc_now()

        captured_wall = time.time()
        captured_monotonic = time.perf_counter()

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

        server_date_value = headers.get("date") or headers.get("Date")
        server_date_timestamp = _parse_http_date(server_date_value)

        timing_bounds = self._request_timing_absolute(
            response,
            captured_wall,
        )

        sync_measurement = None
        if timing_bounds is not None:
            sync_measurement = self.synchronizer.update_from_response(
                server_date_timestamp=server_date_timestamp,
                request_sent_wall=timing_bounds["request_sent_wall"],
                response_received_wall=timing_bounds["response_received_wall"],
                request_sent_monotonic=timing_bounds["request_sent_monotonic"],
                response_received_monotonic=timing_bounds[
                    "response_received_monotonic"
                ],
            )

        current_sync = self.synchronizer.current_time()

        record = {
            "capture_index": len(self.records) + 1,
            "captured_at_utc": _utc_now(),
            "local_wall_time_unix": captured_wall,
            "local_received_monotonic": captured_monotonic,
            "url": response.url,
            "status": response.status,
            "headers": headers,
            "interesting_headers": interesting_headers,
            "request": {
                "method": response.request.method,
                "url": response.request.url,
                "timing": timing,
            },
            "server_time_sync": {
                "http_date": server_date_value,
                "http_date_unix": server_date_timestamp,
                "measurement": sync_measurement,
                "current_estimate": current_sync,
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
            "schema_version": 2,
            "purpose": "E8 server-time synchronization evidence",
            "target": TARGET_PATH,
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": _utc_now(),
            "responses_captured": len(self.records),
            "requested_responses": self.max_responses,
            "synchronization": {
                "source": "HTTP Date header + Playwright response timing",
                "authoritative_event_clock_proven": False,
                "current_offset_ms": (
                    self.synchronizer.offset_seconds * 1000.0
                    if self.synchronizer.offset_seconds is not None
                    else None
                ),
                "current_uncertainty_ms": self.synchronizer.uncertainty_ms,
            },
            "records": self.records,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
