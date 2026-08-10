from purchase.execution.purchase_trigger_evaluator import (
    PurchaseTriggerEvaluator,
)

from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.product_reference import ProductReference
from purchase.models.sku_price_state import SkuPriceState


def create_session(target_price):
    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=448087759,
            item_id=42720981321,
            url="https://shopee.ph/",
        ),
        options={
            "Color": "Midnight",
            "Watch Size": "40MM S M",
        },
        quantity=1,
        auto_checkout=True,
        target_price=target_price,
    )

    return PurchaseSession(
        request=request,
        product=None,
        variation=None,
    )


def create_state(price):
    return SkuPriceState(
        item_id=42720981321,
        model_id=208721552326,
        name="Midnight,40MM S M",
        price=price,
        price_before_discount=1749000000,
        promotion_id=486865010835789,
        promotion_types=(202, 0),
    )


def main():

    evaluator = PurchaseTriggerEvaluator()

    # =====================================================
    # 1. Price exactly reaches target
    # =====================================================

    print()
    print("========== TEST 1: TARGET REACHED ==========")

    session = create_session(1500000000)
    state = create_state(1500000000)

    result = evaluator.evaluate(session, state)

    assert result is True

    print("[TEST 1] PASS")


    # =====================================================
    # 2. Price goes below target
    # =====================================================

    print()
    print("========== TEST 2: PRICE BELOW TARGET ==========")

    session = create_session(1500000000)
    state = create_state(1400000000)

    result = evaluator.evaluate(session, state)

    assert result is True

    print("[TEST 2] PASS")


    # =====================================================
    # 3. Price remains above target
    # =====================================================

    print()
    print("========== TEST 3: PRICE ABOVE TARGET ==========")

    session = create_session(1500000000)
    state = create_state(1600000000)

    result = evaluator.evaluate(session, state)

    assert result is False

    print("[TEST 3] PASS")


    # =====================================================
    # 4. No target price configured
    # =====================================================

    print()
    print("========== TEST 4: NO TARGET PRICE ==========")

    session = create_session(None)
    state = create_state(1400000000)

    result = evaluator.evaluate(session, state)

    assert result is False

    print("[TEST 4] PASS")


    print()
    print("==============================================")
    print("ALL PURCHASE TRIGGER TESTS PASSED")
    print("==============================================")


if __name__ == "__main__":
    main()