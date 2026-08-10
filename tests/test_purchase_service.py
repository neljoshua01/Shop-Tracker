from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.services.purchase_service import PurchaseService


def main():

    service = PurchaseService()

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=42720981321,
            url="https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321",
        ),
        options={
            "Color": "Midnight",
            "Watch Size": "44MM M L",
        },
    )

    session = service.prepare(request)

    print()
    print("========== SESSION ==========")
    print(session.product.product_name)
    print(session.variation.name)
    print(session.variation.model_id)
    print(session.status.value)


if __name__ == "__main__":
    main()