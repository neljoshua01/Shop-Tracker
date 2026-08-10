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


SHOP_ID = 448087759
ITEM_ID = 42720981321
MODEL_ID = 208721552326

CHECKOUT_TOTAL = 1554000000
VALID_TARGET_PRICE = 1600000000
INVALID_TARGET_PRICE = 1500000000


def build_session(target_price):

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=SHOP_ID,
            item_id=ITEM_ID,
            url=PRODUCT_URL,
        ),
        options={
            "color": "Midnight",
            "watch_size": "40MM S M",
        },
        quantity=1,
        target_price=target_price,
        auto_checkout=True,
    )

    product = ProductInfo(
        item_id=ITEM_ID,
        shop_id=SHOP_ID,
        product_name="Apple Watch SE 3",
        shop_name="Apple Flagship Store",
        product_url=PRODUCT_URL,
        currency="PHP",
        image="",
        available_variations=[],
    )

    variation = Variation(
        model_id=MODEL_ID,
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

    return PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )


def main():

    print()
    print("========== CHECKOUT VERIFIER VALIDATION ==========")

    browser = BrowserConnector()

    session = build_session(
        VALID_TARGET_PRICE
    )

    try:

        # =================================================
        # OPEN CART
        # =================================================

        print()
        print("========== OPENING CART ==========")

        browser_session = browser.open_session(
            "test_checkout_verifier_validation",
            "https://shopee.ph/cart",
        )

        session.browser_session = browser_session

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] If Shopee shows a verification puzzle, solve it manually.")
        print("[TEST] Press ENTER to continue.")

        input()

        print()
        print("[TEST] Resuming validation test...")

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

        verifier = CheckoutVerifier()

        page = browser_session.page

        runtime = AsyncRuntime.instance()

        # =================================================
        # TEST 1 — PROTECTION
        # =================================================

        print()
        print("========== TEST 1: PROTECTION ==========")

        protection_ok = runtime.submit(
            verifier.disable_protection(
                page,
            )
        ).result(timeout=20)

        if not protection_ok:
            print()
            print("[TEST] FAILED: Protection could not be disabled.")
            return

        print()
        print("[TEST] PASS: Protection disabled.")

        # =================================================
        # TEST 2 — VALID PRICE
        # =================================================

        print()
        print("========== TEST 2: VALID PRICE ==========")

        session.request.target_price = VALID_TARGET_PRICE

        price_ok = runtime.submit(
            verifier.verify_price(
                page,
                session.request,
            )
        ).result(timeout=15)

        if not price_ok:
            print()
            print(
                "[TEST] FAILED: "
                "Valid price was rejected."
            )
            return

        print()
        print(
            "[TEST] PASS: "
            "Checkout price accepted."
        )

        # =================================================
        # TEST 3 — INVALID PRICE
        # =================================================

        print()
        print("========== TEST 3: INVALID PRICE ==========")

        session.request.target_price = INVALID_TARGET_PRICE

        invalid_price_ok = runtime.submit(
            verifier.verify_price(
                page,
                session.request,
            )
        ).result(timeout=15)

        if invalid_price_ok:
            print()
            print(
                "[TEST] FAILED: "
                "Price above target was accepted."
            )
            return

        print()
        print(
            "[TEST] PASS: "
            "Price above target was rejected."
        )

        # Restore valid target price
        session.request.target_price = VALID_TARGET_PRICE

        # =================================================
        # TEST 4 — PAYMENT
        # =================================================

        print()
        print("========== TEST 4: PAYMENT ==========")

        payment_ok = runtime.submit(
            verifier.select_payment(
                page,
            )
        ).result(timeout=30)

        if not payment_ok:
            print()
            print(
                "[TEST] FAILED: "
                "Payment validation failed."
            )
            return

        print()
        print(
            "[TEST] PASS: "
            f"Payment selected: {verifier.selected_payment}"
        )
        print()
        print("========== TEST 4A: VALID PAYMENT ==========")

        payment_valid = runtime.submit(
            verifier.verify_payment(
                "SPayLater",
            )
        ).result(timeout=15)

        if not payment_valid:

            print(
                "[TEST] FAIL: Expected payment was not selected."
            )

            return

        print(
            "[TEST] PASS: Correct payment method verified."
        )
        print()
        print("========== TEST 4B: INVALID PAYMENT ==========")

        payment_invalid = runtime.submit(
            verifier.verify_payment(
                "Cash on Delivery",
            )
        ).result(timeout=15)

        if payment_invalid:

            print(
                "[TEST] FAIL: Wrong payment method was accepted."
            )

            return

        print(
            "[TEST] PASS: Wrong payment method was rejected."
        )

        # =================================================
        # TEST 5 — ORDER SUMMARY
        # =================================================

        print()
        print("========== TEST 5: ORDER SUMMARY ==========")

        summary = runtime.submit(
            verifier.collect_order_summary(
                page,
            )
        ).result(timeout=15)

        if not summary:
            print()
            print(
                "[TEST] FAILED: "
                "Order summary was empty."
            )
            return

        print()
        print("[TEST] Order summary:")

        for key, value in summary.items():
            print(f"{key:12}: {value}")

        # Basic summary validation
        if summary.get("product") != "Apple Watch SE 3 (GPS) Sport Band":
            print()
            print(
                "[TEST] FAILED: "
                "Unexpected product."
            )
            return

        if summary.get("seller") != "Apple Flagship Store":
            print()
            print(
                "[TEST] FAILED: "
                "Unexpected seller."
            )
            return

        if summary.get("variation") != "Midnight,40mm S/M":
            print()
            print(
                "[TEST] FAILED: "
                "Unexpected variation."
            )
            return

        if summary.get("quantity") != 1:
            print()
            print(
                "[TEST] FAILED: "
                "Unexpected quantity."
            )
            return

        if summary.get("total") != 15540.0:
            print()
            print(
                "[TEST] FAILED: "
                "Unexpected checkout total."
            )
            return

        print()
        print("[TEST] PASS: Order summary validated.")

        # =================================================
        # TEST 6 — PLACE ORDER DETECTION
        # =================================================

        print()
        print("========== TEST 6: PLACE ORDER ==========")

        place_order_ok = runtime.submit(
            verifier.verify_place_order(
                page,
            )
        ).result(timeout=15)

        if not place_order_ok:
            print()
            print(
                "[TEST] FAILED: "
                "Place Order button not detected."
            )
            return

        print()
        print(
            "[TEST] PASS: "
            "Place Order button detected."
        )

        # =================================================
        # FINAL SAFETY CHECK
        # =================================================

        print()
        print("========== FINAL SAFETY CHECK ==========")

        print("[TEST] Place Order was NOT clicked.")
        print("[TEST] No purchase was submitted.")

        print()
        print(
            "========== "
            "CHECKOUT VERIFIER VALIDATION PASSED "
            "=========="
        )

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] Inspect the checkout page if needed.")
        print("[TEST] Press ENTER when finished.")

        input()

    except Exception as e:

        print()
        print("========== TEST ERROR ==========")
        print(
            f"[TEST] {type(e).__name__}: {e}"
        )

        print()
        print("========== BROWSER PAUSED ==========")
        print("[TEST] Browser will remain open.")
        print("[TEST] Inspect the browser before continuing.")
        print("[TEST] Press ENTER when finished.")

        input()

    finally:

        browser.close_session(
            "test_checkout_verifier_validation",
        )


if __name__ == "__main__":
    main()