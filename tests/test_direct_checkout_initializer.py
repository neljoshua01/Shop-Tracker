from types import SimpleNamespace

import pytest

from purchase.execution.direct_checkout_initializer import DirectCheckoutInitializer
from purchase.models.execution_decision import ExecutionDecision
from purchase.models.ime_state import IMEState


def make_session():
    variation = SimpleNamespace(
        model_id=200,
        options={"Color": "Black", "Storage": "256GB"},
    )
    return SimpleNamespace(
        product=SimpleNamespace(item_id=100),
        variation=variation,
        request=SimpleNamespace(
            options={"Color": "Black", "Storage": "256GB"},
            quantity=2,
        ),
    )


def make_decision():
    return ExecutionDecision(
        item_id=100,
        model_id=200,
        variation_options=(("Color", "Black"), ("Storage", "256GB")),
        quantity=2,
        promotion_id=123,
        target_price=10000,
        execution_state=IMEState.EXECUTION_READY,
    )


def test_direct_checkout_initializer_accepts_exact_execution_context():
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    initializer._validate_decision(session, decision)


def test_direct_checkout_initializer_rejects_model_mismatch():
    session = make_session()
    decision = make_decision()
    decision = ExecutionDecision(
        item_id=decision.item_id,
        model_id=999,
        variation_options=decision.variation_options,
        quantity=decision.quantity,
        promotion_id=decision.promotion_id,
        target_price=decision.target_price,
        execution_state=decision.execution_state,
    )
    initializer = object.__new__(DirectCheckoutInitializer)

    with pytest.raises(ValueError, match="model_id"):
        initializer._validate_decision(session, decision)


def test_initialize_routes_to_direct_checkout_url(monkeypatch):
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    called = {}

    def fake_direct_url(_session, _decision):
        called["session"] = _session
        called["decision"] = _decision
        return True

    initializer.initialize_via_direct_url = fake_direct_url

    assert initializer.initialize(session, decision) is True
    assert called["session"] is session
    assert called["decision"] is decision
