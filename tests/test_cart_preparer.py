from purchase.execution.cart_preparer import CartPreparer

from purchase.models.product_info import ProductInfo
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.variation import Variation


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
            "Watch Size": "44MM M L",
        },
    )

    variation = Variation(
        model_id=198721540356,
        name="Midnight / 44MM M L",
        options={
            "Color": "Midnight",
            "Watch Size": "44MM M L",
        },
        price=17990.0,
        price_before_discount=19490.0,
        has_stock=True,
        tier_index=[0, 3],
        sku_image="",
    )

    product = ProductInfo(
        item_id=42720981321,
        shop_id=448087759,
        product_name="Apple Watch SE 3 GPS Aluminium Case Sport Band",
        shop_name="",
        product_url=reference.url,
        currency="PHP",
        image="ph-11134207-81zte-mf7vyfgtjtaid8",
        available_variations=[
            variation,
        ],
    )

    session = PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )

    preparer = CartPreparer()

    preparer.prepare(session)

    print()
    print("========== CART PREPARER ==========")
    print("Browser session:", session.browser_session is not None)

    if session.browser_session:
        print("URL:", session.browser_session.url)

    preparer.browser.close_session(preparer)


if __name__ == "__main__":
    main()