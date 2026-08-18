"""
Represents a purchase attempt.
"""

from dataclasses import dataclass, field

from purchase.models.product_info import ProductInfo
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.variation import Variation
from purchase.models.purchase_status import PurchaseStatus
from execution.browser.browser_session import BrowserSession
from typing import Optional


@dataclass(slots=True)
class PurchaseSession:
    """
    Runtime state of a purchase.

    This object is progressively populated as
    the purchase advances.
    """

    #
    # Original user request
    #
    request: PurchaseRequest

    #
    # Product discovered from Shopee
    #
    product: ProductInfo

    #
    # Selected SKU
    #
    variation: Variation

    #
    # Current pipeline state
    #
    status: PurchaseStatus = field(
        default=PurchaseStatus.CREATED,
    )

    browser_session: Optional[BrowserSession] = None

    # Opaque, hashable engine owner for this one purchase attempt.
    # Services use this token rather than using themselves as an
    # owner, so the browser page survives service handoffs.
    browser_owner: object = field(
        default_factory=object,
        repr=False,
        compare=False,
    )
