"""
Prepares a purchase request by adding the requested
product, variation, and quantity to the Shopee cart.
"""

from execution.browser.browser_connector import BrowserConnector
from purchase.models.purchase_session import PurchaseSession
from purchase.execution.variation_selector import VariationSelector
from execution.browser.browser_action import BrowserActions


class CartPreparer:

    def __init__(self):

        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def prepare(
        self,
        session: PurchaseSession,
    ):

        self._open_product(session)

        self._select_variation(session)

        self.add_to_cart(session)

    def _open_product(
        self,
        session: PurchaseSession,
    ):

        browser_session = self.browser.open_session(
            self,
            session.request.reference.url,
        )

        session.browser_session = browser_session

    def _select_variation(
        self,
        session: PurchaseSession,
    ):

        self.variation_selector.select(session)

    def add_to_cart(
        self,
        session: PurchaseSession,
    ):
        print("[CartPreparer] Adding product to cart...")

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
                    "[CartPreparer] Add To Cart button found."
                )

                browser.click(button)

                print(
                    "[CartPreparer] Product added to cart."
                )

                return

        raise RuntimeError(
            "Add To Cart button not found."
        )