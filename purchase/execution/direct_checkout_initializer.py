"""
Initializes Shopee checkout directly from the selected PDP variation.

The active Phase 1 path uses the normal browser-visible Buy Now flow. It does
not construct or use undocumented checkout URLs during normal execution.

An isolated direct-URL experiment is retained as a separate method for
controlled testing only. It is not wired into PurchasePipeline.

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

        buy_now_button = actions.first(buy_now_buttons)

        print(
            "[DirectCheckoutInitializer] "
            "Scrolling Buy Now into view..."
        )
        actions.scroll_into_view(buy_now_button)

        print(
            "[DirectCheckoutInitializer] "
            "Attempting force click on Shopee Buy Now."
        )
        actions.force_click(buy_now_button)
        actions.wait_for_timeout(3000)

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after Buy Now force click: {current_url}"
        )

        if "/checkout" in current_url:
            print(
                "[DirectCheckoutInitializer] "
                "Direct checkout page reached."
            )
            return True

        # Some React-driven controls can receive a native DOM click even when
        # Playwright's pointer click does not produce the expected transition.
        # This remains a UI click on the same visible Buy Now control.
        print(
            "[DirectCheckoutInitializer] "
            "Buy Now did not transition to checkout; attempting native DOM click."
        )
        actions.dom_click(buy_now_button)
        actions.wait_for_timeout(3000)

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after Buy Now DOM click: {current_url}"
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

    def build_direct_checkout_url(self, session, decision):
        """
        Build the experimental direct-checkout URL from verified execution data.

        This method is intentionally not used by initialize() or the normal
        PurchasePipeline. Shopee may change or reject this route at any time.
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
        Experimental direct-URL checkout path for isolated validation.

        This deliberately remains separate from normal execution and still
        stops at the checkout page; it never clicks Place Order.
        """
        url = self.build_direct_checkout_url(session, decision)
        actions = BrowserActions(session.browser_session)

        print(
            "[DirectCheckoutInitializer] "
            f"Testing experimental direct checkout URL: {url}"
        )
        actions.goto(url, wait_until="domcontentloaded")

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after experimental direct navigation: {current_url}"
        )

        return "/checkout" in current_url

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
