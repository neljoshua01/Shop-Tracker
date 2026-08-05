from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_engine import BrowserEngine


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

    def open_page(
        self,
        owner,
        url,
    ):

        print("[BrowserConnector] Opening monitoring page...")

        future = self.runtime.submit(
            self.engine.get_page(
                owner,
                url,
            )
        )

        page = future.result(timeout=30)

        print("[BrowserConnector] Navigation complete.")

        return page

    # =====================================================
    # Close
    # =====================================================

    def close(
        self,
        owner=None,
    ):

        #
        # BrowserEngine owns page lifecycle.
        #
        if owner is None:
            return

        future = self.runtime.submit(
            self.engine.close_page(owner)
        )

        future.result(timeout=10)