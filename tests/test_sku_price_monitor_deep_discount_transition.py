import time

from purchase.execution.purchase_trigger_evaluator import (
    PurchaseTriggerEvaluator,
)
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.parser.sku_price_parser import SkuPriceParser


ITEM_ID = 42720981321
MODEL_ID = 208721552326

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

    payload = {
        "data": {
            "item": {
                "models": [
                    {
                        "item_id": ITEM_ID,
                        "model_id": MODEL_ID,
                        "name": "Midnight,40MM S M",
                        "price": PDP_PRICE,
                        "price_before_discount": 1749000000,
                        "price_stocks": [],
                    }
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
                "item_name": "Apple Watch SE 3 GPS Aluminium Case Sport Band",
                "start_time": start_time,
                "end_time": end_time,
            },
        }

    return payload


def process_state(
    label,
    payload,
    session,
    parser,
    evaluator,
    expected_status,
    expected_trigger,
):

    state = parser.parse(
        payload,
        model_id=MODEL_ID,
    )

    assert state is not None

    trigger = evaluator.evaluate(
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
        f"Expected Event:      "
        f"{expected_status}"
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
        f"{trigger}"
    )

    assert (
        state.promotion_event_status
        == expected_status
    )

    assert trigger is expected_trigger

    print("PASS")

    return state


def main():

    now = int(time.time())

    parser = SkuPriceParser()
    evaluator = PurchaseTriggerEvaluator()
    session = create_session()

    #
    # ==================================================
    # STATE 1 — INACTIVE
    # ==================================================
    #

    inactive = process_state(
        label="TEST 1: PROMOTION INACTIVE",
        payload=create_payload(),
        session=session,
        parser=parser,
        evaluator=evaluator,
        expected_status="NO_EVENT",
        expected_trigger=False,
    )

    #
    # ==================================================
    # STATE 2 — UPCOMING
    # ==================================================
    #

    upcoming = process_state(
        label="TEST 2: DEEP DISCOUNT UPCOMING",
        payload=create_payload(
            start_time=now + 300,
            end_time=now + 900,
        ),
        session=session,
        parser=parser,
        evaluator=evaluator,
        expected_status="UPCOMING",
        expected_trigger=False,
    )

    #
    # ==================================================
    # STATE 3 — LIVE
    # ==================================================
    #

    live = process_state(
        label="TEST 3: DEEP DISCOUNT LIVE",
        payload=create_payload(
            start_time=now - 60,
            end_time=now + 600,
        ),
        session=session,
        parser=parser,
        evaluator=evaluator,
        expected_status="LIVE",
        expected_trigger=True,
    )

    #
    # ==================================================
    # STATE 4 — ENDED
    # ==================================================
    #

    ended = process_state(
        label="TEST 4: DEEP DISCOUNT ENDED",
        payload=create_payload(
            start_time=now - 900,
            end_time=now - 60,
        ),
        session=session,
        parser=parser,
        evaluator=evaluator,
        expected_status="ENDED",
        expected_trigger=False,
    )

    #
    # ==================================================
    # STATE TRANSITIONS
    # ==================================================
    #

    transitions = [
        (
            inactive.promotion_event_status,
            upcoming.promotion_event_status,
        ),
        (
            upcoming.promotion_event_status,
            live.promotion_event_status,
        ),
        (
            live.promotion_event_status,
            ended.promotion_event_status,
        ),
    ]

    print()
    print("#" * 100)
    print("DEEP DISCOUNT TRANSITIONS")
    print("#" * 100)

    for old_state, new_state in transitions:

        print(
            f"{old_state} -> {new_state}"
        )

    assert transitions == [
        (
            "NO_EVENT",
            "UPCOMING",
        ),
        (
            "UPCOMING",
            "LIVE",
        ),
        (
            "LIVE",
            "ENDED",
        ),
    ]

    print()
    print("#" * 100)
    print("SKU PRICE MONITOR DEEP DISCOUNT TRANSITION PASSED")
    print("#" * 100)


if __name__ == "__main__":
    main()