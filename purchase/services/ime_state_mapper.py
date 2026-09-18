"""
Maps an observed SKU state and purchase session into the formal IME state.

The mapping intentionally keeps observation, session validity, and trigger
readiness separate. A live promotion is useful context, but it is not a
required prerequisite for every purchase trigger.
"""

from purchase.models.execution_decision import ExecutionDecision
from purchase.models.ime_state import IMEState
from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState


class IMEStateMapper:

    def map(
        self,
        session: PurchaseSession,
        state: SkuPriceState,
        trigger_reached: bool = False,
    ) -> IMEState:
        if trigger_reached and state.cookie_integrity:
            return IMEState.EXECUTION_READY

        if state.cookie_integrity:
            return IMEState.SESSION_VALID

        if state.has_stock:
            return IMEState.SKU_AVAILABLE

        if state.promotion_detected and state.promotion_event_status == "LIVE":
            return IMEState.PROMOTION_LIVE

        return IMEState.PRICE_OBSERVED

    def build_execution_decision(
        self,
        session: PurchaseSession,
        state: SkuPriceState,
    ) -> ExecutionDecision:
        return ExecutionDecision(
            item_id=state.item_id,
            model_id=state.model_id,
            promotion_id=state.promotion_id,
            target_price=session.request.target_price,
            execution_state=IMEState.EXECUTION_READY,
        )
