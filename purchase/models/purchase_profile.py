"""
Purchase profile domain model.
"""

from dataclasses import dataclass, field
from typing import List

from purchase.models.product_info import ProductInfo
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.variation import Variation


@dataclass(slots=True)
class PurchaseProfile:
    """
    Represents everything required to monitor
    and optionally purchase a Shopee product.
    """

    profile_name: str

    product: ProductInfo

    selected_variations: List[Variation] = field(default_factory=list)

    quantity: int = 1

    trigger: TriggerCondition = TriggerCondition.TRACK_ONLY

    target_price: float | None = None

    polling_interval: int = 30

    auto_checkout: bool = False

    lock_selected_variations: bool = True

    stock_alert: bool = True