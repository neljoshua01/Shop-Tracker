"""
Formal operational state for the Intelligent Monitoring Engine (IME).

The enum describes what the engine has established from observation.
It does not itself authorize a purchase or a final order action.
"""

from enum import Enum


class IMEState(str, Enum):
    PRICE_OBSERVED = "price_observed"
    PROMOTION_LIVE = "promotion_live"
    SKU_AVAILABLE = "sku_available"
    SESSION_VALID = "session_valid"
    EXECUTION_READY = "execution_ready"
