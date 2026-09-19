"""E1 baseline timing instrumentation.

Measurement-only utility for the controlled V2 baseline experiment.
It records monotonic process timestamps for end-to-end pipeline stages and
browser Performance API timestamps for the get_pc request/response pair.
It does not participate in trigger or execution decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid


class E1TimingRecorder:
    """Record the E1 T0-T11 timing points for one purchase session."""

    EVENT_ORDER = (
        "T0", "T1", "T2", "T3", "T4", "T5",
        "T6", "T7", "T8", "T9", "T10", "T11",
    )

    def __init__(self):
        self.run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        self.events = {}
        self.context = {}

    def set_context(self, **values):
        self.context.update(values)

    def record(self, name: str, *, monotonic: float | None = None, **metadata):
        """Record a process-monotonic event exactly once."""
        now_monotonic = time.perf_counter() if monotonic is None else monotonic
        self.events[name] = {
            "name": name,
            "monotonic": now_monotonic,
            "utc": datetime.now(timezone.utc).isoformat(),
            "source": "python_monotonic",
            **metadata,
        }
        print(
            f"[E1] {name} "
            f"utc={self.events[name]['utc']} "
            f"monotonic={now_monotonic:.9f}"
        )

    def record_browser_timing(
        self,
        name: str,
        *,
        performance_time_origin_ms: float,
        performance_ms: float,
        metadata: dict | None = None,
    ):
        """Record a browser Performance API timestamp."""
        if name in self.events:
            return

        epoch_ms = performance_time_origin_ms + performance_ms
        event = {
            "name": name,
            "browser_performance_ms": performance_ms,
            "browser_time_origin_ms": performance_time_origin_ms,
            "browser_epoch_ms": epoch_ms,
            "utc": datetime.fromtimestamp(
                epoch_ms / 1000.0,
                tz=timezone.utc,
            ).isoformat(),
            "source": "browser_performance",
        }
        if metadata:
            event.update(metadata)

        self.events[name] = event
        print(
            f"[E1] {name} "
            f"utc={event['utc']} "
            f"browser_ms={performance_ms:.3f}"
        )

    def has(self, name: str) -> bool:
        return name in self.events

    def durations(self) -> dict:
        """Return E1 duration metrics where compatible timestamps exist."""
        metrics = {}

        def python_delta(start: str, end: str, key: str):
            if start not in self.events or end not in self.events:
                return
            a = self.events[start].get("monotonic")
            b = self.events[end].get("monotonic")
            if a is None or b is None:
                return
            metrics[key] = round((b - a) * 1000.0, 3)

        def browser_delta(start: str, end: str, key: str):
            if start not in self.events or end not in self.events:
                return
            a = self.events[start].get("browser_epoch_ms")
            b = self.events[end].get("browser_epoch_ms")
            if a is None or b is None:
                return
            metrics[key] = round(b - a, 3)

        browser_delta("T1", "T2", "network_latency_ms")
        python_delta("T2", "T3", "response_to_callback_ms")
        python_delta("T4", "T5", "parse_to_state_ms")
        python_delta("T5", "T6", "state_to_trigger_eval_start_ms")
        python_delta("T6", "T7", "trigger_evaluation_ms")
        python_delta("T7", "T8", "trigger_to_checkout_start_ms")
        python_delta("T8", "T9", "checkout_start_to_cart_resolved_ms")
        python_delta("T9", "T10", "cart_resolved_to_checkout_click_ms")
        python_delta("T10", "T11", "checkout_click_to_checkout_reached_ms")
        python_delta("T7", "T11", "trigger_to_checkout_reached_ms")
        python_delta("T0", "T7", "monitor_start_to_trigger_ms")
        python_delta("T0", "T11", "monitor_start_to_checkout_reached_ms")

        return metrics

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "context": dict(self.context),
            "events": dict(self.events),
            "durations_ms": self.durations(),
            "missing_events": [
                name for name in self.EVENT_ORDER if name not in self.events
            ],
        }

    def finalize(self, *, output_root: str = "runtime/logs/e1_timing"):
        """Persist one immutable E1 run artifact."""
        payload = self.summary()
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)

        path = root / f"{self.run_id}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        print()
        print("[E1] ========== BASELINE TIMING SUMMARY ==========")
        for key, value in payload["durations_ms"].items():
            print(f"[E1] {key}: {value:.3f} ms")
        if payload["missing_events"]:
            print("[E1] Missing timing points: " + ", ".join(payload["missing_events"]))
        else:
            print("[E1] All T0-T11 timing points captured.")
        print(f"[E1] Run artifact: {path}")
        print("[E1] ===============================================")
        return path
