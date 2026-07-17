from services.async_runtime import AsyncRuntime
from services.browser_engine import BrowserEngine


class BrowserConnector:

    def __init__(self):

        self.runtime = AsyncRuntime.instance()

        self.engine = BrowserEngine.instance()

        self.browser = None

    # =====================================================
    # Connect
    # =====================================================

    def connect(self):

        print("[BrowserConnector] Requesting browser from BrowserEngine...")

        future = self.runtime.submit(
            self.engine.connect()
        )

        self.browser = future.result(timeout=15)

        print("[BrowserConnector] Browser acquired.")

    # =====================================================
    # Open Monitoring Tab
    # =====================================================

    def open_tab(self, url):

        print("[BrowserConnector] Opening monitoring tab...")

        future = self.runtime.submit(
            self.engine.open_page(url)
        )

        page = future.result(timeout=30)

        print("[BrowserConnector] Navigation complete.")

        return page

    # =====================================================
    # Close
    # =====================================================

    def close(self):

    #
    # BrowserEngine owns shutdown now.
    #
        pass