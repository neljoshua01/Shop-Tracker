"""
Step 7E: observe the browser lifecycle after Place Order is clicked.

This service deliberately does not interact with OTP, payment, or any
post-order page. It keeps the existing browser session alive, records
main-frame URL transitions, classifies known states, and waits for a
conservative purchase-completion/receipt signal.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlsplit, parse_qsl


@dataclass(slots=True)
class PostOrderNavigation:
    """One observed post-order navigation/state sample."""

    sequence: int
    timestamp: float
    url: str
    safe_url: str
    host: str
    path: str
    state: str
    title: str = ""
    text_excerpt: str = ""


@dataclass(slots=True)
class PostOrderTrackingResult:
    """Final state returned by Step 7E."""

    completed: bool
    timed_out: bool
    stopped: bool
    elapsed_seconds: float
    navigations: list[PostOrderNavigation] = field(default_factory=list)


class PostOrderTracker:
    """
    Observe what happens after an authorized Place Order click.

    The tracker is intentionally passive:
      - no OTP interaction
      - no payment interaction
      - no clicks
      - no redirects initiated by the tracker
      - no attempt to bypass Shopee verification

    The existing BrowserSession/Page remains the source of truth.
    """

    DEFAULT_TIMEOUT_SECONDS = 1800
    POLL_INTERVAL_SECONDS = 0.5
    BODY_INSPECTION_INTERVAL_SECONDS = 1.5
    MAX_TEXT_EXCERPT = 800

    def __init__(self, timeout_seconds: Optional[float] = None):
        if timeout_seconds is None:
            raw_timeout = os.getenv("SHOPEE_POST_ORDER_TIMEOUT_SECONDS")
            if raw_timeout:
                try:
                    timeout_seconds = float(raw_timeout)
                except ValueError:
                    timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS
            else:
                timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS

        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._page: Any = None
        self._listener = None
        self._started = False
        self._start_time: Optional[float] = None
        self._last_url: Optional[str] = None
        self._last_body_inspection = 0.0
        self._navigations: list[PostOrderNavigation] = []
        self._completed = False
        self._listener_removed = False

    @property
    def navigations(self) -> list[PostOrderNavigation]:
        with self._lock:
            return list(self._navigations)

    def start(self, page: Any) -> None:
        """
        Arm navigation observation on the existing page.

        This should be called immediately before the Place Order click so
        an extremely fast redirect cannot be missed.
        """
        if self._started:
            raise RuntimeError("PostOrderTracker has already been started.")

        self._page = page
        self._start_time = time.monotonic()
        self._started = True

        def on_frame_navigated(frame: Any) -> None:
            try:
                if frame != page.main_frame:
                    return
            except Exception:
                return

            try:
                self._record_current_page(reason="navigation")
            except Exception as exc:
                print(f"[PostOrderTracker] Navigation capture warning: {exc}")

        self._listener = on_frame_navigated
        page.on("framenavigated", on_frame_navigated)

        # Capture the page immediately before the irreversible click. This
        # establishes the baseline without treating it as a post-order state.
        self._last_url = page.url

        print("[PostOrderTracker] Armed on existing browser session.")
        print("[PostOrderTracker] Waiting for post-Place-Order navigation...")

    def wait(self) -> PostOrderTrackingResult:
        """Passively wait for completion, timeout, or browser/session stop."""
        if not self._started or self._page is None or self._start_time is None:
            raise RuntimeError("PostOrderTracker.start() must be called first.")

        try:
            while not self._stop_event.is_set():
                elapsed = time.monotonic() - self._start_time
                if elapsed >= self.timeout_seconds:
                    print(
                        "[PostOrderTracker] Tracking timeout reached; "
                        "browser session will remain untouched."
                    )
                    break

                try:
                    if self._page.is_closed():
                        print("[PostOrderTracker] Browser page closed; stopping tracker.")
                        break
                except Exception:
                    break

                # URL polling supplements framenavigated so client-side history
                # changes are still observed even when no frame event is emitted.
                try:
                    current_url = self._page.url
                except Exception:
                    current_url = self._last_url

                if current_url and current_url != self._last_url:
                    self._record_current_page(reason="url-change")

                now = time.monotonic()
                if now - self._last_body_inspection >= self.BODY_INSPECTION_INTERVAL_SECONDS:
                    self._last_body_inspection = now
                    self._inspect_current_state()

                if self._completed:
                    break

                try:
                    self._page.wait_for_timeout(int(self.POLL_INTERVAL_SECONDS * 1000))
                except Exception:
                    time.sleep(self.POLL_INTERVAL_SECONDS)
        finally:
            self._remove_listener()

        elapsed = time.monotonic() - self._start_time
        timed_out = not self._completed and not self._stop_event.is_set() and elapsed >= self.timeout_seconds
        stopped = self._stop_event.is_set()

        return PostOrderTrackingResult(
            completed=self._completed,
            timed_out=timed_out,
            stopped=stopped,
            elapsed_seconds=elapsed,
            navigations=self.navigations,
        )

    def stop(self) -> None:
        """Stop observation without closing or navigating the browser."""
        self._stop_event.set()
        self._remove_listener()
        print("[PostOrderTracker] Tracking stopped.")

    def _remove_listener(self) -> None:
        if self._listener_removed:
            return
        if self._page is None or self._listener is None:
            self._listener_removed = True
            return

        try:
            self._page.remove_listener("framenavigated", self._listener)
        except Exception:
            pass
        finally:
            self._listener_removed = True

    def _record_current_page(self, reason: str) -> None:
        if self._page is None:
            return

        url = self._page.url
        if not url or (url == self._last_url and self._navigations):
            return

        self._last_url = url
        self._record_page(url, reason=reason)

    def _record_page(self, url: str, reason: str) -> None:
        parsed = urlsplit(url)
        host = parsed.netloc.lower()
        path = parsed.path or "/"

        title = self._safe_title()
        text = self._safe_body_text()
        state = self._classify_state(host, path, title, text)

        navigation = PostOrderNavigation(
            sequence=len(self._navigations) + 1,
            timestamp=time.time(),
            url=url,
            safe_url=self._safe_url(url),
            host=host,
            path=path,
            state=state,
            title=title,
            text_excerpt=text[: self.MAX_TEXT_EXCERPT],
        )

        with self._lock:
            self._navigations.append(navigation)

        print()
        print(f"[PostOrderTracker] ---------- NAVIGATION #{navigation.sequence} ----------")
        print(f"[PostOrderTracker] Reason: {reason}")
        print(f"[PostOrderTracker] URL: {navigation.safe_url}")
        print(f"[PostOrderTracker] State: {state}")
        if title:
            print(f"[PostOrderTracker] Title: {title}")

        if state == "OTP_REQUIRED":
            print("[PostOrderTracker] OTP verification detected.")
            print("[PostOrderTracker] Human intervention required; tracker is waiting.")
        elif state == "PAYMENT_CONTINUATION":
            print("[PostOrderTracker] Payment-provider continuation detected.")
        elif state == "OTP_ENTRY":
            print("[PostOrderTracker] OTP entry state detected; tracker remains passive.")
        elif state == "PURCHASE_COMPLETED":
            self._completed = True
            print("[PostOrderTracker] PURCHASE COMPLETION / RECEIPT STATE DETECTED.")

    def _inspect_current_state(self) -> None:
        if self._page is None:
            return

        try:
            url = self._page.url
        except Exception:
            return

        if not url:
            return

        parsed = urlsplit(url)
        title = self._safe_title()
        text = self._safe_body_text()
        state = self._classify_state(
            parsed.netloc.lower(),
            parsed.path or "/",
            title,
            text,
        )

        if url != self._last_url:
            self._last_url = url
            self._record_page(url, reason="state-poll")
            return

        if state == "PURCHASE_COMPLETED" and self._navigations:
            self._completed = True
            print("[PostOrderTracker] Purchase completion detected from current page state.")

    def _safe_title(self) -> str:
        try:
            return (self._page.title() or "").strip()[:200]
        except Exception:
            return ""

    def _safe_body_text(self) -> str:
        try:
            text = self._page.locator("body").inner_text(timeout=1000)
            return " ".join((text or "").split())[: self.MAX_TEXT_EXCERPT]
        except Exception:
            return ""

    @staticmethod
    def _safe_url(url: str) -> str:
        """Remove query values from logs while retaining query-key visibility."""
        parsed = urlsplit(url)
        keys = [key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)]
        query = "&".join(f"{key}=<redacted>" for key in keys)
        if query:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}"
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def _classify_state(host: str, path: str, title: str, text: str) -> str:
        normalized = f"{title} {text}".lower()
        path_lower = path.lower()
        host_lower = host.lower()

        if host_lower == "shopee.ph" and "/verify/otp" in path_lower:
            if "enter verification code" in normalized:
                return "OTP_ENTRY"
            return "OTP_REQUIRED"

        if "paylater.scredit.ph" in host_lower and "pay_v2" in path_lower:
            return "PAYMENT_CONTINUATION"

        completion_phrases = (
            "order placed successfully",
            "order confirmed",
            "purchase successful",
            "payment successful",
            "thank you for your order",
            "thank you for your purchase",
        )
        if any(phrase in normalized for phrase in completion_phrases):
            return "PURCHASE_COMPLETED"

        # A final order page is only considered completed when its visible
        # content contains a strong order/confirmation signal. This avoids
        # treating a generic /orders page as a successful purchase.
        order_path = (
            "/buyer/orders" in path_lower
            or "/order/" in path_lower
            or path_lower.rstrip("/").endswith("/orders")
        )
        strong_order_text = (
            "order number" in normalized
            or "order no" in normalized
            or "order details" in normalized
            or "order confirmed" in normalized
        )
        if order_path and strong_order_text:
            return "PURCHASE_COMPLETED"

        if "verification code" in normalized and "otp" in normalized:
            return "OTP_ENTRY"

        return "POST_ORDER_NAVIGATION"
