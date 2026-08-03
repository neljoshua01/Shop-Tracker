from playwright.async_api import async_playwright


class BrowserEngine:

    _instance = None

    def __init__(self):

        self.playwright = None
        self.browser = None

        #
        # URL -> Playwright Page
        #
        self.pages = {}

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

        #
        # Register page ownership
        #
        self.pages[url] = page

        print(f"[BrowserEngine] Page opened: {url}")

        return page
    
    async def get_page(self, url):

        #
        # Already opened?
        #
        if url in self.pages:

            page = self.pages[url]

            #
            # Ignore closed pages
            #
            if not page.is_closed():
                print(f"[BrowserEngine] Reusing page: {url}")
                return page

            #
            # Remove stale entry
            #
            del self.pages[url]

        #
        # Otherwise create one
        #
        return await self.open_page(url)
    
    async def close_page(self, page):

        if not page:
            return

        #
        # Remove from registry
        #
        for url, registered_page in list(self.pages.items()):

            if registered_page == page:
                del self.pages[url]
                break

        await page.close()

        print("[BrowserEngine] Page closed.")