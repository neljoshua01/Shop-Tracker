"""Independent, read-only promotion-event observation for the purchase experiment.

The observer uses a separate browser page so post-trigger PDP refreshes never
navigate or reload the purchase/checkout page. Its only purpose is to collect
evidence about how the selected SKU and deep-discount price evolve during the
promotion experiment.

The observer owns its polling evidence path. It does not rely solely on the
shared BrowserEngine response-callback path because callback delivery can be
affected by session lifecycle and response-body timing. Each poll explicitly
reloads the independent PDP and waits for the matching get_pc response, then
parses that response into an observation even when there is no promotion event.
"""

import json
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from execution.browser.browser_connector import BrowserConnector
from purchase.parser.sku_price_parser import SkuPriceParser


class PromotionEventObserver:
    POLL_INTERVAL_SECONDS = 1.0
    POST_EVENT_BUFFER_SECONDS = 10.0
    MAX_DURATION_SECONDS = 120.0
    GET_PC_RESPONSE_TIMEOUT_MS = 10000
    GET_PC_REQUEST_TIMEOUT_MS = 10000

    def __init__(self, session, recorder):
        self.session = session
        self.recorder = recorder
        self.browser = BrowserConnector()
        self.parser = SkuPriceParser()
        self.owner = object()
        self.browser_session = None
        self.stop_event = threading.Event()
        self.started_event = threading.Event()
        self.finished_event = threading.Event()
        self.state_event = threading.Event()
        self.thread = None
        self.started_at = None
        self.finished_at = None
        self.live_seen_at = None
        self.ended_seen_at = None
        self.last_state = None
        self.state_history = []
        self.stop_requested = False
        self.termination_reason = None
        self._lock = threading.Lock()

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"PromotionForensics:{self.session.product.item_id}",
        )
        self.thread.start()

    def wait(self, timeout=None):
        if self.thread is None:
            return True
        self.finished_event.wait(timeout=timeout)
        return self.finished_event.is_set()

    def stop(self):
        self.stop_requested = True
        self.termination_reason = "manual_stop"
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=15)

    async def on_browser_response(self, response, response_body=None):
        """Compatibility callback path; direct polling is the primary path."""
        if "/api/v4/pdp/get_pc" not in response.url:
            return

        if response_body is None:
            return

        await self._process_response_body(response.url, response_body, "callback")

    async def _process_response_body(self, response_url, response_body, source):
        try:
            data = json.loads(response_body.decode("utf-8"))
        except Exception as exc:
            self.recorder.record_event(
                "promotion_observer_parse_failed",
                "post_trigger_observation",
                {
                    "source": source,
                    "error": repr(exc),
                },
            )
            return False

        state = self.parser.parse(
            data,
            model_id=self.session.variation.model_id,
        )

        if state is None:
            self.recorder.record_event(
                "promotion_observer_target_not_found",
                "post_trigger_observation",
                {
                    "source": source,
                    "item_id": self.session.product.item_id,
                    "model_id": self.session.variation.model_id,
                },
            )
            return False

        if state.item_id != self.session.product.item_id:
            return False

        if state.model_id != self.session.variation.model_id:
            return False

        now = datetime.now(timezone.utc).isoformat()

        observation = {
            "timestamp": now,
            "source": "independent_forensic_observer",
            "poll_source": source,
            "response_url": response_url,
            "item_id": state.item_id,
            "model_id": state.model_id,
            "sku": state.name,
            "price": state.price,
            "price_before_discount": state.price_before_discount,
            "promotion_detected": state.promotion_detected,
            "promotion_id": state.promotion_id,
            "promotion_types": state.promotion_types,
            "deep_discount": state.deep_discount,
            "promotion_price": state.promotion_price,
            "promotion_event_status": state.promotion_event_status,
            "promotion_seconds_until_start": state.promotion_seconds_until_start,
            "promotion_seconds_until_end": state.promotion_seconds_until_end,
            "promotion_reminder_event": state.promotion_reminder_event,
            "has_stock": state.has_stock,
        }

        with self._lock:
            self.last_state = observation
            self.state_history.append(observation)
            if len(self.state_history) > 300:
                self.state_history = self.state_history[-300:]

            if state.promotion_event_status == "LIVE" and self.live_seen_at is None:
                self.live_seen_at = time.monotonic()

            if state.promotion_event_status == "ENDED" and self.ended_seen_at is None:
                self.ended_seen_at = time.monotonic()

        self.recorder.record_event(
            "promotion_observer_state",
            "post_trigger_observation",
            observation,
        )
        self.state_event.set()
        return True

    def _api_url(self):
        return (
            "https://shopee.ph/api/v4/pdp/get_pc"
            f"?item_id={self.session.product.item_id}"
            f"&shop_id={self.session.product.shop_id}"
            "&tz_offset_in_minutes=480"
            "&detail_level=0"
            "&incoming_pdp_page_source=0"
            "&incoming_pdp_page_scenario=0"
        )

    def _poll_get_pc(self):
        """Reload the observer PDP and return the matching get_pc body.

        The operation is executed on the shared async runtime, but the
        observation is scoped to this observer's own BrowserSession. If the
        browser response body is unavailable, fall back to a read-only
        browser-context request using the same authenticated context.
        """

        page = self.browser_session.page
        api_url = self._api_url()
        runtime = self.browser.runtime

        async def _reload_and_capture():
            async def _capture():
                async with page.expect_response(
                    lambda response: (
                        "/api/v4/pdp/get_pc" in response.url
                        and f"item_id={self.session.product.item_id}" in response.url
                    ),
                    timeout=self.GET_PC_RESPONSE_TIMEOUT_MS,
                ) as response_info:
                    await page.reload(
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )

                response = await response_info.value
                body = await response.body()
                return response.url, body

            return await _capture()

        try:
            future = runtime.submit(_reload_and_capture())
            return future.result(
                timeout=(self.GET_PC_RESPONSE_TIMEOUT_MS / 1000) + 15,
            )
        except Exception as exc:
            self.recorder.record_event(
                "promotion_observer_reload_capture_failed",
                "post_trigger_observation",
                {
                    "error": repr(exc),
                },
            )

        async def _request_fallback():
            response = await page.context.request.get(
                api_url,
                timeout=self.GET_PC_REQUEST_TIMEOUT_MS,
            )
            body = await response.body()
            return response.url, body

        try:
            future = runtime.submit(_request_fallback())
            return future.result(
                timeout=(self.GET_PC_REQUEST_TIMEOUT_MS / 1000) + 5,
            )
        except Exception as exc:
            self.recorder.record_event(
                "promotion_observer_request_fallback_failed",
                "post_trigger_observation",
                {
                    "error": repr(exc),
                },
            )
            return None, None

    def _run(self):
        self.started_at = datetime.now(timezone.utc)
        self.recorder.record_event(
            "promotion_observer_started",
            "post_trigger_observation",
            {
                "poll_interval_seconds": self.POLL_INTERVAL_SECONDS,
                "post_event_buffer_seconds": self.POST_EVENT_BUFFER_SECONDS,
                "max_duration_seconds": self.MAX_DURATION_SECONDS,
                "polling_mode": "independent_pdp_reload",
            },
        )

        deadline = time.monotonic() + self.MAX_DURATION_SECONDS

        try:
            # Keep the callback registered for compatibility/diagnostics, but
            # do not depend on it for the observer's primary evidence stream.
            self.browser.engine.register_response_callback(
                self.owner,
                self.on_browser_response,
            )

            self.browser_session = self.browser.open_session(
                self.owner,
                self.session.request.reference.url,
            )
            self.started_event.set()

            post_event_deadline = None

            while not self.stop_event.is_set():
                now = time.monotonic()

                if now >= deadline:
                    self.termination_reason = "max_duration"
                    self.recorder.record_event(
                        "promotion_observer_max_duration",
                        "post_trigger_observation",
                    )
                    break

                response_url, body = self._poll_get_pc()

                if body is not None:
                    processed = self.browser.runtime.submit(
                        self._process_response_body(
                            response_url,
                            body,
                            "independent_pdp_reload",
                        )
                    ).result(timeout=15)

                    if not processed:
                        self.recorder.record_event(
                            "promotion_observer_poll_unprocessed",
                            "post_trigger_observation",
                            {
                                "response_url": response_url,
                            },
                        )
                else:
                    self.recorder.record_event(
                        "promotion_observer_poll_no_response",
                        "post_trigger_observation",
                    )

                with self._lock:
                    ended_seen_at = self.ended_seen_at

                if ended_seen_at is not None:
                    if post_event_deadline is None:
                        post_event_deadline = (
                            ended_seen_at + self.POST_EVENT_BUFFER_SECONDS
                        )
                    if time.monotonic() >= post_event_deadline:
                        self.termination_reason = "promotion_ended_plus_buffer"
                        break

                self.stop_event.wait(self.POLL_INTERVAL_SECONDS)

        except Exception as exc:
            self.termination_reason = "observer_exception"
            self.recorder.record_event(
                "promotion_observer_failed",
                "post_trigger_observation",
                {"error": repr(exc)},
            )
        finally:
            try:
                if self.browser_session is not None:
                    self.browser.engine.unregister_response_callback(
                        self.owner,
                        session=self.browser_session,
                    )
            except Exception:
                pass

            try:
                if self.browser_session is not None:
                    self.browser.close_session(self.owner)
            except Exception as exc:
                self.recorder.record_event(
                    "promotion_observer_close_failed",
                    "post_trigger_observation",
                    {"error": repr(exc)},
                )

            self.finished_at = datetime.now(timezone.utc)

            with self._lock:
                history = list(self.state_history)
                last_state = self.last_state

            if self.termination_reason is None:
                self.termination_reason = (
                    "manual_stop"
                    if self.stop_requested
                    else "observer_completed"
                )

            summary = {
                "schema_version": 2,
                "source": "independent_forensic_observer",
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "finished_at": self.finished_at.isoformat(),
                "live_seen": self.live_seen_at is not None,
                "ended_seen": self.ended_seen_at is not None,
                "stop_requested": self.stop_requested,
                "termination_reason": self.termination_reason,
                "observation_count": len(history),
                "last_state": last_state,
                "state_history": history,
                "observer_config": {
                    "poll_interval_seconds": self.POLL_INTERVAL_SECONDS,
                    "post_event_buffer_seconds": self.POST_EVENT_BUFFER_SECONDS,
                    "max_duration_seconds": self.MAX_DURATION_SECONDS,
                    "polling_mode": "independent_pdp_reload",
                    "get_pc_response_timeout_seconds": self.GET_PC_RESPONSE_TIMEOUT_MS / 1000,
                    "get_pc_request_fallback_timeout_seconds": self.GET_PC_REQUEST_TIMEOUT_MS / 1000,
                },
            }

            self.recorder.write_observation_summary(summary)
            self.recorder.record_event(
                "promotion_observer_finished",
                "post_trigger_observation",
                {
                    "observation_count": len(history),
                    "live_seen": self.live_seen_at is not None,
                    "ended_seen": self.ended_seen_at is not None,
                    "termination_reason": self.termination_reason,
                },
            )
            self.finished_event.set()
