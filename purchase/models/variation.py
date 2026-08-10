"""
Represents a purchasable Shopee model (SKU).
"""

from dataclasses import dataclass


@dataclass(slots=True)
class Variation:

    model_id: int

    #
    # Human-readable variation
    #
    name: str

    #
    # Structured options
    #
    options: dict[str, str]

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
    # Original Shopee data
    #
    tier_index: list[int]

    sku_image: str