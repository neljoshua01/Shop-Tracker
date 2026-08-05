from dataclasses import dataclass


@dataclass(slots=True)
class ProductReference:
    """
    Identifies a Shopee product.
    """

    shop_id: int
    item_id: int

    url: str