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

        self.monitoring_service.start()

        return True, "Product added successfully."

    # =====================================================
    # Remove Product
    # =====================================================

    def remove_product(self, product):

        if product not in self.products:
            return False, "Product is not being monitored."

        self.monitoring_service.stop()

        self.products.remove(product)

        return True, "Monitoring stopped successfully."

    # =====================================================
    # Get Products
    # =====================================================

    def get_products(self):

        return self.products