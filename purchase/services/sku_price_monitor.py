"""
Monitors Shopee get_pc responses for the selected SKU.
"""

from threading import Event

from execution.browser.browser_connector import BrowserConnector
from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.parser.sku_price_parser import SkuPriceParser
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from execution.browser.browser_action import BrowserActions


class SkuPriceMonitor:

    def __init__(self):

        self.browser = BrowserConnector()

        self.parser = SkuPriceParser()

        self.session = None

        self.latest_state: SkuPriceState | None = None

        self.updated = Event()
        self.triggered = Event()
        self.evaluator = PurchaseTriggerEvaluator()

        self.monitoring = False
        self.poll_interval = 5

    def start(
        self,
        session: PurchaseSession,
    ):

        self.session = session

        self.latest_state = None

        self.updated.clear()
        self.triggered.clear()

        self.browser.engine.register_response_callback(
            self,
            self.on_response,
        )

        print(
            "[SkuPriceMonitor] Monitoring SKU..."
        )

        print(
            f"[SkuPriceMonitor] "
            f"Item ID: {session.product.item_id}"
        )

        print(
            f"[SkuPriceMonitor] "
            f"Model ID: {session.variation.model_id}"
        )

    def monitor(
        self,
        session: PurchaseSession,
        poll_interval: int = 5,
    ):
        self.start(session)

        self.poll_interval = poll_interval
        self.monitoring = True

        print()
        print(
            "[SkuPriceMonitor] "
            "========== CONTINUOUS MONITORING =========="
        )

        try:

            #
            # Open the product page.
            #
            browser_session = self.browser.open_session(
                self,
                session.request.reference.url,
            )

            session.browser_session = browser_session

            browser = BrowserActions(
                browser_session,
            )

            #
            # The initial page load should produce get_pc.
            #
            while self.monitoring:

                print()
                print(
                    "[SkuPriceMonitor] "
                    "Waiting for get_pc response..."
                )

                received = self.updated.wait(
                    timeout=self.poll_interval + 10,
                )

                self.updated.clear()

                if not received:

                    print(
                        "[SkuPriceMonitor] "
                        "No get_pc response received."
                    )

                #
                # A response may have triggered the purchase.
                #
                if self.triggered.is_set():

                    print(
                        "[SkuPriceMonitor] "
                        "Trigger received. "
                        "Stopping monitoring."
                    )

                    break

                #
                # Wait before requesting another
                # product API state.
                #
                print(
                    "[SkuPriceMonitor] "
                    f"Waiting {self.poll_interval}s "
                    "before next check..."
                )

                browser.wait_for_timeout(
                    self.poll_interval * 1000,
                )

                if not self.monitoring:
                    break

                #
                # Reload product page.
                #
                print(
                    "[SkuPriceMonitor] "
                    "Reloading product page..."
                )

                browser.reload()

        finally:

            self.stop()

    async def on_response(
        self,
        response,
    ):

        #
        # Ignore unrelated API responses.
        #
        if "/api/v4/pdp/get_pc" not in response.url:
            return

        print(
            "[SkuPriceMonitor] "
            "get_pc response detected."
        )

        try:

            data = await response.json()

            state = self.parser.parse(
                data,
                model_id=self.session.variation.model_id,
            )

            #
            # Selected SKU wasn't present.
            #
            if state is None:
                return

            #
            # Make absolutely sure this is our product.
            #
            if state.item_id != self.session.product.item_id:

                print(
                    "[SkuPriceMonitor] "
                    "Ignoring unrelated item."
                )

                return

            self.latest_state = state

            #
            # Evaluate whether this SKU should trigger purchase.
            #
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
                "[SkuPriceMonitor] "
                "=============================="
            )

            self.updated.set()

        except Exception as e:

            print(
                f"[SkuPriceMonitor] "
                f"Failed to process get_pc: {e}"
            )

    def stop(self):

        self.monitoring = False

        self.browser.engine.unregister_response_callback(
            self,
        )

        self.session = None

        print(
            "[SkuPriceMonitor] Monitoring stopped."
        )

    def wait_for_trigger(
        self,
        timeout: float | None = None,
    ) -> bool:

        return self.triggered.wait(
            timeout=timeout,
        )