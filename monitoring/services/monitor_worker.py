from execution.browser.browser_connector import BrowserConnector
from services.page_parser import PageParser
from monitoring.services.product_monitor import ProductMonitor
from core.runtime.async_runtime import AsyncRuntime


class MonitorWorker:

    def __init__(
        self,
        url,
        logger=None,
        on_product_update=None,
        initial_product=None,
    ):

        self.runtime = AsyncRuntime.instance()

        self.url = url
        self.logger = logger
        self.on_product_update = on_product_update
        self.initial_product = initial_product

        self.browser = None
        self.page = None
        self.parser = None
        self.monitor = None
        self.checkout_handoff = False

    def run(self):

        print("[MonitorWorker] Worker started.")

        self.browser = BrowserConnector()
        self.browser.connect()

        print("[MonitorWorker] Browser connected.")

        self.page = self.browser.open_tab(self.url)

        print("[MonitorWorker] Monitoring tab ready.")

        self.parser = PageParser(self.page)

        self.monitor = ProductMonitor(
            self.page,
            self.parser,
            logger=self.logger,
            on_product_update=self.on_product_update,
            initial_product=self.initial_product,
            worker=self
        )

        print("[MonitorWorker] ProductMonitor initialized.")

        try:

            future = self.runtime.submit(
                self.monitor.start(interval=5)
            )

            future.result()
   
        finally:

            if not self.checkout_handoff:
                self.browser.close(self.page)

    def set_target(
        self,
        target_price,
        auto_checkout,
        target_locked
    ):

        if self.monitor:

            self.monitor.set_target(
                target_price,
                auto_checkout,
                target_locked
            )

    def stop(self):

        if self.monitor:
            self.monitor.stop()