"""Connects saved purchase profiles to the existing V2 purchase pipeline."""

import threading

from core.config.config_service import ConfigService
from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.purchase_request import PurchaseRequest
from purchase.services.purchase_profile_service import PurchaseProfileService
from purchase.services.purchase_service import PurchaseService


class PurchaseProfileCoordinator:
    """Prepares a profile synchronously, then runs its pipeline in the background."""

    def __init__(self, logger=None, pipeline_factory=PurchasePipeline):
        self.logger = logger
        self.pipeline_factory = pipeline_factory
        self.active_profiles = {}
        self.threads = {}

    def start(self, profile: PurchaseProfile):
        PurchaseProfileService.validate(profile)

        if len(profile.selected_variations) != 1:
            raise ValueError("Select one purchasable variation.")

        variation = profile.selected_variations[0]
        request = PurchaseRequest(
            reference=ProductReference(
                shop_id=profile.product.shop_id,
                item_id=profile.product.item_id,
                url=profile.product.product_url,
            ),
            options=dict(variation.options),
            quantity=profile.quantity,
            auto_checkout=profile.auto_checkout,
            target_price=self._to_backend_price(profile.target_price),
            trigger=profile.trigger,
            polling_interval=profile.polling_interval,
            lock_selected_variations=profile.lock_selected_variations,
        )

        # Reuse the already browser-discovered ProductInfo. This retains
        # SelectionResolver and PurchaseSession as the backend boundary
        # without forcing a second PDP discovery.
        session = PurchaseService().prepare_from_product(request, profile.product)
        key = self._key(profile)

        if key in self.threads and self.threads[key].is_alive():
            raise ValueError("This purchase profile is already running.")

        pipeline = self.pipeline_factory()
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(key, pipeline, session),
            daemon=True,
            name=f"PurchaseProfile:{profile.product.item_id}",
        )
        self.active_profiles[key] = profile
        self.threads[key] = thread
        thread.start()
        if profile.auto_checkout and not ConfigService().load()["armed_mode"]:
            self._log("Auto Checkout is in Safe Mode; checkout will stop at verification.")
        self._log(f"Purchase profile started: {profile.product.product_name}")
        return session

    def _run_pipeline(self, key, pipeline, session):
        try:
            pipeline.run(session)
        except Exception as exc:
            self._log(f"Purchase profile failed: {exc}")
        finally:
            self.threads.pop(key, None)

    @staticmethod
    def _to_backend_price(price):
        if price is None:
            return None
        return int(round(price * 100_000))

    @staticmethod
    def _key(profile):
        return f"{profile.product.shop_id}:{profile.product.item_id}:{profile.selected_variations[0].model_id}"

    def _log(self, message):
        if self.logger:
            self.logger(message)
