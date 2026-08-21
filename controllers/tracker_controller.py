from monitoring.services.monitoring_service import MonitoringService
from core.config.settings_service import SettingsService
from purchase.services.purchase_profile_coordinator import PurchaseProfileCoordinator


class TrackerController:

    def __init__(self, logger=None):
        self.products = []
        self.ui_callback = None
        self.monitoring_state_callback = None
        self.monitoring_event_callback = None
        self.purchase_status_callback = None
        self.purchase_event_callback = None
        self.error_callback = None
        self.logger = logger

        self.settings = SettingsService()
        self.purchase_profiles = self.settings.load_purchase_profiles()

        self.purchase_profile_coordinator = PurchaseProfileCoordinator(
            logger=self.logger,
            on_status_change=self.on_purchase_status_change,
            on_event=self.on_purchase_event,
            on_error=self.on_purchase_error,
        )

        self.monitoring_service = MonitoringService(
            logger=self.logger,
            on_product_update=self.on_product_update,
            on_event=self.on_monitoring_event,
            on_state_change=self.on_monitoring_state_change,
            on_error=self.on_monitoring_error,
        )

    def set_ui_callback(self, callback):
        self.ui_callback = callback

    def set_monitoring_state_callback(self, callback):
        self.monitoring_state_callback = callback

    def set_monitoring_event_callback(self, callback):
        self.monitoring_event_callback = callback

    def set_purchase_status_callback(self, callback):
        self.purchase_status_callback = callback

    def set_purchase_event_callback(self, callback):
        self.purchase_event_callback = callback

    def set_error_callback(self, callback):
        self.error_callback = callback

    def on_monitoring_state_change(self, state, url=None, error=None):
        if self.monitoring_state_callback:
            self.monitoring_state_callback(state, url, error)

    def on_monitoring_event(self, url, event, product=None):
        if self.monitoring_event_callback:
            self.monitoring_event_callback(url, event, product)

    def on_monitoring_error(self, url, error):
        if self.error_callback:
            self.error_callback("monitoring", url, error)

    def on_product_update(self, product):
        if product.url not in self.monitoring_service.workers:
            return

        product.runtime_status = "MONITORING"

        for index, existing in enumerate(self.products):
            if existing.url == product.url:
                self.products[index] = product
                break
        else:
            self.products.append(product)

        if self.ui_callback:
            self.ui_callback(product)

        self.save_products()

    def on_target_updated(self, product, target_price, auto_checkout, target_locked):
        self.save_products()

    def set_target(self, product, target_price, auto_checkout, target_locked):
        self.monitoring_service.set_target(
            product.url,
            target_price,
            auto_checkout,
            target_locked
        )
        self.save_products()

    def add_product(self, url):
        url = url.strip()

        if url == "":
            return False, "Please enter a Shopee URL."

        if "shopee." not in url.lower():
            return False, "Please enter a valid Shopee product URL."

        success = self.monitoring_service.start(url)
        if not success:
            return False, "This product is already being monitored."

        return True, "Product added successfully."

    def remove_product(self, product):
        existing = next(
            (p for p in self.products if p.url == product.url),
            None
        )

        if existing is None:
            return False, "Product is not being monitored."

        success = self.monitoring_service.stop(existing.url)
        if not success:
            return False, "Failed to stop monitoring."

        self.products.remove(existing)
        self.save_products()
        return True, "Monitoring stopped successfully."

    def get_products(self):
        return self.products

    def create_purchase_profile(self, profile):
        session = self.purchase_profile_coordinator.start(profile)
        if profile not in self.purchase_profiles:
            self.purchase_profiles.append(profile)
            self.settings.save_purchase_profiles(self.purchase_profiles)
        return session

    def stop_purchase_profile(self, profile_key):
        """Request cancellation of one Purchase Profile runtime by its UI key."""
        return self.purchase_profile_coordinator.stop_by_key(profile_key)

    def on_purchase_status_change(self, profile, session):
        if self.purchase_status_callback:
            self.purchase_status_callback(profile, session)

    def on_purchase_event(self, profile, session, event):
        if self.purchase_event_callback:
            self.purchase_event_callback(profile, session, event)

    def on_purchase_error(self, profile, session, error):
        if self.error_callback:
            self.error_callback("purchase", profile, error)

    def get_active_purchase_profiles(self):
        return self.purchase_profile_coordinator.active_profiles

    def get_runtime_monitoring_state(self):
        """Return the real aggregate monitoring lifecycle for the UI."""
        service_state = self.monitoring_service.state
        purchase_monitoring_active = bool(self.purchase_profile_coordinator.threads)

        if service_state == MonitoringService.ERROR:
            return MonitoringService.ERROR

        if purchase_monitoring_active:
            return MonitoringService.RUNNING

        return service_state

    def get_runtime_monitoring_count(self):
        """Return the number of currently active monitoring runtimes."""
        normal_count = sum(
            1
            for thread in self.monitoring_service.threads.values()
            if thread.is_alive()
        )
        purchase_count = sum(
            1
            for thread in self.purchase_profile_coordinator.threads.values()
            if thread.is_alive()
        )
        return normal_count + purchase_count

    def save_products(self):
        print(f"[TrackerController] Saving {len(self.products)} products")
        self.settings.save_products(self.products)

    def load_products(self):
        self.products = self.settings.load_products()

        for product in self.products:
            self.monitoring_service.start(
                product.url,
                initial_product=product
            )

        return self.products
