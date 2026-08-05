"""
Trigger conditions for monitoring and checkout.
"""

from enum import Enum


class TriggerCondition(Enum):
    """Conditions that activate monitoring or checkout."""

    TRACK_ONLY = "track_only"
    PRICE_TARGET = "price_target"
    STOCK_AVAILABLE = "stock_available"
    PRICE_AND_STOCK = "price_and_stock"