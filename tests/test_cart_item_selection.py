from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation
from purchase.models.purchase_session import PurchaseSession

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions


CART_URL = "https://shopee.ph/cart"

TARGET_PRODUCT = "Apple Watch SE 3"
TARGET_VARIATION = "Midnight,40MM S M"


def main():

    print()
    print("========== CART ITEM SELECTION TEST ==========")

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
        product_name=TARGET_PRODUCT,
        shop_name="Test Shop",
        product_url=request.reference.url,
        currency="PHP",
        image="",
        available_variations=[],
    )

    variation = Variation(
        model_id=208721552326,
        name=TARGET_VARIATION,
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
            "test_cart_item_selection",
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
        # FIND PRODUCT TEXT
        # =====================================================

        print()
        print("========== SEARCHING FOR TARGET PRODUCT ==========")

        product_locator = actions.find_all(
            f"text={TARGET_PRODUCT}"
        )

        product_count = actions.count(
            product_locator
        )

        print(
            f"[TEST] Product matches: "
            f"{product_count}"
        )

        if product_count == 0:

            print(
                "[TEST] FAILED: "
                "Target product not found."
            )

            return

        # =====================================================
        # INSPECT PRODUCT MATCH
        # =====================================================

        product_element = actions.first(
            product_locator
        )

        print()
        print("========== TARGET PRODUCT ==========")

        print(
            "[TEST] Text:",
            actions.text(product_element),
        )

        print(
            "[TEST] Class:",
            actions.attribute(
                product_element,
                "class",
            ),
        )

        # =====================================================
        # FIND CART ITEM CONTAINER
        # =====================================================

        print()
        print("========== FINDING CART ITEM CONTAINER ==========")

        #
        # Walk upward until we find a container
        # containing a checkbox.
        #
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

            print()
            print(
                "[TEST] FAILED: "
                "Could not find cart item checkbox."
            )

            return

        # =====================================================
        # INSPECT CHECKBOX
        # =====================================================

        print()
        print("========== CHECKBOX INSPECTION ==========")

        checkbox = actions.find_all(
            "input[type='checkbox']",
            parent=found_container,
        )

        checkbox_count = actions.count(
            checkbox
        )

        print(
            f"[TEST] Checkbox count: "
            f"{checkbox_count}"
        )

        if checkbox_count == 0:

            print(
                "[TEST] FAILED: "
                "No checkbox found."
            )

            return

        checkbox = actions.first(
            checkbox
        )

        checked_attribute = actions.attribute(
            checkbox,
            "checked",
        )

        aria_checked = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[TEST] checked attribute:",
            checked_attribute,
        )

        print(
            "[TEST] aria-checked:",
            aria_checked,
        )

        print(
            "[TEST] Checkbox class:",
            actions.attribute(
                checkbox,
                "class",
            ),
        )

        # =====================================================
        # INSPECT CONTAINER HTML
        # =====================================================

        print()
        print("========== CART ITEM CONTAINER ==========")

        html = actions._submit(
            found_container.evaluate(
                "(el) => el.outerHTML"
            ),
            timeout=10,
        )

        print(
            html[:10000]
        )

        # =====================================================
        # SELECT ITEM
        # =====================================================

        print()
        print("========== SELECTING TARGET ITEM ==========")

        print("[TEST] Inspecting checkbox UI...")

        checkbox_parent = actions.parent(
            checkbox
        )

        print(
            "[TEST] Checkbox parent class:",
            actions.attribute(
                checkbox_parent,
                "class",
            ),
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
                "Could not find visible checkbox UI."
            )

            return

        checkbox_box = actions.first(
            checkbox_box
        )

        print(
            "[TEST] Checkbox UI class:",
            actions.attribute(
                checkbox_box,
                "class",
            ),
        )

        print()
        print("[TEST] Clicking visible checkbox UI...")

        actions.click(
            checkbox_box
        )

        print(
            "[TEST] Checkbox UI clicked."
        )

        actions.wait_for_timeout(1000)
        # =====================================================
        # VERIFY SELECTION
        # =====================================================

        print()
        print("========== VERIFYING SELECTION ==========")

        checked_after = actions.attribute(
            checkbox,
            "checked",
        )

        aria_checked_after = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[TEST] checked attribute after:",
            checked_after,
        )

        print(
            "[TEST] aria-checked after:",
            aria_checked_after,
        )

        #
        # Inspect the parent HTML again because Shopee may
        # represent selection through classes rather than
        # the native checked attribute.
        #
        html_after = actions._submit(
            found_container.evaluate(
                "(el) => el.outerHTML"
            ),
            timeout=10,
        )

        print()
        print("========== CART ITEM HTML AFTER SELECTION ==========")

        print(
            html_after[:10000]
        )

        # =====================================================
        # RESULT
        # =====================================================

        if (
            checked_after is not None
            or aria_checked_after == "true"
        ):

            print()
            print(
                "========== SELECTION SUCCESS =========="
            )

            print(
                "[TEST] Target cart item is selected."
            )

        else:

            print()
            print(
                "========== SELECTION STATE UNCLEAR =========="
            )

            print(
                "[TEST] Checkbox was clicked, "
                "but Shopee does not expose selection "
                "through the inspected attributes."
            )

            print(
                "[TEST] Use the HTML above to identify "
                "the actual selected-state indicator."
            )

    finally:

        browser.close_session(
            "test_cart_item_selection"
        )


if __name__ == "__main__":
    main()