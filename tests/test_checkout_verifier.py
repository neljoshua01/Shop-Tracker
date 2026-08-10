from typing_extensions import runtime

from purchase.execution.checkout_executor import CheckoutExecutor
from execution.checkout.checkout_verifier import CheckoutVerifier

from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation
from purchase.models.purchase_session import PurchaseSession
from core.runtime.async_runtime import AsyncRuntime

from execution.browser.browser_connector import BrowserConnector


PRODUCT_URL = (
    "https://shopee.ph/"
    "Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band"
    "-i.448087759.42720981321"
)


def main():

    print()
    print("========== CHECKOUT VERIFIER TEST ==========")

    # =====================================================
    # PURCHASE REQUEST
    # =====================================================

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=42720981321,
            url=PRODUCT_URL,
        ),
        options={
            "color": "Midnight",
            "watch_size": "40MM S M",
        },
        quantity=1,
        target_price=1600000000,
        auto_checkout=True,
    )

    # =====================================================
    # PRODUCT
    # =====================================================

    product = ProductInfo(
        item_id=42720981321,
        shop_id=448087759,
        product_name="Apple Watch SE 3",
        shop_name="Test Shop",
        product_url=PRODUCT_URL,
        currency="PHP",
        image="",
        available_variations=[],
    )

    # =====================================================
    # VARIATION
    # =====================================================

    variation = Variation(
        model_id=208721552326,
        name="Midnight,40MM S M",
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

    # =====================================================
    # PURCHASE SESSION
    # =====================================================

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    browser = BrowserConnector()

    try:

        # =================================================
        # OPEN CART
        # =================================================

        print()
        print("========== OPENING CART ==========")

        browser_session = browser.open_session(
            "test_checkout_verifier",
            "https://shopee.ph/cart",
        )

        session.browser_session = browser_session

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] If Shopee shows a verification puzzle, solve it manually.")
        print("[TEST] If no puzzle appears, press ENTER to continue.")

        input()

        print()
        print("[TEST] Resuming checkout verifier test...")

        print()
        print("========== CART OPENED ==========")
        print(f"[TEST] URL: {browser_session.url}")

        # =================================================
        # ENTER CHECKOUT
        # =================================================

        print()
        print("========== ENTERING CHECKOUT ==========")

        executor = CheckoutExecutor()

        checkout_success = executor.execute(
            session,
        )

        if not checkout_success:

            print()
            print("[TEST] FAILED: Could not reach checkout.")

            return

        print()
        print("[TEST] Checkout page reached.")

        # =================================================
        # CREATE VERIFIER
        # =================================================

        verifier = CheckoutVerifier()

        page = browser_session.page

        runtime = AsyncRuntime.instance()

        # =================================================
        # STEP 1: DISABLE PROTECTION
        # =================================================

        print()
        print("========== STEP 1: DISABLE PROTECTION ==========")

        protection_ok = runtime.submit(
            verifier.disable_protection(
                page,
            )
        ).result(timeout=20)

        if not protection_ok:

            print()
            print("[TEST] FAILED: Protection handling failed.")

            return

        print()
        print("[TEST] Protection verification passed.")

        #
        # Give Shopee time to recalculate the checkout total.
        #

        runtime.submit(
            page.wait_for_timeout(1500)
        ).result(timeout=5)


        # =================================================
        # STEP 2: VERIFY PRICE
        # =================================================

        print()
        print("========== STEP 2: VERIFY PRICE ==========")

        price_ok = runtime.submit(
            verifier.verify_price(
                page,
                request,
            )
        ).result(timeout=15)

        if not price_ok:

            print()
            print("[TEST] FAILED: Price verification failed.")

            return

        print()
        print("[TEST] Price verification passed.")


        # =================================================
        # SELECT PAYMENT
        # =================================================

        print()
        print("========== STEP 3: SELECT PAYMENT ==========")

        try:

            payment_ok = runtime.submit(
                verifier.select_payment(
                    page,
                )
            ).result(timeout=30)

        except Exception as e:

            print()
            print(
                "[TEST] FAILED: Payment selection raised "
                f"an exception: {e}"
            )

            return

        if not payment_ok:

            print()
            print("[TEST] FAILED: Payment selection failed.")
            return

        print()
        print(
            "[TEST] Payment selected: "
            f"{verifier.selected_payment}"
        )


        # =================================================
        # COLLECT ORDER SUMMARY
        # =================================================

        print()
        print("========== STEP 4: ORDER SUMMARY ==========")

        summary = runtime.submit(
            verifier.collect_order_summary(
                page,
            )
        ).result(timeout=15)

        print()
        print("[TEST] Order summary collected.")


        # =================================================
        # VERIFY PLACE ORDER
        # =================================================

        print()
        print("========== STEP 5: VERIFY PLACE ORDER ==========")

        place_order_ok = runtime.submit(
            verifier.verify_place_order(
                page,
            )
        ).result(timeout=15)

        if not place_order_ok:

            print()
            print(
                "[TEST] FAILED: "
                "Place Order button was not detected."
            )

            return

        print()
        print("[TEST] Place Order button detected.")


        # =================================================
        # FINAL SAFETY CHECK
        # =================================================

        print()
        print("========== FINAL SAFETY CHECK ==========")

        print("[TEST] Place Order was NOT clicked.")
        print("[TEST] No purchase was submitted.")

        print()
        print("========== CHECKOUT VERIFIER TEST PASSED ==========")

        # =================================================
        # MANUAL BROWSER PAUSE
        # =================================================

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] If Shopee shows a verification puzzle, solve it manually.")
        print("[TEST] If you want to inspect the checkout page, do so now.")
        print("[TEST] Press ENTER when finished.")

        input()

    except Exception as e:

        print()
        print("========== TEST ERROR ==========")
        print(f"[TEST] {type(e).__name__}: {e}")

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] If Shopee shows a verification puzzle, solve it manually.")
        print("[TEST] Inspect the browser before continuing.")
        print("[TEST] Press ENTER when finished.")

        input()

    finally:

        browser.close_session(
            "test_checkout_verifier",
        )

if __name__ == "__main__":
    main()