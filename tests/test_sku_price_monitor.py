from purchase.services.sku_price_monitor import SkuPriceMonitor

from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation

from execution.browser.browser_connector import BrowserConnector


PRODUCT_URL = (
    "https://shopee.ph/"
    "Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band"
    "-i.448087759.42720981321"
)


def main():

    # =====================================================
    # Product reference
    # =====================================================

    reference = ProductReference(
        shop_id=448087759,
        item_id=42720981321,
        url=PRODUCT_URL,
    )

    # =====================================================
    # Purchase request
    # =====================================================

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

    # =====================================================
    # Selected variation
    # =====================================================

    variation = Variation(
        model_id=208721552326,
        name="Midnight,40MM S M",
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        price=1599.0,
        price_before_discount=1749.0,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )

    # =====================================================
    # Product
    # =====================================================

    product = ProductInfo(
        item_id=42720981321,
        shop_id=448087759,
        product_name=(
            "Apple Watch SE 3 GPS "
            "Aluminium Case Sport Band"
        ),
        shop_name="Beyond the Box",
        product_url=PRODUCT_URL,
        currency="PHP",
        image="",
        available_variations=[
            variation,
        ],
    )

    # =====================================================
    # Purchase session
    # =====================================================

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    # =====================================================
    # Browser
    # =====================================================

    browser = BrowserConnector()

    # =====================================================
    # Monitor
    # =====================================================

    monitor = SkuPriceMonitor()

    #
    # IMPORTANT:
    # Register the monitor BEFORE opening the page.
    #
    monitor.start(session)

    print()
    print(
        "========== OPENING PRODUCT PAGE =========="
    )

    # =====================================================
    # Open Shopee page
    # =====================================================

    browser_session = browser.open_session(
        monitor,
        PRODUCT_URL,
    )

    session.browser_session = browser_session

    print()
    print(
        "========== WAITING FOR LIVE get_pc =========="
    )

    # =====================================================
    # Wait for matching SKU
    # =====================================================

    received = monitor.updated.wait(
        timeout=15,
    )

    if not received:

        print(
            "[TEST] FAILED: "
            "No matching get_pc response received."
        )

        browser.close_session(monitor)
        monitor.stop()

        return

    # =====================================================
    # Read state
    # =====================================================

    state = monitor.latest_state

    if state is None:

        print(
            "[TEST] FAILED: "
            "Monitor signaled update "
            "but state is None."
        )

        browser.close_session(monitor)
        monitor.stop()

        return

    print()
    print(
        "========== LIVE SKU RESULT =========="
    )

    print(
        f"Item ID: "
        f"{state.item_id}"
    )

    print(
        f"Model ID: "
        f"{state.model_id}"
    )

    print(
        f"Name: "
        f"{state.name}"
    )

    print(
        f"Price: "
        f"{state.price}"
    )

    print(
        f"Price Before Discount: "
        f"{state.price_before_discount}"
    )

    print(
        f"Promotion ID: "
        f"{state.promotion_id}"
    )

    print(
        f"Promotion Types: "
        f"{state.promotion_types}"
    )

    print(
        "======================================"
    )

    # =====================================================
    # Validate
    # =====================================================

    assert state.item_id == 42720981321

    assert state.model_id == 208721552326

    assert state.name == "Midnight,40MM S M"

    print()
    print(
        "[TEST] SUCCESS: "
        "Live SKU monitoring works."
    )

    # =====================================================
    # Cleanup
    # =====================================================

    browser.close_session(monitor)

    monitor.stop()


if __name__ == "__main__":
    main()