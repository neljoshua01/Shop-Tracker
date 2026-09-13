"""
Promotion intelligence for the exact monitored Shopee SKU.

This module is observational only. It classifies promotion evidence exposed
by the selected model without changing price-trigger, cart, checkout, or
Place Order behavior.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class PromotionObservation:
    """Promotion facts for one exact item/model observation."""

    detected: bool
    promotion_id: Optional[int]
    promotion_types: tuple[int, ...]
    event_status: str
    seconds_until_start: Optional[int]
    seconds_until_end: Optional[int]
    evidence: tuple[str, ...]


class PromotionIntelligence:
    """Classify promotion evidence without becoming a purchase gate."""

    @staticmethod
    def analyze(
        model: dict,
        event_status: str = "NO_EVENT",
        seconds_until_start: Optional[int] = None,
        seconds_until_end: Optional[int] = None,
    ) -> PromotionObservation:
        if not isinstance(model, dict):
            return PromotionObservation(
                detected=False,
                promotion_id=None,
                promotion_types=(),
                event_status=event_status,
                seconds_until_start=seconds_until_start,
                seconds_until_end=seconds_until_end,
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

        evidence = []
        if promotion_id is not None:
            evidence.append("model_promotion_id")
        if promotion_types:
            evidence.append("model_promotion_type")

        # These signals are deliberately model-scoped. Product-level
        # price-promotion ranges are not treated as proof that this exact SKU
        # participates in the promotion.
        detected = bool(evidence)

        return PromotionObservation(
            detected=detected,
            promotion_id=promotion_id,
            promotion_types=promotion_types,
            event_status=event_status,
            seconds_until_start=seconds_until_start,
            seconds_until_end=seconds_until_end,
            evidence=tuple(evidence),
        )
