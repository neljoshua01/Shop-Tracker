"""Initialize checkout from the already-selected PDP variation.

The production path keeps the active PDP/browser session, restores the exact
variation after monitoring refreshes, and invokes the visible Buy Now control
with a real Playwright locator click. Shopee may route that native Buy Now
handoff through /cart before /checkout, so the initializer verifies the
Buy Now-generated cart identity and continues through its Check Out control.

The initializer never clicks Place Order.

The direct URL method remains available only as an isolated experiment and is
not used by the production initializer.
"""

from urllib.parse import parse_qs, urlparse

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.execution.variation_selector import VariationSelector


class DirectCheckoutInitializer:

    BUY_NOW_LABELS = ("buy now", "bilihin na", "buy with voucher")
    CART_CHECKOUT_LABELS = ("check out", "checkout", "proceed to checkout")

    def __init__(self):
        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def prepare(self, session):
        """Open the PDP and establish the selected variation/quantity once."""
        self._open_product(session)
        self.variation_selector.select(session)

        session.pdp_context_prepared = True
        session.pdp_selection_verified = True

        print(
            "[DirectCheckoutInitializer] "
            "Product context prepared; variation/quantity are now frozen for "
            "this purchase session."
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Prepared SKU: item={session.product.item_id}, "
            f"model={session.variation.model_id}, quantity={session.request.quantity}"
        )

    def initialize(self, session, decision):
        """
        Carry the exact execution decision into checkout using Shopee's native
        PDP Buy Now flow.

        Shopee may route Buy Now through a cart state before checkout. That
        intermediate route is treated as a Buy Now-generated handoff, not as
        the old Add To Cart purchase flow.
        """
        self._validate_decision(session, decision)

        if not session.pdp_context_prepared or not session.pdp_selection_verified:
            print(
                "[DirectCheckoutInitializer] "
                "PDP execution context was not prepared and verified."
            )
            return False

        if (
            session.browser_session is None
            or session.browser_session.page.is_closed()
            or session.browser_session.page.url != session.request.reference.url
        ):
            print(
                "[DirectCheckoutInitializer] "
                "Prepared PDP context is no longer available for Buy Now."
            )
            return False

        print(
            "[DirectCheckoutInitializer] "
            "Pre-Buy-Now state verification: prepared PDP context is intact."
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Frozen SKU: item={session.product.item_id}, "
            f"model={session.variation.model_id}, quantity={session.request.quantity}"
        )

        actions = BrowserActions(session.browser_session)

        print(
            "[DirectCheckoutInitializer] "
            "Starting checkout from monitored SKU."
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Item={decision.item_id}, model={decision.model_id}, "
            f"quantity={decision.quantity}"
        )
        print(
            "[DirectCheckoutInitializer] "
            "========== PDP BUY NOW DOM DIAGNOSTIC =========="
        )

        diagnostic = actions.capture_pdp_purchase_controls(
            labels=list(self.BUY_NOW_LABELS) + ["add to cart"],
            timeout=10000,
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Purchase-control DOM snapshot: {diagnostic}"
        )

        print(
            "[DirectCheckoutInitializer] "
            "================================================"
        )

        print(
            "[DirectCheckoutInitializer] "
            "Clicking visible Buy Now control with Playwright."
        )

        result = actions.click_visible_button_by_labels(
            list(self.BUY_NOW_LABELS),
            timeout=10000,
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Buy Now Playwright click result: {result}"
        )

        if not result or not result.get("clicked"):
            print(
                "[DirectCheckoutInitializer] "
                "Buy Now Playwright click failed."
            )
            return False

        current_url = session.browser_session.page.url
        navigations = result.get("navigations", [])

        print(
            "[DirectCheckoutInitializer] "
            f"Buy Now navigation chain: {navigations}"
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Current URL after Buy Now: {current_url}"
        )

        if "/checkout" in current_url:
            if session.e1_timing is not None:
                session.e1_timing.record("T11")
            print(
                "[DirectCheckoutInitializer] "
                "Checkout page reached directly through Shopee's PDP Buy Now handler."
            )
            return True

        cart_url = next(
            (
                url
                for url in navigations
                if "/cart" in url and "itemKeys=" in url
            ),
            None,
        )

        if cart_url is None and "/cart" in current_url:
            cart_url = current_url

        if cart_url is not None:
            return self._continue_buy_now_cart_handoff(
                session,
                decision,
                actions,
                cart_url,
            )

        print(
            "[DirectCheckoutInitializer] "
            "Buy Now did not produce a recognized cart or checkout handoff."
        )
        return False

    def _continue_buy_now_cart_handoff(
        self,
        session,
        decision,
        actions,
        cart_url,
    ):
        """
        Verify the cart state created by PDP Buy Now, then continue to checkout.

        This is deliberately not CartPreparer: the cart was created by
        Shopee's native Buy Now handler, not by the purchase pipeline's
        Add To Cart flow.
        """
        print(
            "[DirectCheckoutInitializer] "
            "========== BUY NOW CART HANDOFF =========="
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Buy Now cart URL: {cart_url}"
        )

        query = parse_qs(urlparse(cart_url).query)
        item_keys = query.get("itemKeys", [])

        if not item_keys:
            print(
                "[DirectCheckoutInitializer] "
                "Buy Now cart handoff did not expose itemKeys."
            )
            return False

        expected_key = f"{decision.item_id}.{decision.model_id}"
        matched = any(
            expected_key in str(item_key)
            for item_key in item_keys
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Expected cart item key: {expected_key}"
        )
        print(
            "[DirectCheckoutInitializer] "
            f"Observed cart itemKeys: {item_keys}"
        )

        if not matched:
            print(
                "[DirectCheckoutInitializer] "
                "Cart handoff SKU identity mismatch."
            )
            return False

        print(
            "[DirectCheckoutInitializer] "
            "Cart handoff SKU identity verified."
        )

        # The Buy Now flow may redirect from the itemKeys URL to plain /cart.
        # Wait for the final cart document before inspecting its controls.
        if "/cart" not in session.browser_session.page.url:
            try:
                actions.wait_for_url("**/cart**", timeout=10000)
            except Exception as exc:
                print(
                    "[DirectCheckoutInitializer] "
                    f"Cart page was not reached after Buy Now: {exc}"
                )
                return False

        print(
            "[DirectCheckoutInitializer] "
            f"Cart page ready: {session.browser_session.page.url}"
        )

        if session.e1_timing is not None:
            session.e1_timing.record("T9")

        cart_diagnostic = actions.capture_pdp_purchase_controls(
            labels=list(self.CART_CHECKOUT_LABELS),
            timeout=10000,
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Cart checkout-control diagnostic: {cart_diagnostic}"
        )

        print(
            "[DirectCheckoutInitializer] "
            "Clicking cart Check Out control with Playwright."
        )

        checkout_result = actions.click_visible_button_by_labels(
            list(self.CART_CHECKOUT_LABELS),
            timeout=15000,
            wait_for_url="**/checkout**",
            navigation_timeout=15000,
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Cart Check Out click result: {checkout_result}"
        )

        if session.e1_timing is not None:
            session.e1_timing.record("T10")

        if not checkout_result or not checkout_result.get("clicked"):
            print(
                "[DirectCheckoutInitializer] "
                "Cart Check Out control was not available."
            )
            return False

        if not checkout_result.get("url_wait_satisfied", False):
            current_url = session.browser_session.page.url
            print(
                "[DirectCheckoutInitializer] "
                "Checkout URL was not observed by the pre-armed navigation waiter."
            )
            print(
                "[DirectCheckoutInitializer] "
                f"Navigation wait error: {checkout_result.get('url_wait_error')}"
            )
            print(
                "[DirectCheckoutInitializer] "
                f"Current URL after cart Check Out: {current_url}"
            )
            if "/checkout" not in current_url:
                return False

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after cart Check Out: {current_url}"
        )

        if "/checkout" not in current_url:
            print(
                "[DirectCheckoutInitializer] "
                "Checkout page was not reached after cart handoff."
            )
            return False

        if session.e1_timing is not None:
            session.e1_timing.record("T11")

        print(
            "[DirectCheckoutInitializer] "
            "Checkout page reached through Buy Now -> cart -> checkout."
        )
        return True

    def build_direct_checkout_url(self, session, decision):
        """
        Build the direct-checkout URL from verified execution data.

        Retained for isolated experiments only; production initialize() does
        not use this route.
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
        Experimental direct-URL checkout path.

        This is not used by the production pipeline.
        """
        url = self.build_direct_checkout_url(session, decision)
        actions = BrowserActions(session.browser_session)

        print(
            "[DirectCheckoutInitializer] "
            f"Testing experimental direct checkout URL: {url}"
        )
        actions.goto(url, wait_until="domcontentloaded")
        actions.wait_for_timeout(3000)

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
