from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_session import PurchaseSession
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation

from purchase.services.sku_price_monitor import SkuPriceMonitor


URL = "https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321?xptdk=d3f1c8cb-7a25-4630-8899-5fcd76155d9b"


def main():

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=42720981321,
            url=URL,
        ),
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        quantity=1,
        auto_checkout=True,

        # Deliberately BELOW current price.
        # Current price is 1,599,000,000.
        target_price=1500000000,
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
        product_name="Apple Watch SE 3",
        shop_name="Test Shop",
        product_url=URL,
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

    print()
    print("========== STARTING CONTINUOUS SKU MONITOR ==========")
    print()

    try:

        monitor.monitor(
            session,
            poll_interval=5,
        )

    except KeyboardInterrupt:

        print()
        print("========== STOPPING TEST ==========")

        monitor.stop()

        print("[TEST] Continuous monitoring stopped manually.")


if __name__ == "__main__":
    main()