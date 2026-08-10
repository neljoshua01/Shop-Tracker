from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_session import PurchaseSession
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation

from purchase.services.sku_price_monitor import SkuPriceMonitor


def main():

    reference = ProductReference(
        shop_id=448087759,
        item_id=42720981321,
        url="https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321",
    )

    request = PurchaseRequest(
        reference=reference,
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        quantity=1,
        auto_checkout=True,
        target_price=1600000000,
    )

    variation = Variation(
        model_id=208721552326,
        name="Midnight,40MM S M",
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        price=1599000000,
        price_before_discount=1749000000,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )

    product = ProductInfo(
        item_id=42720981321,
        shop_id=448087759,
        product_name="Apple Watch SE 3 GPS Aluminium Case Sport Band",
        shop_name="Beyond the Box",
        product_url=reference.url,
        currency="PHP",
        image="",
        available_variations=[variation],
    )

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    monitor = SkuPriceMonitor()

    try:

        print()
        print("========== STARTING SKU MONITOR ==========")

        monitor.start(session)

        print()
        print("========== OPENING PRODUCT PAGE ==========")

        browser_session = monitor.browser.open_session(
            monitor,
            session.request.reference.url,
        )

        session.browser_session = browser_session

        print()
        print("========== WAITING FOR PURCHASE TRIGGER ==========")

        triggered = monitor.wait_for_trigger(
            timeout=30,
        )

        if not triggered:

            print(
                "[TEST] FAILED: "
                "Purchase trigger was not received."
            )

            return

        print()
        print("========== TRIGGER RECEIVED ==========")

        state = monitor.latest_state

        if state is None:

            print(
                "[TEST] FAILED: "
                "No SKU state available."
            )

            return

        print(
            f"Item ID: {state.item_id}"
        )

        print(
            f"Model ID: {state.model_id}"
        )

        print(
            f"SKU: {state.name}"
        )

        print(
            f"Price: {state.price}"
        )

        print(
            f"Target price: "
            f"{session.request.target_price}"
        )

        print()
        print(
            "[TEST] SUCCESS: "
            "SKU monitoring triggered the purchase pipeline."
        )

    finally:

        monitor.browser.close_session(monitor)
        monitor.stop()


if __name__ == "__main__":
    main()