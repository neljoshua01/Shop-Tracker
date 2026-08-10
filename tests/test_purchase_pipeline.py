from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation


PRODUCT_URL = "https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321?xptdk=d3f1c8cb-7a25-4630-8899-5fcd76155d9b"


def main():

    reference = ProductReference(
        shop_id=448087759,
        item_id=42720981321,
        url=PRODUCT_URL,
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
        product_url=PRODUCT_URL,
        currency="PHP",
        image="",
        available_variations=[variation],
    )

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    pipeline = PurchasePipeline()

    print()
    print("========== RUNNING PURCHASE PIPELINE ==========")

    result = pipeline.run(
        session,
    )

    print()

    if result:

        print(
            "[TEST] SUCCESS: "
            "Purchase pipeline reached checkout handoff."
        )

    else:

        print(
            "[TEST] FAILED: "
            "Purchase pipeline did not reach checkout handoff."
        )


if __name__ == "__main__":
    main()