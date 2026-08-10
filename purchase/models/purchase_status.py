"""
Represents the current state of a purchase session.
"""

from enum import Enum


class PurchaseStatus(Enum):
    """
    High-level purchase pipeline status.
    """

    CREATED = "created"

    PREPARING = "preparing"

    READY = "ready"

    ADDING_TO_CART = "adding_to_cart"

    IN_CART = "in_cart"

    CHECKING_OUT = "checking_out"

    COMPLETED = "completed"

    FAILED = "failed"