from playwright.sync_api import sync_playwright


class ShopeeAdapter:

    def connect(self):

        playwright = sync_playwright().start()

        browser = playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )

        page = browser.contexts[0].pages[0]

        return playwright, browser, page


    def read_product(self):

        playwright, browser, page = self.connect()

        product = {
            "url": page.url,
            "name": None,
            "price": None,
            "stock": None,
            "promotion": None
        }

        try:
            product["name"] = page.locator("h1").inner_text(timeout=3000)
        except:
            pass

        try:
            product["price"] = page.locator(
                '[class*="price"]'
            ).first.inner_text(timeout=3000)
        except:
            pass

        browser.close()
        playwright.stop()

        return product