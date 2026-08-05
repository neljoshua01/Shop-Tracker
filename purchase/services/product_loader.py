"""
Loads Shopee products using the browser layer.
"""

from execution.browser.browser_connector import BrowserConnector
from purchase.models.product_reference import ProductReference


class ProductLoader:

    def __init__(self, browser: BrowserConnector):

        self.browser = browser

    def load(self, reference: ProductReference):

        self.browser.connect()

        page = self.browser.open_page(reference.url)

        return page