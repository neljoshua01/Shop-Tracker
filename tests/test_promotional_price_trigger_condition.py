from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.models.trigger_condition import TriggerCondition


ITEM_ID = 40420862089
MODEL_ID = 276701523745


def make_session(target_price=1200000000):
    request = PurchaseRequest(
        reference=ProductReference(
            shop_id=1275798143,
            item_id=ITEM_ID,
            url="https://shopee.ph/",
        ),
        options={"Color": "Deep Blue", "Capacity": "256GB"},
        quantity=1,
        auto_checkout=True,
        target_price=target_price,
        trigger=TriggerCondition.PROMOTIONAL_PRICE_TARGET,
    )
    return PurchaseSession(
        request=request,
        product=None,
        variation=None,
    )


def make_state(
    price=7549000000,
    promotion_price=990000000,
    status="LIVE",
    deep_discount=True,
):
    return SkuPriceState(
        item_id=ITEM_ID,
        model_id=MODEL_ID,
        name="Deep Blue,256GB",
        price=price,
        price_before_discount=7990000000,
        promotion_id=487782888128821,
        promotion_types=(301, 0),
        deep_discount=deep_discount,
        promotion_price=promotion_price,
        promotion_event_status=status,
    )


def test_promotional_condition_requires_transactional_price_match():
    evaluator = PurchaseTriggerEvaluator()

    assert evaluator.evaluate(
        make_session(),
        make_state(),
    ) is False


def test_promotional_condition_triggers_when_transactional_price_matches_target():
    evaluator = PurchaseTriggerEvaluator()

    assert evaluator.evaluate(
        make_session(1200000000),
        make_state(
            price=990000000,
            promotion_price=990000000,
        ),
    ) is True


def test_promotional_condition_does_not_trigger_when_promotional_price_is_above_target():
    evaluator = PurchaseTriggerEvaluator()

    assert evaluator.evaluate(
        make_session(900000000),
        make_state(
            price=990000000,
            promotion_price=990000000,
        ),
    ) is False


def test_promotional_condition_requires_live_event():
    evaluator = PurchaseTriggerEvaluator()

    assert evaluator.evaluate(
        make_session(),
        make_state(
            price=990000000,
            promotion_price=990000000,
            status="UPCOMING",
        ),
    ) is False
