from purchase.execution.checkout_executor import CheckoutExecutor

from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation
from purchase.models.purchase_session import PurchaseSession

from execution.browser.browser_connector import BrowserConnector


PRODUCT_URL = (
    "https://shopee.ph/"
    "Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band"
    "-i.448087759.42720981321"
)


def main():

    print()
    print("========== CHECKOUT EXECUTOR TEST ==========")

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

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    browser = BrowserConnector()

    try:

        print()
        print("========== OPENING CART ==========")

        browser_session = browser.open_session(
            "test_checkout_executor",
            "https://shopee.ph/cart",
        )

        session.browser_session = browser_session

        print()
        print("========== RUNNING CHECKOUT EXECUTOR ==========")

        executor = CheckoutExecutor()

        success = executor.execute(
            session,
        )

        print()

        if success:

            print(
                "[TEST] SUCCESS: "
                "Checkout page reached."
            )

        else:

            print(
                "[TEST] FAILED: "
                "Checkout page was not reached."
            )

    finally:

        browser.close_session(
            "test_checkout_executor",
        )


if __name__ == "__main__":
    main()