"""Direct-module validation for the Purchase Profile → V2 pipeline bridge."""

from threading import Event
import time

from purchase.models.product_info import ProductInfo
from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.variation import Variation
from purchase.services.purchase_profile_coordinator import PurchaseProfileCoordinator


class RecordingPipeline:
    ran = Event()
    session = None

    def run(self, session, on_trigger=None):
        self.__class__.session = session
        self.__class__.ran.set()
        return True


class BlockingPipeline:
    instances = []

    def __init__(self):
        self.running = Event()
        self.stopped = Event()
        self.__class__.instances.append(self)

    def run(self, session, on_trigger=None):
        self.running.set()
        self.stopped.wait(2)
        return False

    def stop(self):
        self.stopped.set()


def test_stop_by_key_stops_only_the_requested_profile_runtime():
    profile = make_profile(item_id=456, model_id=123)
    other_profile = make_profile(item_id=457, model_id=124)
    events = []
    coordinator = PurchaseProfileCoordinator(
        pipeline_factory=BlockingPipeline,
        on_event=lambda current_profile, _session, event: events.append((current_profile, event)),
    )

    coordinator.start(profile)
    coordinator.start(other_profile)
    first, second = BlockingPipeline.instances[-2:]
    assert first.running.wait(1)
    assert second.running.wait(1)

    assert coordinator.stop_by_key(coordinator.key_for(profile))
    deadline = time.monotonic() + 1
    while coordinator.key_for(profile) in coordinator.threads and time.monotonic() < deadline:
        time.sleep(0.01)

    assert first.stopped.is_set()
    assert coordinator.key_for(profile) not in coordinator.threads
    assert coordinator.key_for(profile) not in coordinator.pipelines
    assert coordinator.key_for(other_profile) in coordinator.threads
    assert not second.stopped.is_set()
    assert (profile, "MONITORING_STOPPED") in events

    coordinator.stop_by_key(coordinator.key_for(other_profile))


def make_profile(item_id, model_id):
    variation = Variation(
        model_id=model_id,
        name="Blue / 256GB",
        options={"Color": "Blue", "Storage": "256GB"},
        price=68990.0,
        price_before_discount=70990.0,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )
    product = ProductInfo(
        item_id=item_id,
        shop_id=789,
        product_name="Example Product",
        shop_name="Example Shop",
        product_url=f"https://shopee.ph/example-i.789.{item_id}",
        currency="PHP",
        image="",
        available_variations=[variation],
    )
    return PurchaseProfile(
        profile_name="Example Product",
        product=product,
        selected_variations=[variation],
        quantity=2,
        trigger=TriggerCondition.PRICE_AND_STOCK,
        target_price=68000.0,
        polling_interval=30,
        auto_checkout=False,
        lock_selected_variations=True,
    )


def main():
    variation = Variation(
        model_id=123,
        name="Blue / 256GB",
        options={"Color": "Blue", "Storage": "256GB"},
        price=68990.0,
        price_before_discount=70990.0,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )
    product = ProductInfo(
        item_id=456,
        shop_id=789,
        product_name="Example Product",
        shop_name="Example Shop",
        product_url="https://shopee.ph/example-i.789.456",
        currency="PHP",
        image="",
        available_variations=[variation],
    )
    profile = PurchaseProfile(
        profile_name="Example Product",
        product=product,
        selected_variations=[variation],
        quantity=2,
        trigger=TriggerCondition.PRICE_AND_STOCK,
        target_price=68000.0,
        polling_interval=30,
        auto_checkout=False,
        lock_selected_variations=True,
    )

    coordinator = PurchaseProfileCoordinator(pipeline_factory=RecordingPipeline)
    session = coordinator.start(profile)

    assert RecordingPipeline.ran.wait(2), "Purchase pipeline did not start."
    assert session.variation is variation
    assert session.request.quantity == 2
    assert session.request.target_price == 6_800_000_000
    assert session.request.trigger is TriggerCondition.PRICE_AND_STOCK
    assert session.request.polling_interval == 30
    assert session.request.lock_selected_variations is True
    print("Purchase Profile coordinator integration passed.")


if __name__ == "__main__":
    main()
