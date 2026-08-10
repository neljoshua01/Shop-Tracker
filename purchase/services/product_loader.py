"""
Loads Shopee products using IME.
"""

from purchase.models.product_info import ProductInfo
from purchase.models.product_reference import ProductReference
from purchase.services.ime_loader import IMELoader


class ProductLoader:

    def __init__(self):

        self.ime = IMELoader()

    def load(
        self,
        reference: ProductReference,
    ) -> ProductInfo:
        """
        Loads a Shopee product.
        """

        return self.ime.load(
            reference.url,
        )