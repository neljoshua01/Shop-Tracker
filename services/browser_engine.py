from playwright.async_api import async_playwright


class BrowserEngine:

    _instance = None

    def __init__(self):

        self.playwright = None
        self.browser = None

    @classmethod
    def instance(cls):

        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

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

    async def open_page(self, url):

        #
        # Ensure browser exists
        #
        await self.connect()

        context = self.browser.contexts[0]

        page = await context.new_page()

        await page.goto(
            url,
            wait_until="domcontentloaded"
        )

        print(f"[BrowserEngine] Page opened: {url}")

        return page

    async def close_page(self, page):

        if page:

            await page.close()