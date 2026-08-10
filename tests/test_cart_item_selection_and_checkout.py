from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation
from purchase.models.purchase_session import PurchaseSession

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions


CART_URL = "https://shopee.ph/cart"

PRODUCT_NAME = "Apple Watch SE 3"
PRODUCT_VARIATION = "Midnight,40MM S M"


def main():

    print()
    print("========== CART ITEM SELECTION + CHECKOUT TEST ==========")

    # =====================================================
    # TEST DATA
    # =====================================================

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=42720981321,
            url=(
                "https://shopee.ph/"
                "Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band"
                "-i.448087759.42720981321"
            ),
        ),
        options={
            "color": "Midnight",
            "watch_size": "40MM S M",
        },
        quantity=1,
        target_price=1600000000,
        auto_checkout=True,
    )

    product = ProductInfo(
        item_id=42720981321,
        shop_id=448087759,
        product_name=PRODUCT_NAME,
        shop_name="Test Shop",
        product_url=request.reference.url,
        currency="PHP",
        image="",
        available_variations=[],
    )

    variation = Variation(
        model_id=208721552326,
        name=PRODUCT_VARIATION,
        options={
            "color": "Midnight",
            "watch_size": "40MM S M",
        },
        price=1599000000,
        price_before_discount=1749000000,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    browser = BrowserConnector()

    try:

        # =====================================================
        # OPEN CART
        # =====================================================

        print()
        print("========== OPENING CART ==========")

        browser_session = browser.open_session(
            "test_cart_item_selection_and_checkout",
            CART_URL,
        )

        session.browser_session = browser_session

        actions = BrowserActions(
            browser_session,
        )

        page = browser_session.page

        print()
        print("========== CART OPENED ==========")
        print(
            f"[TEST] URL: {page.url}"
        )

        # =====================================================
        # WAIT FOR CART
        # =====================================================

        print()
        print("========== WAITING FOR CART UI ==========")

        actions.wait_for_timeout(3000)

        # =====================================================
        # FIND TARGET PRODUCT
        # =====================================================

        print()
        print("========== FINDING TARGET PRODUCT ==========")

        product_locator = actions.find_all(
            f"text={PRODUCT_NAME}"
        )

        product_count = actions.count(
            product_locator
        )

        print(
            f"[TEST] Product matches: {product_count}"
        )

        if product_count == 0:

            print(
                "[TEST] FAILED: "
                "Target product not found."
            )

            return

        product_element = actions.first(
            product_locator
        )

        print(
            "[TEST] Target product:",
            actions.text(product_element),
        )

        # =====================================================
        # FIND CART ITEM CONTAINER
        # =====================================================

        print()
        print("========== FINDING CART ITEM CONTAINER ==========")

        container = product_element
        found_container = None

        for level in range(1, 10):

            container = actions.parent(
                container
            )

            checkbox_locator = actions.find_all(
                "input[type='checkbox']",
                parent=container,
            )

            checkbox_count = actions.count(
                checkbox_locator
            )

            print(
                f"[TEST] Parent level {level}: "
                f"{checkbox_count} checkbox(es)"
            )

            if checkbox_count > 0:

                found_container = container

                print(
                    "[TEST] Cart item container found."
                )

                break

        if found_container is None:

            print(
                "[TEST] FAILED: "
                "Cart item container not found."
            )

            return

        # =====================================================
        # FIND CHECKBOX UI
        # =====================================================

        print()
        print("========== FINDING CHECKBOX UI ==========")

        checkbox = actions.find_all(
            "input[type='checkbox']",
            parent=found_container,
        )

        if actions.count(checkbox) == 0:

            print(
                "[TEST] FAILED: "
                "Checkbox not found."
            )

            return

        checkbox = actions.first(
            checkbox
        )

        checkbox_box = actions.find_all(
            ".stardust-checkbox__box",
            parent=found_container,
        )

        box_count = actions.count(
            checkbox_box
        )

        print(
            f"[TEST] Checkbox UI boxes found: {box_count}"
        )

        if box_count == 0:

            print(
                "[TEST] FAILED: "
                "Visible checkbox UI not found."
            )

            return

        checkbox_box = actions.first(
            checkbox_box
        )

        # =====================================================
        # SELECT ITEM
        # =====================================================

        print()
        print("========== SELECTING TARGET ITEM ==========")

        aria_before = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[TEST] aria-checked before:",
            aria_before,
        )

        if aria_before != "true":

            print(
                "[TEST] Clicking target item..."
            )

            actions.click(
                checkbox_box
            )

            actions.wait_for_timeout(1000)

        # =====================================================
        # VERIFY ITEM SELECTED
        # =====================================================

        print()
        print("========== VERIFYING ITEM SELECTION ==========")

        aria_after = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[TEST] aria-checked after:",
            aria_after,
        )

        if aria_after != "true":

            print(
                "[TEST] FAILED: "
                "Target item was not selected."
            )

            return

        print(
            "[TEST] Target item selected successfully."
        )

        # =====================================================
        # FIND CHECK OUT BUTTON
        # =====================================================

        print()
        print("========== FINDING CHECK OUT BUTTON ==========")

        checkout = actions.find_all(
            "button:has-text('Check Out')"
        )

        checkout_count = actions.count(
            checkout
        )

        print(
            f"[TEST] Check Out buttons found: "
            f"{checkout_count}"
        )

        if checkout_count == 0:

            print(
                "[TEST] FAILED: "
                "Check Out button not found."
            )

            return

        checkout = actions.first(
            checkout
        )

        print(
            "[TEST] Check Out button found."
        )

        # =====================================================
        # CLICK CHECK OUT
        # =====================================================

        print()
        print("========== CLICKING CHECK OUT ==========")

        actions.click(
            checkout
        )

        print(
            "[TEST] Check Out clicked."
        )

        # Give Shopee time to navigate/render checkout.
        actions.wait_for_timeout(3000)

        # =====================================================
        # VERIFY CHECKOUT
        # =====================================================

        print()
        print("========== VERIFYING CHECKOUT ==========")

        print(
            "[TEST] Current URL:",
            page.url,
        )

        print(
            "[TEST] Page title:",
            actions._submit(
                page.title(),
                timeout=10,
            ),
        )

        place_order = actions.find_all(
            "button:has-text('Place Order')"
        )

        place_order_count = actions.count(
            place_order
        )

        print(
            f"[TEST] Place Order buttons found: "
            f"{place_order_count}"
        )

        if place_order_count > 0:

            print()
            print(
                "========== CHECKOUT SUCCESS =========="
            )

            print(
                "[TEST] Target item was selected."
            )

            print(
                "[TEST] Check Out was clicked."
            )

            print(
                "[TEST] Checkout page reached."
            )

        else:

            print()
            print(
                "========== CHECKOUT NOT REACHED =========="
            )

            print(
                "[TEST] Target item was selected, "
                "but Place Order was not detected."
            )

            print(
                "[TEST] Current URL:",
                page.url,
            )

    finally:

        browser.close_session(
            "test_cart_item_selection_and_checkout"
        )


if __name__ == "__main__":
    main()