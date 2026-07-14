import re
from models.product import Product

class PageParser:

    def __init__(self, page):
        self.page = page

    def parse(self):

        product = Product(url=self.page.url)

        # Get product name
        product.name = self.get_name()

        # Get prices and discount
        prices = self.get_prices()

        product.current_price = prices["current_price"] or ""
        product.original_price = prices["original_price"] or ""
        product.discount = prices["discount"] or ""
        product.stock = self.get_stock()

        return product

    def get_name(self):

        try:
            return self.page.locator("h1").inner_text().strip()

        except:
            return None

    def get_price_section(self):

        sections = self.page.locator("section").all()

        for section in sections:

            try:
                text = section.inner_text()

                if "₱" in text:
                    return text

            except:
                pass

        return ""

    def get_prices(self):

        text = self.get_price_section()

        prices = re.findall(r"₱[\d,]+", text)

        discount = re.search(r"-\d+%", text)

        result = {
            "current_price": None,
            "original_price": None,
            "discount": None
        }

        if len(prices) >= 1:
            result["current_price"] = prices[0]

        if len(prices) >= 2:
            result["original_price"] = prices[1]

        if discount:
            result["discount"] = discount.group()

        return result

    def get_main_text(self):

        sections = self.page.locator("section").all()

        for section in sections:

            try:
                text = section.inner_text()

                if (
                    "Ratings" in text
                    and "Sold" in text
                    and "₱" in text
                ):
                    return text

            except:
                pass

        return ""

    def get_stock(self):

        text = self.get_main_text()

        if "OUT OF STOCK" in text.upper():
            return "OUT OF STOCK"

        if "IN STOCK" in text.upper():
            return "IN STOCK"

        return "UNKNOWN"