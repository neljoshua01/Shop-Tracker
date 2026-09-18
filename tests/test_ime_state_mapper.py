from types import SimpleNamespace

from purchase.models.execution_decision import ExecutionDecision
from purchase.models.ime_state import IMEState
from purchase.models.sku_price_state import SkuPriceState
from purchase.services.ime_state_mapper import IMEStateMapper


def make_state(**overrides):
    values = {
        "item_id": 100,
        "model_id": 200,
        "name": "Test SKU",
        "price": 9900,
        "price_before_discount": 19900,
        "promotion_id": 123,
        "promotion_types": (1,),
        "promotion_detected": True,
        "promotion_evidence": ("test",),
        "deep_discount": True,
        "promotion_price": 9900,
        "promotion_event_status": "LIVE",
        "promotion_seconds_until_start": 0,
        "promotion_seconds_until_end": 60,
        "promotion_skin": None,
        "promotion_reminder_event": None,
        "promotion_is_lpp": True,
        "has_stock": True,
        "cookie_integrity": True,
    }
    values.update(overrides)
    return SkuPriceState(**values)


def make_session(target_price=10000):
    return SimpleNamespace(
        request=SimpleNamespace(target_price=target_price),
    )


def test_live_promotion_with_valid_session_reaches_session_valid():
    state = make_state()
    session = make_session()

    assert IMEStateMapper().map(session, state) is IMEState.SESSION_VALID


def test_trigger_reached_with_valid_session_reaches_execution_ready():
    state = make_state()
    session = make_session()

    assert (
        IMEStateMapper().map(session, state, trigger_reached=True)
        is IMEState.EXECUTION_READY
    )


def test_stock_without_valid_session_is_sku_available():
    state = make_state(cookie_integrity=False)
    session = make_session()

    assert IMEStateMapper().map(session, state) is IMEState.SKU_AVAILABLE


def test_live_promotion_without_stock_or_valid_session_is_promotion_live():
    state = make_state(has_stock=False, cookie_integrity=False)
    session = make_session()

    assert IMEStateMapper().map(session, state) is IMEState.PROMOTION_LIVE


def test_no_promotion_no_stock_no_session_is_price_observed():
    state = make_state(
        has_stock=False,
        cookie_integrity=False,
        promotion_event_status="NO_EVENT",
    )
    session = make_session()

    assert IMEStateMapper().map(session, state) is IMEState.PRICE_OBSERVED


def test_execution_decision_carries_exact_observed_context():
    state = make_state()
    session = make_session(target_price=10000)

    decision = IMEStateMapper().build_execution_decision(session, state)

    assert isinstance(decision, ExecutionDecision)
    assert decision.item_id == 100
    assert decision.model_id == 200
    assert decision.promotion_id == 123
    assert decision.target_price == 10000
    assert decision.execution_state is IMEState.EXECUTION_READY
