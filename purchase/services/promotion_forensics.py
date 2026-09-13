"""Persistent forensic capture for promotional purchase runs."""

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
        self.run_dir = Path("runtime/logs/promotion_forensics") / f"{stamp}_item-{item_id}_model-{model_id}"
        self.api_dir = self.run_dir / "api"
        self.page_dir = self.run_dir / "pages"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.page_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(self.run_dir / "run_manifest.json", {
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
                "place_order_is_not_clicked_by_checkout_executor": True,
            },
        })
        self.record_event("forensics_started", "startup", {
            "item_id": item_id,
            "model_id": model_id,
        })

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

    def attach_engine(self, engine, browser_session):
        if self._callback_registered:
            return
        self.browser_session = browser_session
        self._engine_ref = engine
        engine.register_response_callback(self, self.on_browser_response, session=browser_session)
        self._callback_registered = True
        self.record_event("forensics_attached", "monitoring", {
            "page_url": browser_session.page.url,
        })

    async def on_browser_response(self, response):
        if not self._is_relevant(response.url):
            return

        sequence = self._next_sequence()
        timestamp = datetime.now(timezone.utc).isoformat()
        url = response.url
        endpoint = self._endpoint(url)
        phase = self._phase_for_endpoint(endpoint)
        base = {
            "event": "api_response",
            "sequence": sequence,
            "timestamp": timestamp,
            "phase": phase,
            "endpoint": endpoint,
            "url": url,
            "method": response.request.method,
            "status": response.status,
            "resource_type": response.request.resource_type,
        }

        try:
            headers = response.headers
            base["content_type"] = headers.get("content-type", "")
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
            text = body.decode("utf-8", errors="replace")
            raw_path = self.api_dir / f"{sequence:06d}_{phase}_{endpoint}.txt"
            self._write_text(raw_path, text)
            base["body_file"] = str(raw_path.relative_to(self.run_dir))
            base["body_format"] = "text"
            base["body_bytes"] = len(body)

        self._append_event(base)

    def record_event(self, event, phase, data=None):
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
        }
        if data:
            payload.update(data)
        self._append_event(payload)

    def record_phase(self, phase, page):
        """Schedule a page text/HTML snapshot on the Playwright runtime."""
        try:
            from core.runtime.async_runtime import AsyncRuntime
            future = AsyncRuntime.instance().submit(self._capture_page(phase, page))
            future.add_done_callback(self._snapshot_callback)
        except Exception as exc:
            self.record_event("page_snapshot_schedule_failed", phase, {"error": repr(exc)})

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
            self.record_event("page_snapshot_failed", "snapshot", {"error": repr(exc)})

    def stop(self):
        if self._callback_registered and self.browser_session is not None:
            try:
                self._engine_ref.unregister_response_callback(self, session=self.browser_session)
            except Exception as exc:
                self.record_event("forensics_unregister_warning", "final", {"error": repr(exc)})
            self._callback_registered = False

        finished_at = datetime.now(timezone.utc)
        self.record_event("forensics_stopped", "final", {
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - self.started_at).total_seconds(), 3),
        })
        self._write_json(self.run_dir / "final_summary.json", {
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - self.started_at).total_seconds(), 3),
            "event_log": "events.jsonl",
            "api_directory": "api",
            "page_directory": "pages",
        })

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
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

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
                    if "price" in key_lower or "promotion" in key_lower or "discount" in key_lower or key_lower in {"stock", "has_stock", "allocated_stock"}:
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
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        return "".join(char if char in allowed else "_" for char in str(value))[:120]
