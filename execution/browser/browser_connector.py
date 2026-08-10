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

    def open_session(
        self,
        owner,
        url,
    ):

        print("[BrowserConnector] Opening monitoring page...")

        future = self.runtime.submit(
            self.engine.get_session(
                owner,
                url,
            )
        )

        session = future.result(timeout=30)

        print("[BrowserConnector] Navigation complete.")

        return session

    # =====================================================
    # Close
    # =====================================================

    def close_session(
        self,
        owner=None,
    ):

        #
        # BrowserEngine owns page lifecycle.
        #
        if owner is None:
            return

        future = self.runtime.submit(
            self.engine.close_session(owner)
        )

        future.result(timeout=10)

    def disconnect(self):

        future = self.runtime.submit(
            self.engine.disconnect()
        )

        future.result(timeout=15)