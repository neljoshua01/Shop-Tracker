"""
Represents the current pricing and promotion state
of a selected Shopee SKU.
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

    #
    # Promotion state
    #

    deep_discount: bool = False

    promotion_price: Optional[int] = None

    promotion_event_status: str = "NO_EVENT"

    promotion_seconds_until_start: Optional[int] = None

    promotion_seconds_until_end: Optional[int] = None

    promotion_skin: Optional[dict] = None

    promotion_reminder_event: Optional[dict] = None

    promotion_is_lpp: Optional[bool] = None

    has_stock: bool = False
