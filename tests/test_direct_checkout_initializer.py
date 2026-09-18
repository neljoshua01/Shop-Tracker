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


def test_initialize_clicks_visible_buy_now_with_playwright(monkeypatch):
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    captured = {}

    class FakePage:
        url = "https://shopee.ph/checkout"

    class FakeActions:
        def __init__(self, _session):
            pass

        def capture_pdp_purchase_controls(self, labels, timeout=10000):
            captured["diagnostic_labels"] = labels
            captured["diagnostic_timeout"] = timeout
            return [{"tag": "BUTTON", "text": "Buy Now", "visible": True}]

        def click_visible_button_by_labels(self, labels, timeout=10000, **kwargs):
            captured["labels"] = labels
            captured["timeout"] = timeout
            captured["click_kwargs"] = kwargs
            return {"found": True, "clicked": True, "text": "Buy Now"}

        def wait_for_url(self, url, timeout=10000):
            captured["wait_for_url"] = (url, timeout)

    monkeypatch.setattr(
        "purchase.execution.direct_checkout_initializer.BrowserActions",
        FakeActions,
    )

    initializer._open_product = lambda _session: None
    session.browser_session = SimpleNamespace(page=FakePage())

    selection_calls = []

    class FakeVariationSelector:
        def select(self, selected_session):
            selection_calls.append(selected_session)

    initializer.variation_selector = FakeVariationSelector()

    assert initializer.initialize(session, decision) is True
    assert selection_calls == [session]
    assert captured["diagnostic_labels"] == ["buy now", "bilihin na", "buy with voucher", "add to cart"]
    assert captured["diagnostic_timeout"] == 10000
    assert captured["labels"] == ["buy now", "bilihin na", "buy with voucher"]
    assert captured["click_kwargs"] == {}



def test_initialize_continues_buy_now_cart_handoff_to_checkout(monkeypatch):
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    captured = {}

    class FakePage:
        url = "https://shopee.ph/cart"

    class FakeActions:
        def __init__(self, _session):
            self.page = session.browser_session.page

        def capture_pdp_purchase_controls(self, labels, timeout=10000):
            captured.setdefault("diagnostics", []).append(labels)
            return [{"tag": "BUTTON", "text": labels[0], "visible": True}]

        def click_visible_button_by_labels(self, labels, timeout=10000):
            captured.setdefault("clicks", []).append(labels)
            if labels[0] == "buy now":
                return {
                    "found": True,
                    "clicked": True,
                    "text": "Buy Now",
                    "navigations": [
                        "https://shopee.ph/cart?itemKeys=100.200.&shopId=300"
                    ],
                }
            captured["checkout_kwargs"] = kwargs
            self.page.url = "https://shopee.ph/checkout"
            return {
                "found": True,
                "clicked": True,
                "text": "Check Out",
                "navigations": ["https://shopee.ph/checkout"],
                "url_wait_satisfied": True,
                "url_wait_error": None,
            }

        def wait_for_url(self, url, timeout=10000):
            captured.setdefault("waits", []).append((url, timeout))

    monkeypatch.setattr(
        "purchase.execution.direct_checkout_initializer.BrowserActions",
        FakeActions,
    )

    initializer._open_product = lambda _session: None
    session.browser_session = SimpleNamespace(page=FakePage())

    class FakeVariationSelector:
        def select(self, selected_session):
            captured["variation_session"] = selected_session

    initializer.variation_selector = FakeVariationSelector()

    assert initializer.initialize(session, decision) is True
    assert captured["variation_session"] is session
    assert captured["clicks"][0] == ["buy now", "bilihin na", "buy with voucher"]
    assert captured["clicks"][1] == ["check out", "checkout", "proceed to checkout"]
    assert captured["checkout_kwargs"] == {
        "wait_for_url": "**/checkout**",
        "navigation_timeout": 15000,
    }
    assert "waits" not in captured


def test_initialize_rejects_buy_now_cart_identity_mismatch(monkeypatch):
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    class FakePage:
        url = "https://shopee.ph/cart"

    class FakeActions:
        def __init__(self, _session):
            pass

        def capture_pdp_purchase_controls(self, labels, timeout=10000):
            return []

        def click_visible_button_by_labels(self, labels, timeout=10000):
            return {
                "found": True,
                "clicked": True,
                "text": "Buy Now",
                "navigations": [
                    "https://shopee.ph/cart?itemKeys=999.888.&shopId=300"
                ],
            }

    monkeypatch.setattr(
        "purchase.execution.direct_checkout_initializer.BrowserActions",
        FakeActions,
    )

    initializer._open_product = lambda _session: None
    session.browser_session = SimpleNamespace(page=FakePage())

    class FakeVariationSelector:
        def select(self, selected_session):
            pass

    initializer.variation_selector = FakeVariationSelector()

    assert initializer.initialize(session, decision) is False

def test_initialize_fails_when_buy_now_cannot_be_clicked(monkeypatch):
    session = make_session()
    decision = make_decision()
    initializer = object.__new__(DirectCheckoutInitializer)

    class FakePage:
        url = "https://shopee.ph/product/1275798143/100"

    class FakeActions:
        def __init__(self, _session):
            pass

        def capture_pdp_purchase_controls(self, labels, timeout=10000):
            return []

        def click_visible_button_by_labels(self, labels, timeout=10000):
            return {"found": False, "clicked": False}

    monkeypatch.setattr(
        "purchase.execution.direct_checkout_initializer.BrowserActions",
        FakeActions,
    )

    initializer._open_product = lambda _session: None
    session.browser_session = SimpleNamespace(page=FakePage())

    assert initializer.initialize(session, decision) is False


def test_build_direct_checkout_url_remains_experimental_only():
    initializer = object.__new__(DirectCheckoutInitializer)

    url = initializer.build_direct_checkout_url(
        make_session(),
        make_decision(),
    )

    assert url == (
        "https://shopee.ph/checkout"
        "?buy_now=true&item_id=100&model_id=200&quantity=2"
    )
