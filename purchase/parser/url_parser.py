"""
Shopee URL parser.
"""

import re

from purchase.models.product_reference import ProductReference


class URLParser:
    """
    Parses Shopee product URLs.
    """

    PRODUCT_PATTERN = re.compile(
        r"i\.(\d+)\.(\d+)"
    )

    @classmethod
    def parse(cls, url: str) -> ProductReference:
        """
        Parse a Shopee product URL.

        Returns:
            ProductReference

        Raises:
            ValueError
        """

        if not url:
            raise ValueError("URL cannot be empty.")

        match = cls.PRODUCT_PATTERN.search(url)

        if match is None:
            raise ValueError("Invalid Shopee product URL.")

        shop_id = int(match.group(1))
        item_id = int(match.group(2))

        return ProductReference(
            shop_id=shop_id,
            item_id=item_id,
            url=url,
        )