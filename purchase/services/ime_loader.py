from threading import Event

from execution.browser.browser_connector import BrowserConnector
from purchase.parser.shopee_api_parser import ShopeeAPIParser


class IMELoader:

    def __init__(self):

        self.browser = BrowserConnector()

        self.loaded = Event()

        self.product = None

        self.session = None
        self.parser = ShopeeAPIParser()

    def load(
        self,
        url,
    ):

        #
        # Prepare for a new load
        #
        self.loaded.clear()
        self.product = None

        #
        # Connect to browser
        #
        self.browser.connect()

        #
        # Register for network responses
        #
        self.browser.engine.register_response_callback(
            self,
            self.on_response,
        )

        #
        # Open temporary session
        #
        self.session = self.browser.open_session(
            self,
            url,
        )

        #
        # Wait until ProductInfo is ready
        #
        self.loaded.wait(timeout=15)

        #
        # Close temporary session
        #
        self.browser.close_session(self)

        return self.product

    async def on_response(
        self,
        response,
    ):

        #
        # Ignore unrelated requests
        #
        if "/api/v4/pdp/get_pc" not in response.url:
            return

        print(
            "[IMELoader] Product API detected."
        )

        try:

            #
            # Read API JSON
            #
            data = await response.json()

            #
            # Parse ProductInfo
            #
            self.product = self.parser.parse(
                data,
            )

            print(
                "[IMELoader] Product parsed."
            )

            #
            # Notify load() that we're done
            #
            self.loaded.set()

        except Exception as e:

            print(
                f"[IMELoader] Failed to parse API: {e}"
            )

            self.loaded.set()