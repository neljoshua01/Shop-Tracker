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

    def start(
        self,
        session: PurchaseSession,
    ):

        self.session = session

        self.latest_state = None

        self.updated.clear()
        self.triggered.clear()
        self.stop_event.clear()

        browser_session = session.browser_session

        if browser_session is not None and browser_session.page.is_closed():
            session.browser_session = None
            browser_session = None

        callback_kwargs = {}
        if browser_session is not None:
            callback_kwargs["session"] = browser_session

        self.browser.engine.register_response_callback(
            self,
            self.on_browser_response,
            **callback_kwargs,
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

        browser_session = session.browser_session

        if browser_session is None:

            browser_session = self.browser.open_session(
                session.browser_owner,
                session.request.reference.url,
            )
            session.browser_session = browser_session

            # start() intentionally supports legacy registration before
            # a page exists. Bind that registration now to the page that
            # this purchase attempt owns.
            self.browser.engine.register_response_callback(
                self,
                self.on_browser_response,
                session=browser_session,
            )

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
            f"Monitoring from page: "
            f"{browser_session.page.url}"
        )

        actions = BrowserActions(browser_session)

        try:

            # Cart preparation uses this same page. Switch it back to
            # the PDP so Chrome itself produces the get_pc response.
            if browser_session.page.url != session.request.reference.url:
                actions.goto(session.request.reference.url)

            while self.monitoring:

                if self.triggered.is_set():

                    print(
                        "[SkuPriceMonitor] "
                        "Trigger received. "
                        "Stopping monitoring."
                    )

                    break

                print()
                print(
                    "[SkuPriceMonitor] "
                    "Refreshing PDP for get_pc..."
                )

                try:

                    #
                    # IMPORTANT:
                    #
                    # Do NOT call BrowserActions.request()
                    # for get_pc.
                    #
                    # That creates a separate Playwright API
                    # request and Shopee returns 403 / 90309999.
                    #
                    # Reloading the actual PDP causes Chrome itself
                    # to generate the real get_pc request.
                    #
                    # BrowserEngine's response callback then receives
                    # that browser-generated response and
                    # on_browser_response() processes it.
                    #
                    actions.reload()

                except Exception as e:

                    print(
                        "[SkuPriceMonitor] "
                        f"PDP refresh failed: {e}"
                    )

                if self.triggered.is_set():
                    break

                print()
                print(
                    "[SkuPriceMonitor] "
                    f"Waiting {self.poll_interval}s "
                    "before next check..."
                )

                #
                # Interruptible wait.
                #
                # stop() sets stop_event, so the monitor can
                # terminate immediately instead of waiting for
                # the entire polling interval.
                #
                if self.stop_event.wait(
                    timeout=self.poll_interval,
                ):

                    break

        finally:

            self.stop()

    def _process_get_pc(
        self,
        data: dict,
    ):

        print(
            "[SkuPriceMonitor] "
            "get_pc response detected."
        )

        try:

            state = self.parser.parse(
                data,
                model_id=self.session.variation.model_id,
            )

            #
            # Selected SKU wasn't present.
            #
            if state is None:

                print(
                    "[SkuPriceMonitor] "
                    "Selected SKU not found in response."
                )

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
            # Evaluate purchase condition.
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
                f"Seconds until start: "
                f"{state.promotion_seconds_until_start}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Seconds until end: "
                f"{state.promotion_seconds_until_end}"
            )

            print(
                f"[SkuPriceMonitor] "
                f"Is LPP: "
                f"{state.promotion_is_lpp}"
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

        self.stop_event.set()

        if self.session is not None:

            self.browser.engine.unregister_response_callback(
                self,
                session=self.session.browser_session,
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

    async def on_browser_response(
        self,
        response,
    ):

        if "/api/v4/pdp/get_pc" not in response.url:
            return

        if response.status != 200:
            return

        try:

            data = await response.json()

        except Exception as e:

            print(
                "[SkuPriceMonitor] "
                f"Failed to read browser get_pc JSON: {e}"
            )

            return

        self._process_get_pc(
            data,
        )
