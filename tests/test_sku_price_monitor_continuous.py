from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference

from purchase.services.purchase_service import PurchaseService
from purchase.services.sku_price_monitor import SkuPriceMonitor


URL = (
    "https://shopee.ph/"
    "Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band"
    "-i.448087759.42720981321"
)


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

        # Current known price:
        # 1,599,000,000
        #
        # Target is deliberately above the current price
        # so the trigger should eventually fire.
        target_price=1600000000,
    )

    print()
    print(
        "========== PREPARING PURCHASE SESSION =========="
    )

    service = PurchaseService()

    session = service.prepare(
        request,
    )

    print()
    print(
        "========== PREPARED SESSION =========="
    )

    print(
        f"Product: "
        f"{session.product.product_name}"
    )

    print(
        f"Item ID: "
        f"{session.product.item_id}"
    )

    print(
        f"Shop ID: "
        f"{session.product.shop_id}"
    )

    print(
        f"Selected SKU: "
        f"{session.variation.name}"
    )

    print(
        f"Model ID: "
        f"{session.variation.model_id}"
    )

    print(
        f"Initial price: "
        f"{session.variation.price}"
    )

    print(
        f"Target price: "
        f"{session.request.target_price}"
    )

    print(
        f"Session status: "
        f"{session.status.value}"
    )

    print()
    print(
        "========== STARTING CONTINUOUS SKU MONITOR =========="
    )
    print()

    monitor = SkuPriceMonitor()

    try:

        monitor.monitor(
            session,
            poll_interval=5,
        )

    except KeyboardInterrupt:

        print()
        print(
            "========== STOPPING TEST =========="
        )

        monitor.stop()

        print(
            "[TEST] Continuous monitoring stopped manually."
        )


if __name__ == "__main__":
    main()
