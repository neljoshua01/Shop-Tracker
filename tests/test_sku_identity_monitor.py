import unittest
from types import SimpleNamespace

from purchase.services.sku_price_monitor import SkuPriceMonitor


class FakeParser:
    def __init__(self, state):
        self.state = state

    def parse(self, data, model_id):
        return self.state


class FakeEvaluator:
    def evaluate(self, session, state):
        return False


class SkuIdentityMonitorTests(unittest.TestCase):

    def make_session(self, item_id=123, model_id=456):
        return SimpleNamespace(
            product=SimpleNamespace(item_id=item_id),
            variation=SimpleNamespace(model_id=model_id),
            monitored_item_id=None,
            monitored_model_id=None,
            monitored_sku_identity_verified=False,
        )

    def make_state(self, item_id=123, model_id=456):
        return SimpleNamespace(
            item_id=item_id,
            model_id=model_id,
            name="Test SKU",
            price=100,
            price_before_discount=100,
            promotion_id=None,
            promotion_types=(),
            deep_discount=False,
            promotion_price=None,
            promotion_event_status="NO_EVENT",
            promotion_seconds_until_start=None,
            promotion_seconds_until_end=None,
            promotion_is_lpp=None,
        )

    def make_monitor(self, state):
        monitor = SkuPriceMonitor()
        monitor.parser = FakeParser(state)
        monitor.evaluator = FakeEvaluator()
        return monitor

    def test_matching_item_and_model_are_recorded_as_verified(self):
        session = self.make_session()
        monitor = self.make_monitor(self.make_state())
        monitor.session = session

        monitor._process_get_pc({})

        self.assertTrue(session.monitored_sku_identity_verified)
        self.assertEqual(session.monitored_item_id, 123)
        self.assertEqual(session.monitored_model_id, 456)
        self.assertIsNotNone(monitor.latest_state)

    def test_model_mismatch_is_rejected(self):
        session = self.make_session(model_id=456)
        monitor = self.make_monitor(self.make_state(model_id=999))
        monitor.session = session

        monitor._process_get_pc({})

        self.assertFalse(session.monitored_sku_identity_verified)
        self.assertIsNone(session.monitored_item_id)
        self.assertIsNone(session.monitored_model_id)
        self.assertIsNone(monitor.latest_state)

    def test_item_mismatch_is_rejected(self):
        session = self.make_session(item_id=123)
        monitor = self.make_monitor(self.make_state(item_id=999))
        monitor.session = session

        monitor._process_get_pc({})

        self.assertFalse(session.monitored_sku_identity_verified)
        self.assertIsNone(session.monitored_item_id)
        self.assertIsNone(session.monitored_model_id)
        self.assertIsNone(monitor.latest_state)


if __name__ == "__main__":
    unittest.main()
