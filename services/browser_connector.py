from playwright.sync_api import sync_playwright


class BrowserConnector:

    def __init__(self):
        self.playwright = None
        self.browser = None

    def connect(self):
        print("[BrowserConnector] Connecting to Chrome...")
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )
        print("[BrowserConnector] Connected.")

    def open_tab(self, url):

        print("[BrowserConnector] Opening monitoring tab...")

        context = self.browser.contexts[0]

        page = context.new_page()

        page.goto(
            url,
            wait_until="domcontentloaded"
        )

        print("[BrowserConnector] Navigation complete.")

        return page

    def close(self):

        try:

            if self.page:
                self.page.close()

        except Exception:
            pass

        try:

            if self.browser:
                self.browser.close()

        except Exception:
            pass

        try:

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

        self.page = None
        self.browser = None
        self.playwright = None
