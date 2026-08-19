import time

from purchase.execution.purchase_trigger_evaluator import (
    PurchaseTriggerEvaluator,
)
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.parser.sku_price_parser import SkuPriceParser


MODEL_ID = 253939254333
ITEM_ID = 42720981321
TARGET_PRICE = 1000000000
PDP_PRICE = 1599000000
PROMOTION_PRICE = 880000000


def create_session():

    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=ITEM_ID,
            url="https://shopee.ph/",
        ),
        options={},
        quantity=1,
        auto_checkout=True,
        target_price=TARGET_PRICE,
    )

    return PurchaseSession(
        request=request,
        product=None,
        variation=None,
    )


def create_payload(
    start_time=None,
    end_time=None,
):

    model = {
        "model_id": MODEL_ID,
        "item_id": ITEM_ID,
        "name": "Nano [128GB]",
        "price": PDP_PRICE,
        "price_before_discount": 1839000000,
        "price_stocks": [],
    }

    payload = {
        "data": {
            "item": {
                "models": [
                    model,
                ]
            },
            "bottom_banner": {},
        }
    }

    if start_time is not None:

        payload["data"]["bottom_banner"][
            "deep_discount"
        ] = {
            "promotion_id": 888888,
            "is_lpp": True,
            "promotion_price": {
                "single_value": PROMOTION_PRICE,
            },
            "skin": {
                "pre_hype_text": "9.9 Mega Sale",
            },
            "reminder_event": {
                "item_id": ITEM_ID,
                "shop_id": 448087759,
                "item_name": "Test Product",
                "start_time": start_time,
                "end_time": end_time,
            },
        }

    return payload


def run_test(
    label,
    payload,
    expected,
):

    parser = SkuPriceParser()
    evaluator = PurchaseTriggerEvaluator()
    session = create_session()

    state = parser.parse(
        payload,
        model_id=MODEL_ID,
    )

    assert state is not None

    result = evaluator.evaluate(
        session,
        state,
    )

    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

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
        f"{session.request.target_price}"
    )

    print(
        f"Expected Trigger:    "
        f"{expected}"
    )

    print(
        f"Actual Trigger:      "
        f"{result}"
    )

    assert result is expected

    print("PASS")


def main():

    now = int(time.time())

    #
    # ==================================================
    # 1. INACTIVE
    # ==================================================
    #

    run_test(
        "TEST 1: PROMOTION INACTIVE",

        create_payload(),

        False,
    )

    #
    # ==================================================
    # 2. UPCOMING
    # ==================================================
    #

    run_test(
        "TEST 2: DEEP DISCOUNT UPCOMING",

        create_payload(
            start_time=now + 300,
            end_time=now + 900,
        ),

        False,
    )

    #
    # ==================================================
    # 3. LIVE
    # ==================================================
    #

    run_test(
        "TEST 3: DEEP DISCOUNT LIVE",

        create_payload(
            start_time=now - 60,
            end_time=now + 600,
        ),

        True,
    )

    #
    # ==================================================
    # 4. ENDED
    # ==================================================
    #

    run_test(
        "TEST 4: DEEP DISCOUNT ENDED",

        create_payload(
            start_time=now - 900,
            end_time=now - 60,
        ),

        False,
    )

    print()
    print("#" * 100)
    print("SKU PRICE PROMOTION TRIGGER INTEGRATION PASSED")
    print("#" * 100)


if __name__ == "__main__":
    main()