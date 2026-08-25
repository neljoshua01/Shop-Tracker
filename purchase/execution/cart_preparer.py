"""
Prepares a purchase request by adding the requested
product, variation, and quantity to the Shopee cart.
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
        # 2. Select requested variation
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

        # -------------------------------------------------
        # 5. Apply requested quantity to the prepared item
        # -------------------------------------------------

        self._prepare_quantity(session)

        # -------------------------------------------------
        # Cart is now the prepared purchase state.
        #
        # Do NOT require exact product-name text matching
        # here. CheckoutExecutor performs the actual cart
        # item discovery when a purchase trigger occurs.
        # -------------------------------------------------

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

    def _prepare_quantity(
        self,
        session: PurchaseSession,
    ):
        """
        Make the prepared cart item's quantity match the
        Purchase Profile request.

        Add To Cart normally creates the item with quantity 1,
        so the existing cart quantity controls are used to reach
        the requested value without creating another cart flow.
        """

        requested_quantity = int(
            session.request.quantity
        )

        if requested_quantity < 1:
            raise ValueError(
                "Purchase quantity must be at least 1."
            )

        print(
            "[CartPreparer] "
            f"Preparing requested quantity: "
            f"{requested_quantity}"
        )

        browser = BrowserActions(
            session.browser_session,
        )

        target_container = self._find_target_cart_item(
            browser,
            session,
        )

        if target_container is None:
            raise RuntimeError(
                "Target cart item could not be resolved "
                "for quantity preparation."
            )

        quantity_input = self._find_quantity_input(
            browser,
            target_container,
        )

        if quantity_input is None:
            raise RuntimeError(
                "Target cart quantity input not found."
            )

        current_value = browser.attribute(
            quantity_input,
            "value",
        )

        try:
            current_quantity = int(
                current_value
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Target cart quantity could not be read."
            ) from exc

        print(
            "[CartPreparer] "
            f"Cart quantity before adjustment: "
            f"{current_quantity}"
        )

        if current_quantity < requested_quantity:

            controls = browser.find_all(
                "button[aria-label='Increase quantity']",
                parent=target_container,
            )

            control_count = browser.count(controls)

            if control_count == 0:
                raise RuntimeError(
                    "Increase quantity control not found."
                )

            increase_button = browser.first(controls)

            for _ in range(
                requested_quantity - current_quantity
            ):
                browser.click(increase_button)
                browser.wait_for_timeout(300)

        elif current_quantity > requested_quantity:

            controls = browser.find_all(
                "button[aria-label='Decrease quantity']",
                parent=target_container,
            )

            control_count = browser.count(controls)

            if control_count == 0:
                raise RuntimeError(
                    "Decrease quantity control not found."
                )

            decrease_button = browser.first(controls)

            for _ in range(
                current_quantity - requested_quantity
            ):
                browser.click(decrease_button)
                browser.wait_for_timeout(300)

        final_value = browser.attribute(
            quantity_input,
            "value",
        )

        try:
            final_quantity = int(
                final_value
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Target cart quantity could not be verified."
            ) from exc

        print(
            "[CartPreparer] "
            f"Cart quantity after adjustment: "
            f"{final_quantity}"
        )

        if final_quantity != requested_quantity:
            raise RuntimeError(
                "Prepared cart quantity does not match "
                f"requested quantity: expected "
                f"{requested_quantity}, got "
                f"{final_quantity}."
            )

        print(
            "[CartPreparer] "
            "Requested cart quantity verified."
        )

    def _find_target_cart_item(
        self,
        browser,
        session: PurchaseSession,
    ):
        """Resolve the cart container for the prepared product."""

        item_id = str(
            session.product.item_id
        )

        checkbox_inputs = browser.find_all(
            "input.stardust-checkbox__input"
        )

        checkbox_count = browser.count(
            checkbox_inputs
        )

        for index in range(checkbox_count):

            checkbox = checkbox_inputs.nth(index)
            current = checkbox

            for _ in range(8):

                current = browser.parent(
                    current
                )

                if current is None:
                    break

                identity_values = []

                for attribute_name in (
                    "data-item-id",
                    "data-model-id",
                    "data-product-id",
                    "data-sku-id",
                    "data-id",
                ):

                    value = browser.attribute(
                        current,
                        attribute_name,
                    )

                    if value:
                        identity_values.append(
                            str(value)
                        )

                identity_text = " ".join(
                    identity_values
                )

                container_text = browser.text(
                    current
                )

                if str(item_id) in identity_text or str(item_id) in container_text:
                    return current

        return None

    def _find_quantity_input(
        self,
        browser,
        target_container,
    ):
        """Find the cart quantity input associated with the target item."""

        quantity_inputs = browser.find_all(
            "input[aria-label='Quantity']",
            parent=target_container,
        )

        if browser.count(quantity_inputs) > 0:
            return browser.first(quantity_inputs)

        # Shopee has rendered the quantity control without a stable
        # aria-label in some cart layouts. Prefer an input whose value
        # is numeric and whose surrounding container exposes the
        # existing Increase/Decrease controls.
        inputs = browser.find_all(
            "input",
            parent=target_container,
        )

        input_count = browser.count(inputs)

        for index in range(input_count):

            candidate = inputs.nth(index)
            value = browser.attribute(
                candidate,
                "value",
            )

            if value is None or not str(value).isdigit():
                continue

            parent = browser.parent(
                candidate
            )

            increase = browser.find_all(
                "button[aria-label='Increase quantity']",
                parent=parent,
            )

            decrease = browser.find_all(
                "button[aria-label='Decrease quantity']",
                parent=parent,
            )

            if (
                browser.count(increase) > 0
                or browser.count(decrease) > 0
            ):
                return candidate

        return None
