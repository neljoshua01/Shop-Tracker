from services.monitoring_service import MonitoringService


class TrackerController:

    def __init__(self, logger=None):

        # ==========================
        # Product Data
        # ==========================

        self.products = []

        # ==========================
        # UI Callback
        # ==========================

        self.ui_callback = None

        # ==========================
        # Logger
        # ==========================

        self.logger = logger

        # ==========================
        # Monitoring Engine
        # (Will become multi-worker later)
        # ==========================

        self.monitoring_service = MonitoringService(
            logger=self.logger,
            on_product_update=self.on_product_update
        )

    # =====================================================
    # UI
    # =====================================================

    def set_ui_callback(self, callback):

        self.ui_callback = callback

    # =====================================================
    # Monitoring Updates
    # =====================================================

    def on_product_update(self, product):

        if product.url not in self.monitoring_service.workers:
            return   # stopped/removed since this update was queued — drop it

        for index, existing in enumerate(self.products):
            if existing.url == product.url:
                self.products[index] = product
                break
        else:
            self.products.append(product)

        if self.ui_callback:
            self.ui_callback(product)

    # =====================================================
    # Add Product
    # =====================================================

    def add_product(self, url):

        url = url.strip()

        # Empty textbox
        if url == "":
            return False, "Please enter a Shopee URL."

        # Basic Shopee URL validation
        if "shopee." not in url.lower():
            return False, "Please enter a valid Shopee product URL."

        success = self.monitoring_service.start(url)
        if not success:
            return False, "This product is already being monitored."

        return True, "Product added successfully."

    # =====================================================
    # Remove Product
    # =====================================================

    def remove_product(self, product):

        existing = next(
            (
                p for p in self.products
                if p.url == product.url
            ),
            None
        )

        if existing is None:
            return False, "Product is not being monitored."

        success = self.monitoring_service.stop(existing.url)

        if not success:
            return False, "Failed to stop monitoring."

        self.products.remove(existing)

        return True, "Monitoring stopped successfully."

    # =====================================================
    # Get Products
    # =====================================================

    def get_products(self):

        return self.products