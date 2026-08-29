"""Deterministic coverage for the runtime Armed/Safe authorization gate."""

import asyncio
from pathlib import Path
from core.config.config_service import ConfigService
from core.runtime.safety_gate import RuntimeSafetyGate
from execution.checkout.checkout_verifier import CheckoutVerifier
from purchase.execution.checkout_executor import CheckoutExecutor
from ui.safety_mode import set_armed_mode


class FailingSafetyGate:
    def is_final_action_authorized(self):
        raise RuntimeError("safety state unavailable")


class InvalidSafetyGate:
    def is_final_action_authorized(self):
        return "armed"


class FakePlaceOrder:
    def __init__(self):
        self.waited = False
        self.clicked = False
        self.first = self

    async def wait_for(self, **_kwargs):
        self.waited = True

    async def click(self):
        self.clicked = True


class FakePage:
    def __init__(self):
        self.button = FakePlaceOrder()

    def get_by_role(self, role, name):
        assert (role, name) == ("button", "Place Order")
        return self.button


def test_runtime_starts_safe_even_when_config_persisted_armed(tmp_path):
    config = ConfigService(tmp_path / "config.json")
    config.save({"armed_mode": True})
    assert config.load()["armed_mode"] is True

    # Runtime authorization deliberately does not hydrate from persisted config.
    assert RuntimeSafetyGate().is_final_action_authorized() is False


def test_explicit_armed_and_safe_states_control_execution_authorization():
    gate = RuntimeSafetyGate()
    executor = CheckoutExecutor(safety_gate=gate)

    assert executor.is_final_action_authorized() is False
    gate.set_armed(True)
    assert executor.is_final_action_authorized() is True
    gate.set_armed(False)
    assert executor.is_final_action_authorized() is False


def test_invalid_or_unavailable_safety_state_fails_closed():
    assert CheckoutExecutor(safety_gate=FailingSafetyGate()).is_final_action_authorized() is False
    assert CheckoutExecutor(safety_gate=InvalidSafetyGate()).is_final_action_authorized() is False


def test_purchase_profile_toggle_updates_runtime_gate_without_starting_checkout():
    gate = RuntimeSafetyGate()
    assert set_armed_mode(gate, True) is True
    assert gate.is_armed() is True

    assert set_armed_mode(gate, False) is False
    assert gate.is_armed() is False


def test_place_order_verification_remains_detection_only():
    page = FakePage()
    assert asyncio.run(CheckoutVerifier().verify_place_order(page)) is True
    assert page.button.waited is True
    assert page.button.clicked is False


def test_legacy_checkout_path_has_no_place_order_click():
    source = Path("execution/checkout/execution_engine.py").read_text(encoding="utf-8")
    assert "await place_order.click()" not in source
