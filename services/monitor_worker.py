from services.browser_connector import BrowserConnector
from services.page_parser import PageParser
from services.monitor import ProductMonitor
from services.async_runtime import AsyncRuntime


class MonitorWorker:

    def __init__(
        self,
        url,
        logger=None,
        on_product_update=None
    ):

        self.runtime = AsyncRuntime.instance()

        self.url = url
        self.logger = logger
        self.on_product_update = on_product_update

        self.browser = None
        self.parser = None
        self.monitor = None

    def run(self):

        print("[MonitorWorker] Worker started.")

        self.browser = BrowserConnector()
        self.browser.connect()

        print("[MonitorWorker] Browser connected.")

        page = self.browser.open_tab(self.url)

        print("[MonitorWorker] Monitoring tab ready.")

        self.parser = PageParser(page)

        self.monitor = ProductMonitor(
            page,
            self.parser,
            logger=self.logger,
            on_product_update=self.on_product_update
        )

        print("[MonitorWorker] ProductMonitor initialized.")

        try:

            future = self.runtime.submit(
                self.monitor.start(interval=5)
            )

            future.result()

        finally:

            self.browser.close()

    def stop(self):

        if self.monitor:
            self.monitor.stop()