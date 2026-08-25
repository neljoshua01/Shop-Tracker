"""
Prepares a purchase request by adding the requested
product and variation to the Shopee cart.
"""

from execution.browser.browser_connector import BrowserConnector
from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_status import PurchaseStatus
from purchase.execution.variation_selector import VariationSelector
from execution.browser.browser_action import BrowserActions


class CartPreparer:

    CART_URL = "https://shopee.ph/cart"

    def __init__(self):

        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def prepare(
        self,
        session: PurchaseSession,
    ):

        session.status = PurchaseStatus.ADDING_TO_CART

        # -------------------------------------------------
        # 1. Open the product page
        # -------------------------------------------------

        self._open_product(session)

        # -------------------------------------------------
        # 2. Select requested variation and prepare quantity
        # -------------------------------------------------

        self._select_variation(session)

        # -------------------------------------------------
        # 3. Add requested SKU to cart
        # -------------------------------------------------

        self.add_to_cart(session)

        # -------------------------------------------------
        # 4. Open cart and synchronize cart state
        # -------------------------------------------------

        self._open_cart(session)

        # Cart is now the prepared purchase state.
        session.status = PurchaseStatus.IN_CART

        print(
            "[CartPreparer] "
            "Cart preparation complete and cart state preserved."
        )

    def _open_product(
        self,
        session: PurchaseSession,
    ):

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

        elif (
            browser_session.page.url
            != session.request.reference.url
        ):

            BrowserActions(
                browser_session
            ).goto(
                session.request.reference.url
            )

    def _select_variation(
        self,
        session: PurchaseSession,
    ):

        self.variation_selector.select(session)

    def add_to_cart(
        self,
        session: PurchaseSession,
    ):

        print(
            "[CartPreparer] "
            "Adding product to cart..."
        )

        browser = BrowserActions(
            session.browser_session,
        )

        buttons = browser.find_all("button")
        count = browser.count(buttons)

        for i in range(count):

            button = buttons.nth(i)

            text = browser.text(button)

            if not text:
                continue

            normalized = " ".join(
                text.strip().lower().split()
            )

            if normalized == "add to cart":

                print(
                    "[CartPreparer] "
                    "Add To Cart button found."
                )

                browser.click(button)

                print(
                    "[CartPreparer] "
                    "Add To Cart clicked."
                )

                # Give Shopee's cart operation/UI a chance
                # to settle before navigating away.
                browser.wait_for_timeout(1000)

                return

        raise RuntimeError(
            "Add To Cart button not found."
        )

    def _open_cart(
        self,
        session: PurchaseSession,
    ):

        print(
            "[CartPreparer] "
            "Opening cart..."
        )

        browser = BrowserActions(
            session.browser_session,
        )

        browser.goto(
            self.CART_URL,
        )

        current_url = (
            session.browser_session.page.url
        )

        print(
            "[CartPreparer] "
            f"Cart URL: {current_url}"
        )

        if "/cart" not in current_url:

            raise RuntimeError(
                "Cart page was not reached."
            )

        # Allow the cart UI/API state to settle.
        browser.wait_for_timeout(2000)

        print(
            "[CartPreparer] "
            "Cart page ready."
        )
