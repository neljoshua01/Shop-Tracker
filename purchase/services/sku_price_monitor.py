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

    # =====================================================
    # START
    # =====================================================

    def start(self, session: PurchaseSession):

        self.session = session

        self.latest_state = None

        self.updated.clear()
        self.triggered.clear()
        self.stop_event.clear()

        self.monitoring = True
        self._stopped = False

        browser_session = session.browser_session

        if (
            browser_session is not None
            and browser_session.page.is_closed()
        ):
            session.browser_session = None
            browser_session = None

        #
        # The cart preparer should already have created the
        # browser session. Reuse that exact session.
        #
        if browser_session is None:

            browser_session = self.browser.open_session(
                session.browser_owner,
                session.request.reference.url,
            )

            session.browser_session = browser_session

        #
        # Bind get_pc response monitoring to this session.
        #
        self.browser.engine.register_response_callback(
            self,
            self.on_browser_response,
            session=browser_session,
        )

        self._callback_session = browser_session
        self._callback_registered = True

        print(
            "[SkuPriceMonitor] "
            "Response callback bound to BrowserSession."
        )

        print(
            "[SkuPriceMonitor] "
            "Monitoring SKU..."
        )

        print(
            f"[SkuPriceMonitor] "
            f"Item ID: {session.product.item_id}"
        )

        print(
            f"[SkuPriceMonitor] "
            f"Model ID: {session.variation.model_id}"
        )

    # =====================================================
    # MONITOR
    # =====================================================

    def monitor(
        self,
        session: PurchaseSession,
        poll_interval: int = 5,
        cancellation_event: Event | None = None,
    ):

        if (
            cancellation_event is not None
            and cancellation_event.is_set()
        ):
            return

        self.poll_interval = poll_interval

        self.start(session)

        browser_session = session.browser_session

        if browser_session is None:

            print(
                "[SkuPriceMonitor] "
                "Browser session not available."
            )

            self.stop()
            return

        print()
        print(
            "[SkuPriceMonitor] "
            "========== CONTINUOUS MONITORING =========="
        )

        print(
            "[SkuPriceMonitor] "
            "Prepared cart remains intact while monitoring the PDP."
        )

        actions = BrowserActions(browser_session)

        try:

            #
            # Navigate the EXISTING purchase session to the PDP.
            #
            # This does not recreate the cart.
            #

            if (
                browser_session.page.url
                != session.request.reference.url
            ):

                print(
                    "[SkuPriceMonitor] "
                    "Navigating to PDP for browser-generated "
                    "get_pc monitoring..."
                )

                actions.goto(
                    session.request.reference.url,
                )

            print(
                "[SkuPriceMonitor] "
                f"Monitoring PDP: {browser_session.page.url}"
            )

            #
            # Continuous monitoring loop.
            #

            while self.monitoring:

                #
                # External cancellation.
                #

                if (
                    cancellation_event is not None
                    and cancellation_event.is_set()
                ):
                    print(
                        "[SkuPriceMonitor] "
                        "Cancellation received."
                    )
                    break

                #
                # Purchase trigger.
                #

                if self.triggered.is_set():

                    print(
                        "[SkuPriceMonitor] "
                        "Purchase trigger received."
                    )

                    break

                #
                # Browser session unexpectedly closed.
                #

                if browser_session.page.is_closed():

                    print(
                        "[SkuPriceMonitor] "
                        "Monitoring page was closed."
                    )

                    break

                print()
                print(
                    "[SkuPriceMonitor] "
                    "Refreshing PDP for get_pc..."
                )

                try:

                    actions.reload()

                except Exception as e:

                    if browser_session.page.is_closed():

                        print(
                            "[SkuPriceMonitor] "
                            "Monitoring session closed."
                        )

                        break

                    print(
                        "[SkuPriceMonitor] "
                        f"PDP refresh failed: {e}"
                    )

                #
                # Do not immediately stop after a refresh.
                #
                # Give the callback time to process the response.
                #

                if self.triggered.is_set():
                    break

                if not self.monitoring:
                    break

                print()
                print(
                    "[SkuPriceMonitor] "
                    f"Waiting {self.poll_interval}s "
                    "before next check..."
                )

                if self.stop_event.wait(
                    timeout=self.poll_interval,
                ):
                    break

        finally:

            #
            # The monitor itself is finished.
            #
            # Clean up ONLY its callback state.
            #

            self._unregister_callback()

            self.monitoring = False

            print(
                "[SkuPriceMonitor] "
                "Monitoring stopped."
            )

    # =====================================================
    # BROWSER RESPONSE CALLBACK
    # =====================================================

    async def on_browser_response(
        self,
        response,
    ):

        if self._stopped:
            return

        if "/api/v4/pdp/get_pc" not in response.url:
            return

        print(
            "[SkuPriceMonitor] "
            "get_pc response callback received."
        )

        try:

            data = await response.json()

        except Exception as e:

            print(
                "[SkuPriceMonitor] "
                f"Failed to decode get_pc response: {e}"
            )

            return

        if not isinstance(data, dict):

            print(
                "[SkuPriceMonitor] "
                "get_pc response is not a JSON object."
            )

            return

        self._process_get_pc(data)

    # =====================================================
    # PROCESS GET_PC
    # =====================================================

    def _process_get_pc(
        self,
        data: dict,
    ):

        print(
            "[SkuPriceMonitor] "
            "get_pc response detected."
        )

        if self.session is None:

            print(
                "[SkuPriceMonitor] "
                "No active purchase session."
            )

            return

        try:

            state = self.parser.parse(
                data,
                model_id=self.session.variation.model_id,
            )

            if state is None:

                print(
                    "[SkuPriceMonitor] "
                    "Selected SKU not found in response."
                )

                return

            if state.item_id != self.session.product.item_id:

                print(
                    "[SkuPriceMonitor] "
                    "Ignoring unrelated item."
                )

                return

            self.latest_state = state
            self.updated.set()

            should_trigger = self.evaluator.evaluate(
                self.session,
                state,
            )

            if should_trigger:

                print(
                    "[SkuPriceMonitor] "
                    "PURCHASE TRIGGERED."
                )

                self.triggered.set()

            else:

                print(
                    "[SkuPriceMonitor] "
                    "Purchase trigger not reached."
                )

            print()
            print(
                "[SkuPriceMonitor] "
                "========== SKU STATE =========="
            )

            print(
                f"[SkuPriceMonitor] "
                f"SKU: {state.name}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Price: {state.price}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Price before discount: "
                f"{state.price_before_discount}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion ID: "
                f"{state.promotion_id}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion types: "
                f"{state.promotion_types}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Deep discount: "
                f"{state.deep_discount}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion price: "
                f"{state.promotion_price}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion event status: "
                f"{state.promotion_event_status}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion seconds until start: "
                f"{state.promotion_seconds_until_start}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion seconds until end: "
                f"{state.promotion_seconds_until_end}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Promotion is LPP: "
                f"{state.promotion_is_lpp}"
            )

            print(
                "[SkuPriceMonitor] "
                "=============================="
            )

        except Exception as e:

            print(
                "[SkuPriceMonitor] "
                f"Failed to process get_pc response: {e}"
            )

    # =====================================================
    # WAIT FOR TRIGGER
    # =====================================================

    def wait_for_trigger(
        self,
        cancellation_event: Event | None = None,
    ):

        while not self.triggered.is_set():

            if (
                cancellation_event is not None
                and cancellation_event.is_set()
            ):
                return False

            if self.stop_event.wait(0.25):
                if self.triggered.is_set():
                    return True
                return False

        return True

    # =====================================================
    # CALLBACK CLEANUP
    # =====================================================

    def _unregister_callback(self):

        if not self._callback_registered:
            return

        try:

            self.browser.engine.unregister_response_callback(
                self,
                session=self._callback_session,
            )

        except Exception as e:

            print(
                "[SkuPriceMonitor] "
                f"Callback unregister warning: {e}"
            )

        self._callback_session = None
        self._callback_registered = False

    # =====================================================
    # STOP
    # =====================================================

    def stop(self):

        if self._stopped:
            return

        self._stopped = True
        self.monitoring = False

        self.stop_event.set()

        self._unregister_callback()