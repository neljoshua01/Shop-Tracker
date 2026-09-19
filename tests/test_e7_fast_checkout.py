import asyncio

import pytest

from execution.browser.browser_action import BrowserActions


class FakeLocator:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    async def get_attribute(self, name):
        assert name == "aria-checked"
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        return value


def run_wait(actions, locator, **kwargs):
    return actions.wait_for_attribute(locator, "aria-checked", "true", **kwargs)


def test_e7_checkbox_wait_returns_as_soon_as_state_is_true(monkeypatch):
    actions = BrowserActions.__new__(BrowserActions)
    actions._submit = lambda coro, timeout: asyncio.run(coro)
    locator = FakeLocator(["false", "false", "true"])

    result = run_wait(actions, locator, timeout=1000, poll_interval=0.001)

    assert result == "true"
    assert locator.calls == 3


def test_e7_checkbox_wait_times_out_when_state_never_settles(monkeypatch):
    actions = BrowserActions.__new__(BrowserActions)
    actions._submit = lambda coro, timeout: asyncio.run(coro)
    locator = FakeLocator(["false"])

    with pytest.raises(TimeoutError):
        run_wait(actions, locator, timeout=5, poll_interval=0.001)

    assert locator.calls >= 1
