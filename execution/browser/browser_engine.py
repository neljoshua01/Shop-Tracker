from core.runtime.async_runtime import AsyncRuntime
from playwright.async_api import async_playwright


class BrowserEngine:

    _instance = None

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.runtime = AsyncRuntime.instance()

        #
        # Owner -> Playwright Page
        #
        self.pages = {}

        #
        # Owner -> Response callback
        #
        self.response_callbacks = {}

    # =====================================================
    # Singleton
    # =====================================================

    @classmethod
    def instance(cls):

        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

    # =====================================================
    # Browser Connection
    # =====================================================

    async def connect(self):

        if self.browser:
            return self.browser

        print("[BrowserEngine] Starting Playwright...")

        self.playwright = await async_playwright().start()

        print("[BrowserEngine] Connecting to Chrome...")

        self.browser = await self.playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )

        print("[BrowserEngine] Connected.")

        return self.browser

    # =====================================================
    # Page Management
    # =====================================================

    async def open_page(
        self,
        owner,
        url,
    ):

        await self.connect()

        context = self.browser.contexts[0]

        page = await context.new_page()

        #
        # Listen for every network response.
        #
        page.on(
            "response",
            lambda response: self.runtime.submit(
                self._handle_response(
                    owner,
                    response,
                )
            ),
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
        )

        self.pages[owner] = page

        print(
            f"[BrowserEngine] "
            f"Page opened ({owner})"
        )

        return page

    async def get_page(
        self,
        owner,
        url,
    ):

        if owner in self.pages:

            page = self.pages[owner]

            if not page.is_closed():

                print(
                    f"[BrowserEngine] "
                    f"Reusing page ({owner})"
                )

                return page

            del self.pages[owner]

        return await self.open_page(
            owner,
            url,
        )

    async def close_page(
        self,
        owner,
    ):

        page = self.pages.get(owner)

        if page is None:
            return

        if page.is_closed():

            self.unregister_response_callback(owner)

            self.pages.pop(owner, None)

            return

        await page.close()

        self.unregister_response_callback(owner)

        self.pages.pop(owner, None)

        print(
            f"[BrowserEngine] "
            f"Page closed ({owner})"
        )

    # =====================================================
    # Response Callbacks
    # =====================================================

    def register_response_callback(
        self,
        owner,
        callback,
    ):

        self.response_callbacks[owner] = callback

    def unregister_response_callback(
        self,
        owner,
    ):

        self.response_callbacks.pop(owner, None)

    async def _handle_response(
        self,
        owner,
        response,
    ):

        callback = self.response_callbacks.get(owner)

        if callback is None:
            return

        try:

            await callback(response)

        except Exception as e:

            print(
                f"[BrowserEngine] Response callback error: {e}"
            )