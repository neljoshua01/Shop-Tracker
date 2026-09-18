"""
Initializes Shopee checkout directly from the selected PDP variation.

Phase 1 carries the exact monitored execution decision directly to Shopee's
checkout route. The cart DOM and Buy Now button are not used by the production
checkout path.

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
        """
        Carry the exact execution decision directly to Shopee checkout.

        No Buy Now button is clicked and no cart page is visited.
        """
        return self.initialize_via_direct_url(session, decision)

    def build_direct_checkout_url(self, session, decision):
        """
        Build the direct-checkout URL from verified execution data.
        """
        self._validate_decision(session, decision)

        item_id = decision.item_id
        model_id = decision.model_id
        quantity = decision.quantity

        return (
            "https://shopee.ph/checkout"
            f"?buy_now=true&item_id={item_id}"
            f"&model_id={model_id}&quantity={quantity}"
        )

    def initialize_via_direct_url(self, session, decision):
        """
        Navigate directly to checkout using the exact monitored SKU.

        This stops at the checkout page and never clicks Place Order.
        """
        url = self.build_direct_checkout_url(session, decision)
        actions = BrowserActions(session.browser_session)

        print(
            "[DirectCheckoutInitializer] "
            "Starting direct checkout from monitored SKU."
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Item={decision.item_id}, model={decision.model_id}, "
            f"quantity={decision.quantity}"
        )
        print(
            "[DirectCheckoutInitializer] "
            "Bypassing cart DOM and Buy Now button."
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Navigating to direct checkout URL: {url}"
        )

        actions.goto(url, wait_until="domcontentloaded")
        actions.wait_for_timeout(3000)

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after direct checkout navigation: {current_url}"
        )

        if "/checkout" not in current_url:
            print(
                "[DirectCheckoutInitializer] "
                "Direct checkout page was not reached."
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
