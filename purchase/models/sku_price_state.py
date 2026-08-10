"""
Represents the current pricing state of a selected Shopee SKU.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class SkuPriceState:

    item_id: int

    model_id: int

    name: str

    price: int

    price_before_discount: Optional[int]

    promotion_id: Optional[int]

    promotion_types: tuple[int, ...]