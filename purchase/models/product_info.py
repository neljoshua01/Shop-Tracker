"""
Product information loaded from Shopee.
"""

from dataclasses import dataclass, field
from typing import List

from purchase.models.variation import Variation


@dataclass(slots=True)
class ProductInfo:
    """
    Read-only product information discovered by IME.

    This represents the product itself.
    Individual purchasable SKUs are stored in
    available_variations.
    """

    #
    # Product identifiers
    #
    item_id: int
    shop_id: int

    #
    # Product details
    #
    product_name: str
    shop_name: str

    #
    # Metadata
    #
    product_url: str
    currency: str
    image: str

    #
    # Available SKUs
    #
    available_variations: List[Variation] = field(
        default_factory=list
    )