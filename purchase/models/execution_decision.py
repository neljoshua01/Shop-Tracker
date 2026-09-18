"""
Decision produced by the IME before execution.

ExecutionDecision carries the exact SKU and pricing/promotion context that
was observed when the purchase trigger became actionable. It does not
authorize the final Place Order action.
"""

from dataclasses import dataclass
from typing import Optional

from purchase.models.ime_state import IMEState


@dataclass(frozen=True, slots=True)
class ExecutionDecision:
    item_id: int
    model_id: int
    variation_options: tuple[tuple[str, str], ...]
    quantity: int
    promotion_id: Optional[int]
    target_price: Optional[int]
    execution_state: IMEState
