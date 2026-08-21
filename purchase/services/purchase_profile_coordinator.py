"""Connects saved purchase profiles to the existing V2 purchase pipeline."""

import threading
import time

from core.config.config_service import ConfigService
from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_status import PurchaseStatus
from purchase.services.purchase_profile_service import PurchaseProfileService
from purchase.services.purchase_service import PurchaseService


class PurchaseProfileCoordinator:
    """Prepares profiles synchronously, then runs each pipeline in the background."""

    def __init__(
        self,
        logger=None,
        pipeline_factory=PurchasePipeline,
        on_status_change=None,
        on_event=None,
        on_error=None,
    ):
        self.logger = logger
        self.pipeline_factory = pipeline_factory
        self.on_status_change = on_status_change
        self.on_event = on_event
        self.on_error = on_error
        self.active_profiles = {}
        self.active_sessions = {}
        self.threads = {}
        self._watchers = {}

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
        self.active_sessions[key] = session
        self.threads[key] = thread

        self._notify_status(profile, session)
        self._notify_event(profile, session, "MONITORING")

        watcher = threading.Thread(
            target=self._watch_session,
            args=(key, profile, session),
            daemon=True,
            name=f"PurchaseProfileState:{profile.product.item_id}",
        )
        self._watchers[key] = watcher

        thread.start()
        watcher.start()

        if profile.auto_checkout and not ConfigService().load()["armed_mode"]:
            self._log("Auto Checkout is in Safe Mode; checkout will stop at verification.")
        self._log(f"Purchase profile started: {profile.product.product_name}")
        return session

    def _run_pipeline(self, key, pipeline, session):
        try:
            pipeline.run(
                session,
                on_trigger=lambda: self._notify_event_by_key(key, "TRIGGERED"),
            )
        except Exception as exc:
            session.status = PurchaseStatus.FAILED
            self._notify_status_by_key(key)
            self._notify_error_by_key(key, exc)
            self._log(f"Purchase profile failed: {exc}")
        finally:
            self.threads.pop(key, None)

    def _watch_session(self, key, profile, session):
        last_status = session.status
        while key in self.active_sessions:
            current = session.status
            if current is not last_status:
                last_status = current
                self._notify_status(profile, session)
            if current in (PurchaseStatus.COMPLETED, PurchaseStatus.FAILED) and key not in self.threads:
                break
            time.sleep(0.05)
        self._watchers.pop(key, None)

    def _notify_status(self, profile, session):
        if self.on_status_change:
            self.on_status_change(profile, session)

    def _notify_status_by_key(self, key):
        profile = self.active_profiles.get(key)
        session = self.active_sessions.get(key)
        if profile is not None and session is not None:
            self._notify_status(profile, session)

    def _notify_event(self, profile, session, event):
        if self.on_event:
            self.on_event(profile, session, event)

    def _notify_event_by_key(self, key, event):
        profile = self.active_profiles.get(key)
        session = self.active_sessions.get(key)
        if profile is not None and session is not None:
            self._notify_event(profile, session, event)

    def _notify_error_by_key(self, key, error):
        profile = self.active_profiles.get(key)
        session = self.active_sessions.get(key)
        if profile is not None and session is not None and self.on_error:
            self.on_error(profile, session, error)

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
