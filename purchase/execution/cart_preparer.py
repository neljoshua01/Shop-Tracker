"""
Prepares a purchase request by adding the requested
product and variation to the Shopee cart.
"""

from execution.browser.browser_connector import BrowserConnector
from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_status import PurchaseStatus
from purchase.execution.variation_selector import VariationSelector
from execution.browser.browser_action import BrowserActions
from purchase.services.promotion_forensics import PromotionForensicsRecorder


class CartPreparer:

    CART_URL = "https://shopee.ph/cart"

    def __init__(self):
        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def prepare(self, session: PurchaseSession):
        session.status = PurchaseStatus.ADDING_TO_CART

        # 1. Open the product page.
        self._open_product(session)

        # Attach forensic capture before variation selection, Add To Cart,
        # and the cart navigation so the run preserves the complete purchase
        # preparation evidence rather than starting only at monitoring.
        recorder = PromotionForensicsRecorder.get(session)
        if recorder is not None and session.browser_session is not None:
            recorder.attach_engine(self.browser.engine, session.browser_session)
            recorder.record_event("product_page_ready", "cart_preparation", {
                "page_url": session.browser_session.page.url,
                "item_id": session.product.item_id,
                "model_id": session.variation.model_id,
            })

        # 2. Select requested variation and prepare quantity.
        self._select_variation(session)

        # 3. Add requested SKU to cart.
        self.add_to_cart(session)

        # 4. Open cart and synchronize cart state.
        self._open_cart(session)

        session.status = PurchaseStatus.IN_CART

        if recorder is not None:
            recorder.record_event("cart_preparation_complete", "cart_preparation", {
                "page_url": session.browser_session.page.url if session.browser_session else None,
                "item_id": session.product.item_id,
                "model_id": session.variation.model_id,
            })

        print(
            "[CartPreparer] "
            "Cart preparation complete and cart state preserved."
        )

    def _open_product(self, session: PurchaseSession):
        browser_session = session.browser_session

        if browser_session is None or browser_session.page.is_closed():
            browser_session = self.browser.open_session(
                session.browser_owner,
                session.request.reference.url,
            )
            session.browser_session = browser_session
        elif browser_session.page.url != session.request.reference.url:
            BrowserActions(browser_session).goto(session.request.reference.url)

    def _select_variation(self, session: PurchaseSession):
        self.variation_selector.select(session)

    def add_to_cart(self, session: PurchaseSession):
        print("[CartPreparer] Adding product to cart...")

        browser = BrowserActions(session.browser_session)
        buttons = browser.find_all("button")
        count = browser.count(buttons)

        for i in range(count):
            button = buttons.nth(i)
            text = browser.text(button)
            if not text:
                continue

            normalized = " ".join(text.strip().lower().split())
            if normalized == "add to cart":
                print("[CartPreparer] Add To Cart button found.")
                browser.click(button)
                print("[CartPreparer] Add To Cart clicked.")

                recorder = PromotionForensicsRecorder.get(session)
                if recorder is not None:
                    recorder.record_event("add_to_cart_clicked", "cart_preparation", {
                        "item_id": session.product.item_id,
                        "model_id": session.variation.model_id,
                        "quantity": session.request.quantity,
                    })

                browser.wait_for_timeout(1000)
                return

        recorder = PromotionForensicsRecorder.get(session)
        if recorder is not None:
            recorder.record_event("add_to_cart_button_missing", "cart_preparation")
        raise RuntimeError("Add To Cart button not found.")

    def _open_cart(self, session: PurchaseSession):
        print("[CartPreparer] Opening cart...")

        browser = BrowserActions(session.browser_session)
        browser.goto(self.CART_URL)

        current_url = session.browser_session.page.url
        print(f"[CartPreparer] Cart URL: {current_url}")

        if "/cart" not in current_url:
            recorder = PromotionForensicsRecorder.get(session)
            if recorder is not None:
                recorder.record_event("cart_navigation_failed", "cart_preparation", {
                    "page_url": current_url,
                })
            raise RuntimeError("Cart page was not reached.")

        browser.wait_for_timeout(2000)
        print("[CartPreparer] Cart page ready.")
