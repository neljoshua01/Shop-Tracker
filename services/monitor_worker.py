from services.browser_connector import BrowserConnector
from services.page_parser import PageParser
from services.monitor import ProductMonitor


class MonitorWorker:

    def __init__(
        self,
        logger=None,
        on_product_update=None
    ):

        self.logger = logger
        self.on_product_update = on_product_update

        self.browser = None
        self.parser = None
        self.monitor = None

    def run(self):
        print("MonitorWorker -> run()")
        self.browser = BrowserConnector()

        page = self.browser.connect()
        print("MonitorWorker -> Browser connected")

        self.parser = PageParser(page)

        self.monitor = ProductMonitor(
            self.browser,
            self.parser,
            logger=self.logger,
            on_product_update=self.on_product_update
        )

        try:
            print("MonitorWorker -> Starting ProductMonitor")
            self.monitor.start(interval=2)

        finally:

            self.browser.close()

    def stop(self):

        if self.monitor:
            self.monitor.stop()