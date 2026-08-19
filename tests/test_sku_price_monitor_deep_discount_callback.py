import asyncio

from purchase.models.purchase_request import PurchaseRequest
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_session import PurchaseSession
from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation

from purchase.services.sku_price_monitor import SkuPriceMonitor


ITEM_ID = 42720981321
SHOP_ID = 448087759
MODEL_ID = 208721552326


class FakeResponse:

    def __init__(self, data):

        self.url = (
            "https://shopee.ph/"
            "api/v4/pdp/get_pc"
        )

        self._data = data

    async def json(self):

        return self._data


def create_session():

    reference = ProductReference(
        shop_id=SHOP_ID,
        item_id=ITEM_ID,
        url="https://shopee.ph/",
    )

    request = PurchaseRequest(
        reference=reference,
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        quantity=1,
        auto_checkout=True,
        target_price=1000000000,
    )

    variation = Variation(
        model_id=MODEL_ID,
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
        item_id=ITEM_ID,
        shop_id=SHOP_ID,
        product_name=(
            "Apple Watch SE 3 GPS "
            "Aluminium Case Sport Band"
        ),
        shop_name="Beyond the Box",
        product_url=reference.url,
        currency="PHP",
        image="",
        available_variations=[
            variation,
        ],
    )

    return PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )


def base_api_data():

    return {
        "data": {
            "item": {
                "item_id": ITEM_ID,
                "models": [
                    {
                        "item_id": ITEM_ID,
                        "model_id": MODEL_ID,
                        "name": "Midnight,40MM S M",
                        "price": 1599000000,
                        "price_before_discount": 1749000000,
                        "price_stocks": [],
                    }
                ],
            },
            "bottom_banner": {},
        }
    }


def make_deep_discount_data(
    start_time,
    end_time,
):

    data = base_api_data()

    data["data"]["bottom_banner"][
        "deep_discount"
    ] = {
        "promotion_id": 486865010835789,
        "is_lpp": False,
        "promotion_price": {
            "single_value": 880000000,
        },
        "skin": {
            "pre_hype_text": (
                "880000000 ON AUG 8, 6PM"
            ),
        },
        "reminder_event": {
            "item_id": ITEM_ID,
            "shop_id": SHOP_ID,
            "item_name": (
                "Apple Watch SE 3 GPS "
                "Aluminium Case Sport Band"
            ),
            "start_time": start_time,
            "end_time": end_time,
        },
    }

    return data


def make_inactive_data():

    return base_api_data()


async def process(
    monitor,
    data,
):

    await monitor.on_response(
        FakeResponse(data)
    )


def run_test(
    label,
    data,
    expected_event,
    expected_trigger,
    monitor,
):

    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

    monitor.triggered.clear()
    monitor.updated.clear()

    asyncio.run(
        process(
            monitor,
            data,
        )
    )

    state = monitor.latest_state

    if state is None:

        print(
            "[TEST] FAILED: "
            "No SKU state produced."
        )

        return False

    print(
        f"Deep Discount:       "
        f"{state.deep_discount}"
    )

    print(
        f"Promotion Price:     "
        f"{state.promotion_price}"
    )

    print(
        f"Event Status:        "
        f"{state.promotion_event_status}"
    )

    print(
        f"PDP Price:           "
        f"{state.price}"
    )

    print(
        f"Target Price:        "
        f"{monitor.session.request.target_price}"
    )

    print(
        f"Expected Event:      "
        f"{expected_event}"
    )

    print(
        f"Actual Event:        "
        f"{state.promotion_event_status}"
    )

    print(
        f"Expected Trigger:    "
        f"{expected_trigger}"
    )

    print(
        f"Actual Trigger:      "
        f"{monitor.triggered.is_set()}"
    )

    assert (
        state.promotion_event_status
        == expected_event
    )

    assert (
        monitor.triggered.is_set()
        == expected_trigger
    )

    print("PASS")

    return True


def main():

    session = create_session()

    monitor = SkuPriceMonitor()

    monitor.session = session

    #
    # Use deterministic timestamps.
    #
    import time

    now = int(time.time())

    #
    # ==================================================
    # TEST 1 — PROMOTION INACTIVE
    # ==================================================
    #

    result = run_test(
        "TEST 1: PROMOTION INACTIVE",
        make_inactive_data(),
        expected_event="NO_EVENT",
        expected_trigger=False,
        monitor=monitor,
    )

    assert result

    #
    # ==================================================
    # TEST 2 — PROMOTION UPCOMING
    # ==================================================
    #

    result = run_test(
        "TEST 2: DEEP DISCOUNT UPCOMING",
        make_deep_discount_data(
            start_time=now + 300,
            end_time=now + 900,
        ),
        expected_event="UPCOMING",
        expected_trigger=False,
        monitor=monitor,
    )

    assert result

    #
    # ==================================================
    # TEST 3 — PROMOTION LIVE
    # ==================================================
    #

    result = run_test(
        "TEST 3: DEEP DISCOUNT LIVE",
        make_deep_discount_data(
            start_time=now - 60,
            end_time=now + 600,
        ),
        expected_event="LIVE",
        expected_trigger=True,
        monitor=monitor,
    )

    assert result

    #
    # ==================================================
    # TEST 4 — PROMOTION ENDED
    # ==================================================
    #

    monitor.triggered.clear()

    result = run_test(
        "TEST 4: DEEP DISCOUNT ENDED",
        make_deep_discount_data(
            start_time=now - 900,
            end_time=now - 60,
        ),
        expected_event="ENDED",
        expected_trigger=False,
        monitor=monitor,
    )

    assert result

    print()
    print("#" * 100)
    print(
        "SKU PRICE MONITOR DEEP DISCOUNT "
        "CALLBACK PASSED"
    )
    print("#" * 100)


if __name__ == "__main__":
    main()