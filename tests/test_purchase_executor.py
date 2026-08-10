from purchase.execution.purchase_executor import PurchaseExecutor
from purchase.services.purchase_service import PurchaseService

from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest


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

    service = PurchaseService()
    session = service.prepare(request)

    executor = PurchaseExecutor()
    executor.execute(session)

    print()

    print("========== EXECUTION ==========")
    print(session.browser_session is not None)
    print(session.browser_session.page.url)

    executor.close()


if __name__ == "__main__":
    main()