"""Initializes Shopee checkout from the already-selected PDP variation.

The production path keeps the active PDP/browser session and dispatches the
visible Buy Now control through the page's native DOM. This lets Shopee's own
frontend initialize checkout state before redirecting to /checkout.

The cart DOM is never used. The initializer never clicks Place Order.

The direct URL method remains available only as an isolated experiment and is
not used by the production initializer.
"""

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.execution.variation_selector import VariationSelector


class DirectCheckoutInitializer:

    BUY_NOW_DISPATCH_SCRIPT = """
    (labels) => {
        const wanted = labels.map(label => label.toLowerCase());

        const isVisible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            return (
                rect.width > 0 &&
                rect.height > 0 &&
                style.visibility !== "hidden" &&
                style.display !== "none"
            );
        };

        const buttons = Array.from(document.querySelectorAll("button"));
        const button = buttons.find((candidate) => {
            const text = (candidate.innerText || candidate.textContent || "")
                .replace(/\s+/g, " ")
                .trim()
                .toLowerCase();

            return (
                wanted.some((label) => text === label || text.includes(label)) &&
                !candidate.disabled &&
                isVisible(candidate)
            );
        });

        if (!button) {
            return {
                found: false,
                clicked: false,
                reason: "Buy Now button not found or not interactable",
            };
        }

        button.scrollIntoView({
            block: "center",
            inline: "center",
        });

        button.click();

        return {
            found: true,
            clicked: true,
            text: (button.innerText || button.textContent || "")
                .replace(/\s+/g, " ")
                .trim(),
        };
    }
    """

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
        Carry the exact execution decision into checkout using the active PDP.

        No cart navigation and no direct /checkout URL navigation are used.
        """
        self._validate_decision(session, decision)
        self._open_product(session)

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
            "Dispatching native Buy Now DOM event on the selected PDP."
        )

        result = actions.evaluate(
            self.BUY_NOW_DISPATCH_SCRIPT,
            ["buy now", "bilihin na"],
        )

        print(
            "[DirectCheckoutInitializer] "
            f"Buy Now DOM dispatch result: {result}"
        )

        if not result or not result.get("clicked"):
            print(
                "[DirectCheckoutInitializer] "
                "Buy Now DOM dispatch failed."
            )
            return False

        try:
            actions.wait_for_url("**/checkout**", timeout=10000)
        except Exception as exc:
            current_url = session.browser_session.page.url
            print(
                "[DirectCheckoutInitializer] "
                f"Checkout navigation was not observed: {exc}"
            )
            print(
                "[DirectCheckoutInitializer] "
                f"Current URL after DOM dispatch: {current_url}"
            )
            return False

        current_url = session.browser_session.page.url
        print(
            "[DirectCheckoutInitializer] "
            f"URL after native Buy Now DOM dispatch: {current_url}"
        )

        if "/checkout" not in current_url:
            print(
                "[DirectCheckoutInitializer] "
                "Checkout page was not reached."
            )
            return False

        print(
            "[DirectCheckoutInitializer] "
            "Checkout page reached through Shopee's PDP Buy Now handler."
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
