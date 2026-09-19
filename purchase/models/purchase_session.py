"""Represents a purchase attempt."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from purchase.models.product_info import ProductInfo
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.variation import Variation
from purchase.models.purchase_status import PurchaseStatus
from execution.browser.browser_session import BrowserSession
from typing import Optional

from purchase.models.ime_state import IMEState
from purchase.models.execution_decision import ExecutionDecision


@dataclass(slots=True)
class PurchaseSession:
    """Runtime state of a purchase."""

    request: PurchaseRequest
    product: ProductInfo
    variation: Variation

    status: PurchaseStatus = field(default=PurchaseStatus.CREATED)

    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    browser_session: Optional[BrowserSession] = None

    monitored_item_id: Optional[int] = None
    monitored_model_id: Optional[int] = None
    monitored_sku_identity_verified: bool = False

    # PDP preparation is a one-time execution invariant. Once the requested
    # variation/quantity is prepared, the monitor must not reconstruct it at
    # trigger time.
    pdp_context_prepared: bool = False
    pdp_selection_verified: bool = False

    # URL of the browser-generated get_pc request captured from the prepared
    # PDP. Monitoring can poll this endpoint without reloading the PDP, which
    # preserves the rendered variation state for native Buy Now execution.
    monitoring_get_pc_url: Optional[str] = None

    ime_state: Optional[IMEState] = None
    execution_decision: Optional[ExecutionDecision] = None

    # E1 controlled-experiment timing recorder; measurement-only state.
    e1_timing: object | None = None

    monitored_order_id: Optional[int] = None
    monitored_checkout_id: Optional[int] = None
    monitored_order_identity_verified: bool = False

    successful_purchase_identity_verified: bool = False

    browser_owner: object = field(
        default_factory=object,
        repr=False,
        compare=False,
    )
