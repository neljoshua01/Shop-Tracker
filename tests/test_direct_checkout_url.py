from types import SimpleNamespace

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


def test_experimental_direct_checkout_url_is_built_from_verified_execution_context():
    initializer = object.__new__(DirectCheckoutInitializer)

    url = initializer.build_direct_checkout_url(
        make_session(),
        make_decision(),
    )

    assert url == (
        "https://shopee.ph/checkout"
        "?buy_now=true&item_id=100&model_id=200&quantity=2"
    )


def test_experimental_direct_checkout_url_navigates_without_place_order(monkeypatch):
    initializer = object.__new__(DirectCheckoutInitializer)
    session = make_session()
    decision = make_decision()

    navigated = {}

    class FakeActions:
        def __init__(self, _session):
            pass

        def goto(self, url, wait_until="domcontentloaded", timeout=30000):
            navigated["url"] = url
            navigated["wait_until"] = wait_until

    monkeypatch.setattr(
        "purchase.execution.direct_checkout_initializer.BrowserActions",
        FakeActions,
    )

    session.browser_session = SimpleNamespace(
        page=SimpleNamespace(
            url="https://shopee.ph/checkout?buy_now=true&item_id=100&model_id=200&quantity=2"
        )
    )

    assert initializer.initialize_via_direct_url(session, decision) is True
    assert navigated["url"] == (
        "https://shopee.ph/checkout"
        "?buy_now=true&item_id=100&model_id=200&quantity=2"
    )
    assert navigated["wait_until"] == "domcontentloaded"
