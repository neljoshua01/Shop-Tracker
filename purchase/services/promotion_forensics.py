"""Persistent forensic capture for promotional purchase runs.

The recorder preserves the raw API evidence needed to reconstruct a
promotional event without changing purchase decisions or safety behavior.
It is intentionally scoped to one PurchaseSession and writes only to the
runtime logs directory, which is already excluded from source control.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class PromotionForensicsRecorder:
    """Capture relevant Shopee API responses and phase snapshots for a run."""

    RELEVANT_PATHS = (
        "/api/v4/pdp/get_pc",
        "/api/v4/pdp/cart_panel/select_variation",
        "/api/v4/cart/",
        "/api/v4/checkout",
        "/api/v4/order/",
        "/api/v4/payment/",
        "/api/v4/transaction/",
    )

    _active = {}
    _registry_lock = threading.Lock()

    def __init__(self, session):
        self.session = session
        self.browser_session = None
        self._engine_ref = None
        self._callback_registered = False
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        self._file_lock = threading.Lock()
        self.started_at = datetime.now(timezone.utc)

        item_id = session.product.item_id
        model_id = session.variation.model_id
        stamp = self.started_at.strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
        self.run_dir = (
            Path("runtime/logs/promotion_forensics")
            / f"{stamp}_item-{item_id}_model-{model_id}"
        )
        self.api_dir = self.run_dir / "api"
        self.page_dir = self.run_dir / "pages"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.page_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(
            self.run_dir / "run_manifest.json",
            {
                "schema_version": 1,
                "started_at": self.started_at.isoformat(),
                "item_id": item_id,
                "model_id": model_id,
                "product_name": session.product.product_name,
                "requested_variations": dict(session.request.options),
                "quantity": session.request.quantity,
                "target_price": session.request.target_price,
                "polling_interval": session.request.polling_interval,
                "auto_checkout": session.request.auto_checkout,
                "promotional_url": session.request.reference.url,
                "safety": {
                    "payment_selection_not_recorded_as_an_action": True,
                    "place_order_is_not_clicked_by_checkout_executor": True,
                },
            },
        )
        self._append_event(
            {
                "event": "forensics_started",
                "phase": "startup",
                "item_id": item_id,
                "model_id": model_id,
            }
        )

    @classmethod
    def start(cls, session):
        key = id(session)
        with cls._registry_lock:
            existing = cls._active.get(key)
            if existing is not None:
                return existing
            recorder = cls(session)
            cls._active[key] = recorder
            return recorder

    @classmethod
    def get(cls, session):
        with cls._registry_lock:
            return cls._active.get(id(session))

    @classmethod
    def stop(cls, session):
        key = id(session)
        with cls._registry_lock:
            recorder = cls._active.pop(key, None)
        if recorder is not None:
            recorder.stop()
        return recorder

    def attach(self, browser_session):
        """Attach to an already-created BrowserSession."""
        self.attach_engine(self._engine_ref or self._default_engine(), browser_session)

    def attach_engine(self, engine, browser_session=None):
        """Register before or after session creation.

        When no BrowserSession exists yet, the BrowserEngine owner callback is
        registered first. BrowserEngine will bind that callback automatically
        when the PurchaseSession opens its page. This is required so the
        recorder can observe Add-to-Cart and cart responses, not only later
        monitoring responses.
        """
        if self._callback_registered:
            if browser_session is not None:
                self.browser_session = browser_session
            return

        self._engine_ref = engine
        self.browser_session = browser_session
        engine.register_response_callback(
            self,
            self.on_browser_response,
            session=browser_session,
            all_sessions=True,
        )
        self._callback_registered = True
        self._append_event(
            {
                "event": "forensics_attached",
                "phase": "startup" if browser_session is None else "monitoring",
                "page_url": getattr(getattr(browser_session, "page", None), "url", None),
                "session_bound": browser_session is not None,
            }
        )

    def bind_session(self, browser_session):
        """Associate the recorder with the session created after pre-registration."""
        self.browser_session = browser_session
        self._append_event(
            {
                "event": "forensics_session_bound",
                "phase": "cart",
                "page_url": browser_session.page.url,
            }
        )

    def record_event(self, event, phase, details=None):
        """Record a structured lifecycle or promotion observation event."""
        payload = {
            "event": event,
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if details:
            payload.update(details)
        self._append_event(payload)

    async def on_browser_response(self, response):
        if not self._is_relevant(response.url):
            return

        sequence = self._next_sequence()
        timestamp = datetime.now(timezone.utc).isoformat()
        url = response.url
        endpoint = self._endpoint(url)
        phase = self._phase_for_endpoint(endpoint)
        request = response.request
        base = {
            "sequence": sequence,
            "timestamp": timestamp,
            "phase": phase,
            "endpoint": endpoint,
            "url": url,
            "method": request.method,
            "status": response.status,
            "resource_type": request.resource_type,
        }

        # E5 captures the request-side transaction context as well as the
        # response. This is required to determine whether promotion identity
        # survives the PDP -> cart -> checkout transition. Request bodies are
        # redacted before persistence because checkout/payment endpoints may
        # contain sensitive values.
        try:
            request_body = request.post_data
        except Exception:
            request_body = None

        if request_body:
            request_payload, request_format = self._parse_request_body(request_body)
            base["request_body_format"] = request_format
            base["request_body_bytes"] = len(request_body.encode("utf-8", errors="replace"))
            if request_payload is not None:
                request_path = self.api_dir / f"{sequence:06d}_{phase}_{endpoint}_request.json"
                self._write_json(request_path, request_payload)
                base["request_body_file"] = str(request_path.relative_to(self.run_dir))
                base["target_request_observations"] = self._extract_target_observations(
                    request_payload
                )
            else:
                request_path = self.api_dir / f"{sequence:06d}_{phase}_{endpoint}_request.txt"
                self._write_text(request_path, request_body)
                base["request_body_file"] = str(request_path.relative_to(self.run_dir))

        try:
            headers = response.headers
            content_type = headers.get("content-type", "")
            base["content_type"] = content_type
            base["content_length"] = headers.get("content-length")
        except Exception:
            base["content_type"] = None
            base["content_length"] = None

        try:
            body = await response.body()
        except Exception as exc:
            base["body_error"] = repr(exc)
            self._append_event(base)
            return

        # Do not depend on Content-Type to decide whether the response is
        # JSON. Shopee responses can still be JSON when that header is absent
        # or inconsistent. This makes raw forensic capture more reliable.
        parsed = None
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            parsed = None

        if parsed is not None:
            raw_path = self.api_dir / f"{sequence:06d}_{phase}_{endpoint}.json"
            self._write_json(raw_path, parsed)
            base["body_file"] = str(raw_path.relative_to(self.run_dir))
            base["body_format"] = "json"
            base["body_bytes"] = len(body)
            base["target_observations"] = self._extract_target_observations(parsed)
        else:
            try:
                text = body.decode("utf-8", errors="replace")
            except Exception:
                text = repr(body)
            raw_path = self.api_dir / f"{sequence:06d}_{phase}_{endpoint}.txt"
            self._write_text(raw_path, text)
            base["body_file"] = str(raw_path.relative_to(self.run_dir))
            base["body_format"] = "text"
            base["body_bytes"] = len(body)

        self._append_event(base)

    def record_phase(self, phase, page):
        """Schedule a page text/HTML snapshot on the Playwright runtime."""
        try:
            from core.runtime.async_runtime import AsyncRuntime

            future = AsyncRuntime.instance().submit(
                self._capture_page(phase, page)
            )
            future.add_done_callback(self._snapshot_callback)
        except Exception as exc:
            self._append_event(
                {
                    "event": "page_snapshot_schedule_failed",
                    "phase": phase,
                    "error": repr(exc),
                }
            )

    async def _capture_page(self, phase, page):
        timestamp = datetime.now(timezone.utc).isoformat()
        safe_phase = self._safe_name(phase)
        text_path = self.page_dir / f"{safe_phase}.txt"
        html_path = self.page_dir / f"{safe_phase}.html"

        try:
            text = await page.locator("body").inner_text()
        except Exception as exc:
            text = f"PAGE TEXT CAPTURE ERROR: {exc!r}"

        try:
            html = await page.content()
        except Exception as exc:
            html = f"PAGE HTML CAPTURE ERROR: {exc!r}"

        self._write_text(text_path, text)
        self._write_text(html_path, html)

        event = {
            "event": "page_snapshot",
            "timestamp": timestamp,
            "phase": phase,
            "page_url": page.url,
            "text_file": str(text_path.relative_to(self.run_dir)),
            "html_file": str(html_path.relative_to(self.run_dir)),
        }
        self._append_event(event)
        return event

    def _snapshot_callback(self, future):
        try:
            future.result()
        except Exception as exc:
            self._append_event(
                {
                    "event": "page_snapshot_failed",
                    "error": repr(exc),
                }
            )

    def stop(self):
        """Finalize capture without allowing one cleanup step to block the summary."""
        finished_at = datetime.now(timezone.utc)
        duration_seconds = round(
            (finished_at - self.started_at).total_seconds(),
            3,
        )
        warnings = []

        # Finalization is deliberately best-effort and isolated step-by-step.
        # A failed callback unregister, event append, directory scan, or other
        # cleanup operation must not prevent final_summary.json from being
        # written for an otherwise normally completed pipeline run.
        if self._callback_registered and self._engine_ref is not None:
            try:
                self._engine_ref.unregister_response_callback(
                    self,
                    session=self.browser_session,
                    all_sessions=True,
                )
            except Exception as exc:
                warnings.append(
                    {
                        "step": "unregister_response_callback",
                        "error": repr(exc),
                    }
                )
            finally:
                self._callback_registered = False

        try:
            self._append_event(
                {
                    "event": "forensics_stopped",
                    "phase": "final",
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": duration_seconds,
                }
            )
        except Exception as exc:
            warnings.append(
                {
                    "step": "append_forensics_stopped",
                    "error": repr(exc),
                }
            )

        event_count = 0
        try:
            event_path = self.run_dir / "events.jsonl"
            if event_path.exists():
                event_count = sum(
                    1
                    for _ in event_path.open("r", encoding="utf-8")
                )
        except Exception as exc:
            warnings.append(
                {
                    "step": "count_events",
                    "error": repr(exc),
                }
            )

        api_files = 0
        try:
            api_files = len(list(self.api_dir.iterdir()))
        except Exception as exc:
            warnings.append(
                {
                    "step": "count_api_files",
                    "error": repr(exc),
                }
            )

        page_files = 0
        try:
            page_files = len(list(self.page_dir.iterdir()))
        except Exception as exc:
            warnings.append(
                {
                    "step": "count_page_files",
                    "error": repr(exc),
                }
            )

        summary = {
            "schema_version": 1,
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration_seconds,
            "event_log": "events.jsonl",
            "api_directory": "api",
            "page_directory": "pages",
            "event_count": event_count,
            "api_file_count": api_files,
            "page_file_count": page_files,
            "finalization_status": "completed_with_warnings" if warnings else "completed",
        }
        if warnings:
            summary["finalization_warnings"] = warnings

        # This write is intentionally the final operation and is independent
        # of all earlier cleanup/counting steps. A failure in an earlier
        # finalization step therefore cannot suppress the summary.
        try:
            self._write_json(
                self.run_dir / "final_summary.json",
                summary,
            )
        except Exception as exc:
            # There is no reliable way to guarantee a filesystem write if the
            # runtime itself is terminating, but preserve the warning whenever
            # the event log remains writable.
            try:
                self._append_event(
                    {
                        "event": "forensics_finalization_warning",
                        "phase": "final",
                        "error": repr(exc),
                        "step": "write_final_summary",
                    }
                )
            except Exception:
                pass

    @classmethod
    def _parse_request_body(cls, body):
        try:
            parsed = json.loads(body)
        except Exception:
            return None, "text"
        return cls._redact_sensitive(parsed), "json"

    @classmethod
    def _redact_sensitive(cls, node):
        sensitive = {
            "password", "passwd", "pwd", "cvv", "cvc", "security_code",
            "card_number", "cardnumber", "card_no", "account_number",
            "authorization", "access_token", "refresh_token", "secret",
        }
        if isinstance(node, dict):
            return {
                str(key): (
                    "<redacted>"
                    if str(key).lower().replace("-", "_") in sensitive
                    else cls._redact_sensitive(value)
                )
                for key, value in node.items()
            }
        if isinstance(node, list):
            return [cls._redact_sensitive(value) for value in node]
        return node

    def _default_engine(self):
        from execution.browser.browser_connector import BrowserConnector

        return BrowserConnector().engine

    def _is_relevant(self, url):
        low = url.lower()
        return any(path in low for path in self.RELEVANT_PATHS)

    @staticmethod
    def _endpoint(url):
        try:
            from urllib.parse import urlparse

            path = urlparse(url).path.strip("/").replace("/", "_")
            return PromotionForensicsRecorder._safe_name(path[-80:])
        except Exception:
            return "unknown_endpoint"

    @staticmethod
    def _phase_for_endpoint(endpoint):
        if "pdp_get_pc" in endpoint:
            return "pdp_get_pc"
        if "cart" in endpoint:
            return "cart"
        if "checkout" in endpoint:
            return "checkout"
        if "order" in endpoint or "payment" in endpoint or "transaction" in endpoint:
            return "order_payment"
        return "api"

    def _next_sequence(self):
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    def _append_event(self, event):
        path = self.run_dir / "events.jsonl"
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with self._file_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def _write_json(self, path, data):
        with self._file_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

    def _write_text(self, path, text):
        with self._file_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def _extract_target_observations(self, node, path="root", out=None):
        if out is None:
            out = []
        item_id = str(self.session.product.item_id)
        model_id = str(self.session.variation.model_id)

        if isinstance(node, dict):
            normalized = {str(k).lower(): v for k, v in node.items()}
            item = normalized.get("item_id", normalized.get("itemid"))
            model = normalized.get("model_id", normalized.get("modelid"))
            if str(item) == item_id or str(model) == model_id:
                record = {
                    "path": path,
                    "item_id": item,
                    "model_id": model,
                    "name": normalized.get("name") or normalized.get("model_name") or normalized.get("item_name"),
                }
                for key, value in normalized.items():
                    key_lower = str(key).lower()
                    if (
                        "price" in key_lower
                        or "promotion" in key_lower
                        or "discount" in key_lower
                        or key_lower in {"stock", "has_stock", "allocated_stock"}
                    ):
                        record[key_lower] = value
                out.append(record)
            for key, value in node.items():
                self._extract_target_observations(value, f"{path}.{key}", out)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._extract_target_observations(value, f"{path}[{index}]", out)
        return out

    @staticmethod
    def _safe_name(value):
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-." )
        return "".join(char if char in allowed else "_" for char in str(value))[:120]
