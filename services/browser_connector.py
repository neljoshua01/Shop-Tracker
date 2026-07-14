from playwright.sync_api import sync_playwright


class BrowserConnector:

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def connect(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )

        context = self.browser.contexts[0]

        if context.pages:
            self.page = context.pages[0]
        else:
            self.page = context.new_page()

        return self.page

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

    def refresh(self):

        if not self.page:
            return

        try:

            self.page.reload(wait_until="domcontentloaded")

        except Exception:
            raise
