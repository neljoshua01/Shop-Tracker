"""
Monitors Shopee get_pc responses for the selected SKU.
"""

import threading
from threading import Event

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.parser.sku_price_parser import SkuPriceParser
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator


class SkuPriceMonitor:

    def __init__(self):

        self.browser = BrowserConnector()
        self.parser = SkuPriceParser()
        self.session = None
        self.latest_state: SkuPriceState | None = None
        self.updated = Event()
        self.triggered = Event()
        self.stop_event = Event()
        self.evaluator = PurchaseTriggerEvaluator()
        self.monitoring = False
        self.poll_interval = 5
        self._stopped = True
        self._callback_session = None
        self._callback_registered = False
        self._capture_done = Event()
        self._capture_done.set()
        self._capture_lock = threading.Lock()
        self._capture_pending = 0

    def start(self, session: PurchaseSession):
        self.session = session
        self.latest_state = None
        self.updated.clear()
        self.triggered.clear()
        self.stop_event.clear()
        self._capture_done.set()
        with self._capture_lock:
            self._capture_pending = 0
        self.monitoring = True
        self._stopped = False
        browser_session = session.browser_session

        if browser_session is not None and browser_session.page.is_closed():
            session.browser_session = None
            browser_session = None

        if browser_session is None:
            browser_session = self.browser.open_session(
                session.browser_owner,
                session.request.reference.url,
            )
            session.browser_session = browser_session

        self.browser.engine.register_response_callback(
            self,
            self.on_browser_response,
            session=browser_session,
        )
        self._callback_session = browser_session
        self._callback_registered = True

        print("[SkuPriceMonitor] Response callback bound to BrowserSession.")
        print("[SkuPriceMonitor] Monitoring SKU...")
        print(f"[SkuPriceMonitor] Item ID: {session.product.item_id}")
        print(f"[SkuPriceMonitor] Model ID: {session.variation.model_id}")

    def monitor(
        self,
        session: PurchaseSession,
        poll_interval: int = 5,
        cancellation_event: Event | None = None,
    ):
        if cancellation_event is not None and cancellation_event.is_set():
            return

        self.poll_interval = poll_interval
        self.start(session)
        browser_session = session.browser_session

        if browser_session is None:
            print("[SkuPriceMonitor] Browser session not available.")
            self.stop()
            return

        print()
        print("[SkuPriceMonitor] ========== CONTINUOUS MONITORING ==========")
        print("[SkuPriceMonitor] Prepared cart remains intact while monitoring the PDP.")
        actions = BrowserActions(browser_session)

        try:
            if browser_session.page.url != session.request.reference.url:
                print(
                    "[SkuPriceMonitor] Navigating to PDP for browser-generated "
                    "get_pc monitoring..."
                )
                actions.goto(session.request.reference.url)

            print(f"[SkuPriceMonitor] Monitoring PDP: {browser_session.page.url}")

            while self.monitoring:
                if cancellation_event is not None and cancellation_event.is_set():
                    print("[SkuPriceMonitor] Cancellation received.")
                    break

                if self.triggered.is_set():
                    print("[SkuPriceMonitor] Purchase trigger received.")
                    break

                if browser_session.page.is_closed():
                    print("[SkuPriceMonitor] Monitoring page was closed.")
                    break

                print()
                print("[SkuPriceMonitor] Refreshing PDP for get_pc...")

                self.updated.clear()

                try:
                    actions.reload()
                except Exception as e:
                    if browser_session.page.is_closed():
                        print("[SkuPriceMonitor] Monitoring session closed.")
                        break
                    print(f"[SkuPriceMonitor] PDP refresh failed: {e}")

                if self.triggered.is_set() or not self.monitoring:
                    break

                print()
                print(
                    "[SkuPriceMonitor] "
                    f"Waiting up to {self.poll_interval}s for get_pc processing..."
                )

                if self.updated.wait(timeout=self.poll_interval):
                    if self.triggered.is_set():
                        break
                    print("[SkuPriceMonitor] get_pc processing complete.")
                elif self.stop_event.is_set():
                    break
                else:
                    print(
                        "[SkuPriceMonitor] No valid get_pc response processed "
                        "during the polling window; retrying."
                    )

                # Never navigate away while a get_pc response body is still
                # being captured by the Playwright event-loop callback.
                if not self._capture_done.wait(timeout=self.poll_interval):
                    print(
                        "[SkuPriceMonitor] Waiting for in-flight get_pc response "
                        "capture before retrying."
                    )
                    self._capture_done.wait()

        finally:
            self._unregister_callback()
            self.monitoring = False
            print("[SkuPriceMonitor] Monitoring stopped.")

    def on_browser_response(self, response):
        if self._stopped:
            return

        if "/api/v4/pdp/get_pc" not in response.url:
            return

        # BrowserEngine invokes this synchronous boundary immediately on the
        # Playwright event-loop thread. Mark the body capture as pending before
        # returning the async handler, so the monitor thread cannot start a
        # second reload before the callback task begins execution.
        with self._capture_lock:
            self._capture_pending += 1
            self._capture_done.clear()

        print("[SkuPriceMonitor] get_pc response callback received.")
        return self._handle_browser_response(response)

    async def _handle_browser_response(self, response):
        try:
            try:
                data = await response.json()
            except Exception as e:
                print(f"[SkuPriceMonitor] Failed to decode get_pc response: {e}")
                return

            if not isinstance(data, dict):
                print("[SkuPriceMonitor] get_pc response is not a JSON object.")
                return

            self._process_get_pc(data)
        finally:
            with self._capture_lock:
                self._capture_pending -= 1
                if self._capture_pending <= 0:
                    self._capture_pending = 0
                    self._capture_done.set()

    def _process_get_pc(self, data: dict):
        print("[SkuPriceMonitor] get_pc response detected.")

        if self.session is None:
            print("[SkuPriceMonitor] No active purchase session.")
            return

        try:
            state = self.parser.parse(
                data,
                model_id=self.session.variation.model_id,
            )

            if state is None:
                print("[SkuPriceMonitor] Selected SKU not found in response.")
                return

            if state.item_id != self.session.product.item_id:
                print("[SkuPriceMonitor] Ignoring unrelated item.")
                return

            self.latest_state = state
            self.updated.set()

            should_trigger = self.evaluator.evaluate(self.session, state)

            if should_trigger:
                print("[SkuPriceMonitor] PURCHASE TRIGGERED.")
                self.triggered.set()
            else:
                print("[SkuPriceMonitor] Purchase trigger not reached.")

            print()
            print("[SkuPriceMonitor] ========== SKU STATE ==========")
            print(f"[SkuPriceMonitor] SKU: {state.name}")
            print(f"[SkuPriceMonitor] Price: {state.price}")
            print(f"[SkuPriceMonitor] Price before discount: {state.price_before_discount}")
            print(f"[SkuPriceMonitor] Promotion ID: {state.promotion_id}")
            print(f"[SkuPriceMonitor] Promotion types: {state.promotion_types}")
            print(f"[SkuPriceMonitor] Deep discount: {state.deep_discount}")
            print(f"[SkuPriceMonitor] Promotion price: {state.promotion_price}")
            print(f"[SkuPriceMonitor] Promotion event status: {state.promotion_event_status}")
            print(f"[SkuPriceMonitor] Promotion seconds until start: {state.promotion_seconds_until_start}")
            print(f"[SkuPriceMonitor] Promotion seconds until end: {state.promotion_seconds_until_end}")
            print(f"[SkuPriceMonitor] Promotion is LPP: {state.promotion_is_lpp}")
            print("[SkuPriceMonitor] ==============================")

        except Exception as e:
            print(f"[SkuPriceMonitor] Failed to process get_pc response: {e}")

    def wait_for_trigger(self, cancellation_event: Event | None = None):
        while not self.triggered.is_set():
            if cancellation_event is not None and cancellation_event.is_set():
                return False

            if self.stop_event.wait(0.25):
                if self.triggered.is_set():
                    return True
                return False

        return True

    def _unregister_callback(self):
        if not self._callback_registered:
            return

        try:
            self.browser.engine.unregister_response_callback(
                self,
                session=self._callback_session,
            )
        except Exception as e:
            print(f"[SkuPriceMonitor] Callback unregister warning: {e}")

        self._callback_session = None
        self._callback_registered = False

    def stop(self):
        if self._stopped:
            return

        self._stopped = True
        self.monitoring = False
        self.stop_event.set()
        self._unregister_callback()
