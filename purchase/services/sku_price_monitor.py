"""
Monitors Shopee get_pc responses for the selected SKU.
"""

from threading import Event

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.parser.sku_price_parser import SkuPriceParser
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from purchase.services.promotion_forensics import PromotionForensicsRecorder


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

    def start(self, session: PurchaseSession):
        self.session = session
        self.latest_state = None
        session.monitored_item_id = None
        session.monitored_model_id = None
        session.monitored_sku_identity_verified = False
        self.updated.clear()
        self.triggered.clear()
        self.stop_event.clear()
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

        finally:
            self._unregister_callback()
            self.monitoring = False
            print("[SkuPriceMonitor] Monitoring stopped.")

    async def on_browser_response(self, response):
        if self._stopped:
            return

        if "/api/v4/pdp/get_pc" not in response.url:
            return

        print("[SkuPriceMonitor] get_pc response callback received.")

        try:
            data = await response.json()
        except Exception as e:
            print(f"[SkuPriceMonitor] Failed to decode get_pc response: {e}")
            return

        if not isinstance(data, dict):
            print("[SkuPriceMonitor] get_pc response is not a JSON object.")
            return

        self._process_get_pc(data)

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

            expected_item_id = self.session.product.item_id
            expected_model_id = self.session.variation.model_id

            if state.item_id != expected_item_id:
                print("[SkuPriceMonitor] Ignoring unrelated item.")
                return

            if state.model_id != expected_model_id:
                print(
                    "[SkuPriceMonitor] SKU identity mismatch: "
                    f"expected item/model {expected_item_id}/{expected_model_id}, "
                    f"received {state.item_id}/{state.model_id}."
                )
                return

            # The parser already selects the requested model_id. Keep an
            # explicit runtime identity record so the exact model observed in
            # live get_pc data is carried with this purchase session.
            self.session.monitored_item_id = state.item_id
            self.session.monitored_model_id = state.model_id
            self.session.monitored_sku_identity_verified = True

            print(
                "[SkuPriceMonitor] SKU identity verified: "
                f"item={state.item_id}, model={state.model_id}"
            )

            if state.promotion_detected:
                print(
                    "[SkuPriceMonitor] PROMOTION DETECTED for exact SKU: "
                    f"item={state.item_id}, model={state.model_id}, "
                    f"promotion_id={state.promotion_id}, "
                    f"types={state.promotion_types}"
                )
            else:
                print(
                    "[SkuPriceMonitor] No exact-SKU promotion evidence detected."
                )

            self.latest_state = state
            self.updated.set()

            should_trigger = self.evaluator.evaluate(self.session, state)

            recorder = PromotionForensicsRecorder.get(self.session)
            if recorder is not None:
                recorder.record_event(
                    "sku_state_processed",
                    "pdp_get_pc",
                    {
                        "item_id": state.item_id,
                        "model_id": state.model_id,
                        "sku": state.name,
                        "price": state.price,
                        "price_before_discount": state.price_before_discount,
                        "promotion_detected": state.promotion_detected,
                        "promotion_evidence": state.promotion_evidence,
                        "promotion_id": state.promotion_id,
                        "promotion_types": state.promotion_types,
                        "deep_discount": state.deep_discount,
                        "promotion_price": state.promotion_price,
                        "promotion_event_status": state.promotion_event_status,
                        "promotion_seconds_until_start": state.promotion_seconds_until_start,
                        "promotion_seconds_until_end": state.promotion_seconds_until_end,
                        "promotion_is_lpp": state.promotion_is_lpp,
                        "has_stock": state.has_stock,
                        "trigger_evaluation": should_trigger,
                    },
                )

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
            print(f"[SkuPriceMonitor] Promotion detected: {state.promotion_detected}")
            print(f"[SkuPriceMonitor] Promotion evidence: {state.promotion_evidence}")
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
