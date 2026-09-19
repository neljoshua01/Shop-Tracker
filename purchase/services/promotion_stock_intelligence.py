"""Promotion-stock intelligence for an exact monitored Shopee SKU.

This module is observational only. It classifies model-level promotion and
stock evidence already exposed by the PDP API. It does not change trigger,
cart, checkout, payment, or Place Order behavior.
"""

from dataclasses import dataclass
from typing import Optional


NO_PROMOTION = "NO_PROMOTION"
UPCOMING = "UPCOMING"
LIVE = "LIVE"
LIVE_NO_RESERVE = "LIVE_NO_RESERVE"
LIVE_RESERVE_AVAILABLE = "LIVE_RESERVE_AVAILABLE"
ENDED = "ENDED"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PromotionStockObservation:
    """Exact-SKU promotion inventory evidence for one PDP observation."""

    state: str
    promotion_id: Optional[int]
    promotion_types: tuple[int, ...]
    event_status: str
    has_stock: bool
    current_promotion_reserved_stock: Optional[int]
    current_promotion_has_reserve_stock: Optional[bool]
    allocated_stock: Optional[int]
    evidence: tuple[str, ...]


class PromotionStockIntelligence:
    """Classify promotion-stock evidence without becoming a purchase gate."""

    @staticmethod
    def analyze(
        model: dict,
        *,
        promotion_detected: bool,
        event_status: str,
    ) -> PromotionStockObservation:
        if not isinstance(model, dict):
            return PromotionStockObservation(
                state=UNKNOWN,
                promotion_id=None,
                promotion_types=(),
                event_status=event_status,
                has_stock=False,
                current_promotion_reserved_stock=None,
                current_promotion_has_reserve_stock=None,
                allocated_stock=None,
                evidence=(),
            )

        promotion_id = model.get("promotion_id")
        if not isinstance(promotion_id, int) or promotion_id <= 0:
            promotion_id = None

        promotion_types = tuple(
            promotion_type
            for stock in model.get("price_stocks", [])
            if isinstance(stock, dict)
            for promotion_type in [stock.get("promotion_type")]
            if isinstance(promotion_type, int) and promotion_type > 0
        )

        has_stock = bool(model.get("has_stock", False))
        reserved_stock = model.get("current_promotion_reserved_stock")
        if not isinstance(reserved_stock, int) or reserved_stock < 0:
            reserved_stock = None

        reserve_signal = model.get("current_promotion_has_reserve_stock")
        if not isinstance(reserve_signal, bool):
            reserve_signal = None

        allocated_stock = PromotionStockIntelligence._allocated_stock(model)

        evidence = []
        if promotion_id is not None:
            evidence.append("model_promotion_id")
        if promotion_types:
            evidence.append("model_promotion_type")
        if "has_stock" in model:
            evidence.append("model_has_stock")
        if "current_promotion_has_reserve_stock" in model:
            evidence.append("current_promotion_has_reserve_stock")
        if reserved_stock is not None:
            evidence.append("current_promotion_reserved_stock")
        if allocated_stock is not None:
            evidence.append("promotion_allocated_stock")

        if not promotion_detected:
            state = NO_PROMOTION
        elif event_status == "UPCOMING":
            state = UPCOMING
        elif event_status == "ENDED":
            state = ENDED
        elif event_status == "LIVE":
            if reserve_signal is True or (
                reserved_stock is not None and reserved_stock > 0
            ):
                state = LIVE_RESERVE_AVAILABLE
            elif reserve_signal is False:
                state = LIVE_NO_RESERVE
            else:
                state = LIVE
        else:
            # A model-level promotion signal without a usable event state is
            # intentionally not promoted to LIVE. This prevents the stock
            # intelligence layer from inferring eligibility from incomplete
            # evidence.
            state = UNKNOWN

        return PromotionStockObservation(
            state=state,
            promotion_id=promotion_id,
            promotion_types=promotion_types,
            event_status=event_status,
            has_stock=has_stock,
            current_promotion_reserved_stock=reserved_stock,
            current_promotion_has_reserve_stock=reserve_signal,
            allocated_stock=allocated_stock,
            evidence=tuple(evidence),
        )

    @staticmethod
    def _allocated_stock(model: dict) -> Optional[int]:
        """Return positive allocated stock exposed by promotion price stocks.

        If multiple promotion price-stock entries expose allocated stock, the
        largest value is retained as the strongest available quantity signal.
        Zero is retained as evidence that an allocation field was present but
        currently empty. Missing/non-numeric values are ignored.
        """
        values = []
        for stock in model.get("price_stocks", []):
            if not isinstance(stock, dict):
                continue
            promotion_type = stock.get("promotion_type")
            if not isinstance(promotion_type, int) or promotion_type <= 0:
                continue
            value = stock.get("allocated_stock")
            if isinstance(value, int) and value >= 0:
                values.append(value)

        return max(values) if values else None
