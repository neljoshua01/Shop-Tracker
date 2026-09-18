"""
Initializes Shopee checkout directly from the selected PDP variation.

This intentionally uses the normal browser-visible Buy Now flow. It does not
construct undocumented checkout URLs or call private checkout APIs.

The initializer is responsible only for carrying the already-selected SKU
into checkout. It never authorizes or clicks Place Order.
"""

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.execution.variation_selector import VariationSelector


class DirectCheckoutInitializer:

    def __init__(self):
        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def prepare(self, session):
        """Open the PDP and establish the selected variation/quantity for monitoring."""
        self._open_product(session)
        self.variation_selector.select(session)

        print(
            "[DirectCheckoutInitializer] "
            "Product context prepared; cart flow is not used."
        )

    def initialize(self, session, decision):
        """Carry the exact execution decision into Shopee checkout."""
        self._validate_decision(session, decision)

        # The variation was already selected during product-context preparation.
        # Re-selecting it here adds latency and can race Shopee PDP updates.
        # Phase 1 carries the exact selected context forward to Buy Now.
        self._open_product(session)

        actions = BrowserActions(session.browser_session)

        buy_now_buttons = actions.find_all(
            "button:has-text('Buy Now')"
        )
        count = actions.count(buy_now_buttons)

        print(
            "[DirectCheckoutInitializer] "
            f"Buy Now buttons found: {count}"
        )

        if count == 0:
            print(
                "[DirectCheckoutInitializer] "
                "Buy Now button not found; direct checkout aborted."
            )
            return False

        print(
            "[DirectCheckoutInitializer] "
            "Starting direct checkout through Shopee Buy Now."
        )
        actions.click(actions.first(buy_now_buttons))
        actions.wait_for_timeout(3000)

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after Buy Now: {current_url}"
        )

        if "/checkout" not in current_url:
            print(
                "[DirectCheckoutInitializer] "
                "Checkout page was not reached."
            )
            return False

        print(
            "[DirectCheckoutInitializer] "
            "Direct checkout page reached."
        )
        return True

    def _validate_decision(self, session, decision):
        if decision is None:
            raise ValueError("Execution decision is required.")

        if decision.item_id != session.product.item_id:
            raise ValueError(
                "Execution decision item_id does not match the purchase session."
            )

        if decision.model_id != session.variation.model_id:
            raise ValueError(
                "Execution decision model_id does not match the selected variation."
            )

        expected_options = tuple(sorted(
            (str(key), str(value))
            for key, value in session.request.options.items()
        ))
        if decision.variation_options != expected_options:
            raise ValueError(
                "Execution decision variation options do not match the purchase session."
            )

        if decision.quantity != session.request.quantity:
            raise ValueError(
                "Execution decision quantity does not match the purchase session."
            )

    def _open_product(self, session):
        browser_session = session.browser_session

        if (
            browser_session is None
            or browser_session.page.is_closed()
        ):
            browser_session = self.browser.open_session(
                session.browser_owner,
                session.request.reference.url,
            )
            session.browser_session = browser_session
            return

        if browser_session.page.url != session.request.reference.url:
            BrowserActions(browser_session).goto(
                session.request.reference.url
            )
