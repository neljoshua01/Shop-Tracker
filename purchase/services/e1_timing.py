"""E1 timing instrumentation for the purchase monitoring/execution path.

E1 is observational only. It records timestamps and derives latency metrics;
it does not change trigger decisions, checkout behavior, or safety gates.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class E1TimingRecorder:
    """Record the E1 T0-T11 timing points for one PurchaseSession."""

    POINTS = (
        "T0", "T1", "T2", "T3", "T4", "T5",
        "T6", "T7", "T8", "T9", "T10", "T11",
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.started_at = None
        self.started_at_wallclock = None
        self.points: dict[str, int] = {}
        self.network: dict[str, object] = {}
        self.completed = False

    def start(self):
        self.reset()
        self.started_at = time.perf_counter_ns()
        self.started_at_wallclock = datetime.now(timezone.utc).isoformat()
        self.points["T0"] = self.started_at
        return self.started_at

    def mark(self, point: str) -> int:
        if point not in self.POINTS:
            raise ValueError(f"Unknown E1 timing point: {point}")
        timestamp = time.perf_counter_ns()
        self.points[point] = timestamp
        return timestamp

    def record_get_pc_network(self, request, callback_received_ns: int):
        """Record T1/T2 from Playwright resource timing.

        Playwright's responseEnd is final once the request has finished.
        """
        try:
            timing = dict(request.timing or {})
        except Exception:
            timing = {}

        # Playwright exposes startTime as an epoch-based request anchor.
        # The detailed Resource Timing fields requestStart, responseStart,
        # and responseEnd are offsets within that resource timing origin.
        # Therefore startTime must not be subtracted from responseEnd.
        request_start_ms = timing.get("requestStart")
        response_end_ms = timing.get("responseEnd")
        response_start_ms = timing.get("responseStart")

        if isinstance(request_start_ms, (int, float)) and request_start_ms >= 0:
            self.network["request_start_ms"] = float(request_start_ms)
            self.points["T1"] = int(request_start_ms * 1_000_000)

        if isinstance(response_end_ms, (int, float)) and response_end_ms >= 0:
            self.network["response_end_ms"] = float(response_end_ms)
            self.points["T2"] = int(response_end_ms * 1_000_000)

        if isinstance(response_start_ms, (int, float)) and response_start_ms >= 0:
            self.network["response_start_ms"] = float(response_start_ms)

        self.network.update({
            "url": getattr(request, "url", None),
            "method": getattr(request, "method", None),
            "timing": timing,
            "callback_received_ns": callback_received_ns,
            "timing_source": "playwright_request_timing",
            "clock_domains": {
                "request_start_response_end": "resource_timing_relative_ms",
                "playwright_startTime": "epoch_ms",
                "python_callback": "monotonic_ns",
            },
        })

    def metrics(self) -> dict[str, float | None]:
        def delta_ms(start: str, end: str):
            a = self.points.get(start)
            b = self.points.get(end)
            if a is None or b is None:
                return None
            return round((b - a) / 1_000_000, 3)

        return {
            "network_latency_ms": (
                round(
                    self.network["response_end_ms"] - self.network["request_start_ms"],
                    3,
                )
                if self.network.get("request_start_ms") is not None
                and self.network.get("response_end_ms") is not None
                else None
            ),
            "browser_observation_latency_ms": None,
            "parsing_latency_ms": delta_ms("T4", "T5"),
            "trigger_processing_latency_ms": delta_ms("T5", "T7"),
            "evaluator_latency_ms": delta_ms("T6", "T7"),
            "trigger_to_checkout_start_ms": delta_ms("T7", "T8"),
            "cart_resolution_ms": delta_ms("T8", "T9"),
            "cart_to_checkout_ms": delta_ms("T10", "T11"),
            "trigger_to_checkout_ms": delta_ms("T7", "T11"),
        }

    def snapshot(self) -> dict:
        timestamps = {
            point: (
                datetime.fromtimestamp(timestamp / 1_000_000_000, timezone.utc).isoformat()
                if timestamp is not None
                else None
            )
            for point, timestamp in self.points.items()
        }
        return {
            "schema_version": 1,
            "started_at": self.started_at_wallclock,
            "points": dict(self.points),
            "timestamps_utc": timestamps,
            "network": dict(self.network),
            "metrics_ms": self.metrics(),
            "completed": self.completed,
        }

    def finalize(self, output_path: str | Path | None = None) -> dict:
        self.completed = True
        result = self.snapshot()

        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(result, indent=2, default=str),
                encoding="utf-8",
            )

        return result
