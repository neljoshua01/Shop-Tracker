import re
from models.product import Product

class PageParser:

    def __init__(self, page):
        self.page = page

    async def parse(self):

        product = Product(url=self.page.url)

        # Get product name
        product.name = await self.get_name()

        # Get prices and discount
        prices = await self.get_prices()

        product.current_price = prices["current_price"] or ""
        product.original_price = prices["original_price"] or ""
        product.discount = prices["discount"] or ""
        product.stock = await self.get_stock()

        #get img of product
        product.stock = await self.get_stock()
        product.image_url = await self.get_image_url()


        return product

    async def get_name(self):

        try:
            text = await self.page.locator("h1").inner_text()
            return text.strip()
        
        except:
            return None

    async def get_price_section(self):

        sections = await self.page.locator("section").all()

        for section in sections:

            try:
                text = await section.inner_text()

                if "₱" in text:
                    return text

            except:
                pass

        return ""

    async def get_prices(self):

        text = await self.get_price_section()

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

    async def get_main_text(self):

        sections = await self.page.locator("section").all()

        for section in sections:

            try:
                text = await section.inner_text()

                if (
                    "Ratings" in text
                    and "Sold" in text
                    and "₱" in text
                ):
                    return text

            except:
                pass

        return ""

    async def get_stock(self):

        text = await self.get_main_text()

        if "OUT OF STOCK" in text.upper():
            return "OUT OF STOCK"

        if "IN STOCK" in text.upper():
            return "IN STOCK"

        return "UNKNOWN"
    
    async def get_image_url(self):

        #
        # og:image is the single most reliable source — it's the
        # exact image Shopee itself designates as "the" product photo,
        # same one used for link previews.
        #
        try:
            meta = self.page.locator('meta[property="og:image"]')

            if await meta.count() > 0:
                url = await meta.first.get_attribute("content")
                if url:
                    return url

        except:
            pass

        #
        # Fallback: first Shopee CDN image on the page.
        #
        try:
            img = self.page.locator("img[src*='cf.shopee']").first
            url = await img.get_attribute("src")
            if url:
                return url

        except:
            pass

        return ""