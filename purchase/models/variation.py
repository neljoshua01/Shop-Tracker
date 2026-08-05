"""
Represents a purchasable Shopee model (SKU).
"""

from dataclasses import dataclass


@dataclass(slots=True)
class Variation:
    """
    Represents one purchasable product variation returned
    by Shopee's Product API.

    Example:
        Starlight / 40MM M/L
    """

    #
    # Shopee model identifier
    #
    model_id: int

    #
    # Human-readable variation name
    #
    name: str

    #
    # Pricing
    #
    price: float
    price_before_discount: float

    #
    # Availability
    #
    has_stock: bool

    #
    # Selected option indexes
    #
    tier_index: list[int]

    #
    # Variation-specific image
    #
    sku_image: str = ""