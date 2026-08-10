from core.runtime.async_runtime import AsyncRuntime
from playwright.async_api import async_playwright
from execution.browser.browser_session import BrowserSession


class BrowserEngine:

    _instance = None

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.runtime = AsyncRuntime.instance()

        #
        # Owner -> Playwright Page
        #
        self.sessions = {}

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

    async def open_session(
        self,
        owner,
        url,
    ):

        await self.connect()

        context = self.browser.contexts[0]

        page = await context.new_page()

        session = BrowserSession(
            context=context,
            page=page,
        )

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

        self.sessions[owner] = session

        print(
            f"[BrowserEngine] "
            f"Session opened ({owner})"
        )

        return session

    async def get_session(
        self,
        owner,
        url,
    ):

        if owner in self.sessions:

            session = self.sessions[owner]

            if not session.page.is_closed():

                print(
                    f"[BrowserEngine] "
                    f"Reusing session ({owner})"
                )

                return session

            del self.sessions[owner]

        return await self.open_session(
            owner,
            url,
        )

    async def close_session(
        self,
        owner,
    ):

        session = self.sessions.get(owner)

        if session is None:
            return

        if session.page.is_closed():

            self.unregister_response_callback(owner)

            self.sessions.pop(owner, None)

            return

        await session.close()

        self.unregister_response_callback(owner)

        self.sessions.pop(owner, None)

        print(
            f"[BrowserEngine] "
            f"Session closed ({owner})"
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

    async def disconnect(self):

        #
        # Close every open session.
        #
        for owner in list(self.sessions.keys()):
            await self.close_session(owner)

        #
        # Disconnect browser.
        #
        if self.browser is not None:

            await self.browser.close()
            self.browser = None

        #
        # Stop Playwright.
        #
        if self.playwright is not None:

            await self.playwright.stop()
            self.playwright = None

        print("[BrowserEngine] Disconnected.")